from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.jobs.queue import enqueue
from app.models.submission import GradingJob, QuestionResult, Submission
from app.pipeline.aggregator import aggregate
from app.schemas.api import (
    QuestionOverridePatchRequest,
    SubmissionCreateResponse,
    SubmissionDetailResponse,
)
from app.schemas.document import TeacherDocument
from app.schemas.grading import OverviewSummary, QuestionGradeResult, SubmissionResult
from app.storage.local import save_bytes, save_upload

router = APIRouter()

OVERRIDE_FRACTIONS = {"full": 1.0, "half": 0.5, "no_credit": 0.0}


def _row_to_result(r: QuestionResult) -> QuestionGradeResult:
    return QuestionGradeResult(
        id=r.id,
        unit_id=r.unit_id,
        path=r.path_json,
        label=r.label,
        question_text=r.question_text,
        model_answer=r.model_answer,
        student_answer=r.student_answer,
        attempted=r.attempted,
        max_marks=r.max_marks,
        similarity_score=r.similarity_score,
        llm_score_pct=r.llm_score_pct,
        final_score=r.final_score,
        feedback=r.feedback,
        counted_toward_total=r.counted_toward_total,
        teacher_override=r.teacher_override,  # type: ignore[arg-type]
        has_diagram=r.has_diagram,
        has_table=r.has_table,
        has_code=r.has_code,
    )


@router.post("/submissions", response_model=SubmissionCreateResponse)
async def create_submission(
    teacher_files: list[UploadFile] = File(...),
    student_files: list[UploadFile] = File(...),
    db: AsyncSession = Depends(get_db),
) -> SubmissionCreateResponse:
    submission = Submission(status="queued")
    db.add(submission)
    await db.flush()  # assigns submission.id, needed for the storage path below

    submission.teacher_file_paths = [
        await save_upload(submission.id, "teacher", i, f) for i, f in enumerate(teacher_files)
    ]
    submission.student_file_paths = [
        await save_upload(submission.id, "student", i, f) for i, f in enumerate(student_files)
    ]

    job = GradingJob(submission_id=submission.id, status="queued")
    db.add(job)
    await db.commit()

    await enqueue(job.id)
    return SubmissionCreateResponse(submission_id=submission.id, job_id=job.id)


@router.post("/submissions/batch", response_model=list[SubmissionCreateResponse])
async def create_submissions_batch(
    teacher_files: list[UploadFile] = File(...),
    student_files: list[UploadFile] = File(...),  # one sheet per student
    db: AsyncSession = Depends(get_db),
) -> list[SubmissionCreateResponse]:
    # Read the shared teacher answer key once — UploadFile is a single-use stream,
    # so re-invoking save_upload() on it for every student submission would only
    # succeed for the first iteration and silently write empty files after that.
    teacher_blobs = [(f.filename, await f.read()) for f in teacher_files]

    responses = []
    for student_file in student_files:
        submission = Submission(status="queued")
        db.add(submission)
        await db.flush()

        submission.teacher_file_paths = [
            save_bytes(submission.id, "teacher", i, name, blob) for i, (name, blob) in enumerate(teacher_blobs)
        ]
        submission.student_file_paths = [await save_upload(submission.id, "student", 0, student_file)]

        job = GradingJob(submission_id=submission.id, status="queued")
        db.add(job)
        await db.commit()

        await enqueue(job.id)
        responses.append(SubmissionCreateResponse(submission_id=submission.id, job_id=job.id))

    return responses


@router.get("/submissions/{submission_id}", response_model=SubmissionDetailResponse)
async def get_submission(submission_id: str, db: AsyncSession = Depends(get_db)) -> SubmissionDetailResponse:
    submission = await db.get(Submission, submission_id)
    if submission is None:
        raise HTTPException(status_code=404, detail="submission not found")

    if submission.status != "done":
        return SubmissionDetailResponse(submission_id=submission.id, status=submission.status, result=None)  # type: ignore[arg-type]

    rows = (
        await db.execute(select(QuestionResult).where(QuestionResult.submission_id == submission_id))
    ).scalars().all()

    results = [_row_to_result(r) for r in rows]

    submission_result = SubmissionResult(
        overview=OverviewSummary.model_validate(submission.overview_json or {"strengths": [], "watch_for": []}),
        handwriting_confidence=submission.handwriting_confidence or 0.0,
        results=results,
        total_score=submission.total_score or 0.0,
        max_score=submission.max_score or 0.0,
        grade_letter=submission.grade_letter or "",
    )
    return SubmissionDetailResponse(submission_id=submission.id, status=submission.status, result=submission_result)  # type: ignore[arg-type]


@router.patch("/submissions/{submission_id}/questions/{question_id}", response_model=SubmissionDetailResponse)
async def override_question(
    submission_id: str,
    question_id: str,
    body: QuestionOverridePatchRequest,
    db: AsyncSession = Depends(get_db),
) -> SubmissionDetailResponse:
    question = await db.get(QuestionResult, question_id)
    if question is None or question.submission_id != submission_id:
        raise HTTPException(status_code=404, detail="question result not found")

    question.teacher_override = body.override
    question.final_score = round(question.max_marks * OVERRIDE_FRACTIONS[body.override], 2)
    await db.flush()

    rows = (
        await db.execute(select(QuestionResult).where(QuestionResult.submission_id == submission_id))
    ).scalars().all()

    submission = await db.get(Submission, submission_id)
    if submission is None:
        raise HTTPException(status_code=404, detail="submission not found")

    # Re-run the real aggregator rather than re-adding the totals by hand. Summing the
    # already-counted rows kept whichever answers won the "attempt any N of M" choice
    # at grading time, so raising an excluded answer to full marks could not promote it
    # into the counted set — and grade_letter, being derived, went stale as well.
    teacher_doc = TeacherDocument.model_validate(submission.teacher_document_json or {"sections": []})
    recomputed = aggregate(
        teacher_doc,
        [_row_to_result(r) for r in rows],
        OverviewSummary.model_validate(submission.overview_json or {"strengths": [], "watch_for": []}),
        submission.handwriting_confidence or 0.0,
    )

    counted_by_unit = {r.unit_id: r.counted_toward_total for r in recomputed.results}
    for row in rows:
        row.counted_toward_total = counted_by_unit.get(row.unit_id, row.counted_toward_total)

    submission.total_score = recomputed.total_score
    submission.max_score = recomputed.max_score
    submission.grade_letter = recomputed.grade_letter
    await db.commit()

    return await get_submission(submission_id, db)
