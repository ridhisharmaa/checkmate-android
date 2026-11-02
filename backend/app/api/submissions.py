from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import get_current_teacher
from app.db import get_db
from app.jobs.queue import enqueue
from app.models.exam import Exam, Student
from app.models.submission import GradingJob, QuestionResult, Submission
from app.models.teacher import Teacher
from app.pipeline.aggregator import aggregate
from app.pipeline.marking import half_marks
from app.schemas.api import (
    QuestionOverridePatchRequest,
    SubmissionCreateResponse,
    SubmissionDetailResponse,
)
from app.schemas.document import TeacherDocument
from app.schemas.grading import OverviewSummary, QuestionGradeResult, SubmissionResult
from app.storage.local import save_upload

router = APIRouter(tags=["submissions"])



def override_marks(max_marks: float, override: str) -> float:
    if override == "full":
        return max_marks
    if override == "half":
        return half_marks(max_marks)
    return 0.0


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


async def _get_owned_submission(submission_id: str, teacher: Teacher, db: AsyncSession) -> Submission:
    submission = await db.get(Submission, submission_id)
    if submission is None:
        raise HTTPException(status_code=404, detail="submission not found")
    exam = await db.get(Exam, submission.exam_id)
    if exam is None or exam.teacher_id != teacher.id:
        # 404, not 403 — don't reveal that a submission id belongs to someone else.
        raise HTTPException(status_code=404, detail="submission not found")
    return submission


@router.post("/exams/{exam_id}/students/{student_id}/submission", response_model=SubmissionCreateResponse)
async def create_submission(
    exam_id: str,
    student_id: str,
    student_files: list[UploadFile] = File(...),
    teacher: Teacher = Depends(get_current_teacher),
    db: AsyncSession = Depends(get_db),
) -> SubmissionCreateResponse:
    exam = await db.get(Exam, exam_id)
    if exam is None or exam.teacher_id != teacher.id:
        raise HTTPException(status_code=404, detail="exam not found")
    if exam.teacher_document_json is None:
        raise HTTPException(status_code=422, detail="this exam's answer key has not been parsed yet")

    student = await db.get(Student, student_id)
    if student is None or student.exam_id != exam.id:
        raise HTTPException(status_code=404, detail="roll number not found in this exam")

    existing = (
        await db.execute(select(Submission).where(Submission.student_id == student.id))
    ).scalar_one_or_none()
    if existing is not None:
        raise HTTPException(status_code=409, detail="this roll number already has a submission")

    submission = Submission(exam_id=exam.id, student_id=student.id, status="queued")
    db.add(submission)
    await db.flush()  # assigns submission.id, needed for the storage path below

    submission.student_file_paths = [
        await save_upload(submission.id, "student", i, f) for i, f in enumerate(student_files)
    ]

    job = GradingJob(submission_id=submission.id, status="queued")
    db.add(job)
    await db.commit()

    await enqueue(job.id)
    return SubmissionCreateResponse(submission_id=submission.id, job_id=job.id)


@router.get("/submissions/{submission_id}", response_model=SubmissionDetailResponse)
async def get_submission(
    submission_id: str,
    teacher: Teacher = Depends(get_current_teacher),
    db: AsyncSession = Depends(get_db),
) -> SubmissionDetailResponse:
    submission = await _get_owned_submission(submission_id, teacher, db)

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
    teacher: Teacher = Depends(get_current_teacher),
    db: AsyncSession = Depends(get_db),
) -> SubmissionDetailResponse:
    submission = await _get_owned_submission(submission_id, teacher, db)

    question = await db.get(QuestionResult, question_id)
    if question is None or question.submission_id != submission_id:
        raise HTTPException(status_code=404, detail="question result not found")

    question.teacher_override = body.override
    question.final_score = override_marks(question.max_marks, body.override)
    await db.flush()

    rows = (
        await db.execute(select(QuestionResult).where(QuestionResult.submission_id == submission_id))
    ).scalars().all()

    exam = await db.get(Exam, submission.exam_id)

    # Re-run the real aggregator rather than re-adding the totals by hand. Summing the
    # already-counted rows kept whichever answers won the "attempt any N of M" choice
    # at grading time, so raising an excluded answer to full marks could not promote it
    # into the counted set — and grade_letter, being derived, went stale as well.
    teacher_doc = TeacherDocument.model_validate((exam and exam.teacher_document_json) or {"sections": []})
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

    return await get_submission(submission_id, teacher, db)
