from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import get_current_teacher
from app.db import get_db
from app.models.exam import Exam, Student
from app.models.submission import Submission
from app.models.teacher import Teacher
from app.schemas.exam import (
    AddRollNumberRequest,
    ExamDetailResponse,
    ExamSummary,
    RollRangeRequest,
    StudentSummary,
)
from app.storage.local import save_upload

router = APIRouter(prefix="/exams", tags=["exams"])


async def _get_owned_exam(exam_id: str, teacher: Teacher, db: AsyncSession) -> Exam:
    exam = await db.get(Exam, exam_id)
    if exam is None or exam.teacher_id != teacher.id:
        # 404, not 403 — don't reveal that an exam id belongs to someone else.
        raise HTTPException(status_code=404, detail="exam not found")
    return exam


def _roll_sort_key(student: Student) -> tuple[int, object]:
    try:
        return (0, int(student.roll_number))
    except ValueError:
        return (1, student.roll_number)


def _max_marks_of(teacher_doc_json: dict) -> float:
    total = 0.0
    for section in teacher_doc_json.get("sections", []):
        for question in section.get("questions", []):
            subparts = question.get("subparts") or []
            if subparts:
                total += sum(s["max_marks"] for s in subparts)
            else:
                total += question.get("max_marks", 0.0)
    return total


@router.post("", response_model=ExamSummary)
async def create_exam(
    request: Request,
    title: str = Form(...),
    subject: str = Form(""),
    answer_key_files: list[UploadFile] = File(...),
    teacher: Teacher = Depends(get_current_teacher),
    db: AsyncSession = Depends(get_db),
) -> ExamSummary:
    exam = Exam(teacher_id=teacher.id, title=title, subject=subject)
    db.add(exam)
    await db.flush()  # assigns exam.id, needed for the storage path below

    exam.teacher_file_paths = [
        await save_upload(exam.id, "answer_key", i, f) for i, f in enumerate(answer_key_files)
    ]

    # Parsed once, here — every later submission to this exam reuses this same
    # parsed answer key instead of re-running OCR on it.
    orchestrator = request.app.state.orchestrator
    try:
        teacher_doc = await orchestrator.parse_answer_key(exam.teacher_file_paths)
    except Exception as e:
        raise HTTPException(status_code=422, detail=f"could not parse answer key: {e}") from e

    teacher_doc_json = teacher_doc.model_dump()
    exam.teacher_document_json = teacher_doc_json
    exam.max_marks = _max_marks_of(teacher_doc_json)
    await db.commit()

    return ExamSummary(
        id=exam.id, title=exam.title, subject=exam.subject, max_marks=exam.max_marks,
        student_count=0, graded_count=0,
    )


@router.get("", response_model=list[ExamSummary])
async def list_exams(
    teacher: Teacher = Depends(get_current_teacher), db: AsyncSession = Depends(get_db)
) -> list[ExamSummary]:
    exams = (await db.execute(select(Exam).where(Exam.teacher_id == teacher.id))).scalars().all()

    summaries = []
    for exam in exams:
        students = (await db.execute(select(Student).where(Student.exam_id == exam.id))).scalars().all()
        student_ids = [s.id for s in students]
        graded_count = 0
        if student_ids:
            done = (
                await db.execute(
                    select(Submission).where(
                        Submission.student_id.in_(student_ids), Submission.status == "done"
                    )
                )
            ).scalars().all()
            graded_count = len(done)
        summaries.append(
            ExamSummary(
                id=exam.id, title=exam.title, subject=exam.subject, max_marks=exam.max_marks,
                student_count=len(students), graded_count=graded_count,
            )
        )
    return summaries


@router.get("/{exam_id}", response_model=ExamDetailResponse)
async def get_exam(
    exam_id: str, teacher: Teacher = Depends(get_current_teacher), db: AsyncSession = Depends(get_db)
) -> ExamDetailResponse:
    exam = await _get_owned_exam(exam_id, teacher, db)
    students = (await db.execute(select(Student).where(Student.exam_id == exam.id))).scalars().all()
    students = sorted(students, key=_roll_sort_key)

    summaries = []
    for student in students:
        submission = (
            await db.execute(select(Submission).where(Submission.student_id == student.id))
        ).scalar_one_or_none()
        if submission is None:
            summaries.append(StudentSummary(id=student.id, roll_number=student.roll_number))
        else:
            summaries.append(
                StudentSummary(
                    id=student.id,
                    roll_number=student.roll_number,
                    submission_id=submission.id,
                    status=submission.status,  # type: ignore[arg-type]
                    total_score=submission.total_score,
                    max_score=submission.max_score,
                    grade_letter=submission.grade_letter,
                )
            )
    return ExamDetailResponse(
        id=exam.id, title=exam.title, subject=exam.subject, max_marks=exam.max_marks, students=summaries
    )


@router.post("/{exam_id}/roster/range", response_model=list[StudentSummary])
async def add_roll_range(
    exam_id: str,
    body: RollRangeRequest,
    teacher: Teacher = Depends(get_current_teacher),
    db: AsyncSession = Depends(get_db),
) -> list[StudentSummary]:
    exam = await _get_owned_exam(exam_id, teacher, db)
    if body.end < body.start:
        raise HTTPException(status_code=422, detail="end must be >= start")

    existing = {
        s.roll_number
        for s in (await db.execute(select(Student).where(Student.exam_id == exam.id))).scalars().all()
    }
    created: list[Student] = []
    for n in range(body.start, body.end + 1):
        roll = str(n)
        if roll in existing:  # idempotent: re-running to extend a range skips what's already there
            continue
        student = Student(exam_id=exam.id, roll_number=roll)
        db.add(student)
        created.append(student)
    await db.commit()

    return [StudentSummary(id=s.id, roll_number=s.roll_number) for s in created]


@router.post("/{exam_id}/roster", response_model=StudentSummary)
async def add_roll_number(
    exam_id: str,
    body: AddRollNumberRequest,
    teacher: Teacher = Depends(get_current_teacher),
    db: AsyncSession = Depends(get_db),
) -> StudentSummary:
    exam = await _get_owned_exam(exam_id, teacher, db)
    existing = (
        await db.execute(
            select(Student).where(Student.exam_id == exam.id, Student.roll_number == body.roll_number)
        )
    ).scalar_one_or_none()
    if existing is not None:
        raise HTTPException(status_code=409, detail="roll number already exists in this exam")

    student = Student(exam_id=exam.id, roll_number=body.roll_number)
    db.add(student)
    await db.commit()
    return StudentSummary(id=student.id, roll_number=student.roll_number)


@router.delete("/{exam_id}/roster/{student_id}", status_code=204)
async def remove_roll_number(
    exam_id: str,
    student_id: str,
    teacher: Teacher = Depends(get_current_teacher),
    db: AsyncSession = Depends(get_db),
) -> None:
    exam = await _get_owned_exam(exam_id, teacher, db)
    student = await db.get(Student, student_id)
    if student is None or student.exam_id != exam.id:
        raise HTTPException(status_code=404, detail="roll number not found")

    submission = (
        await db.execute(select(Submission).where(Submission.student_id == student.id))
    ).scalar_one_or_none()
    if submission is not None:
        raise HTTPException(status_code=409, detail="cannot remove a roll number that already has a submission")

    await db.delete(student)
    await db.commit()
