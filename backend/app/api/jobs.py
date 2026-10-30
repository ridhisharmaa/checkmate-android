from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import get_current_teacher
from app.db import get_db
from app.models.exam import Exam
from app.models.submission import GradingJob, Submission
from app.models.teacher import Teacher
from app.schemas.api import JobStatusResponse

router = APIRouter()


@router.get("/jobs/{job_id}", response_model=JobStatusResponse)
async def get_job(
    job_id: str, teacher: Teacher = Depends(get_current_teacher), db: AsyncSession = Depends(get_db)
) -> JobStatusResponse:
    job = await db.get(GradingJob, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="job not found")

    submission = await db.get(Submission, job.submission_id)
    exam = await db.get(Exam, submission.exam_id) if submission else None
    if exam is None or exam.teacher_id != teacher.id:
        raise HTTPException(status_code=404, detail="job not found")

    return JobStatusResponse(
        job_id=job.id,
        status=job.status,  # type: ignore[arg-type]
        current_stage=job.current_stage,
        error_message=job.error_message,
    )
