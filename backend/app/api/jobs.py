from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.models.submission import GradingJob
from app.schemas.api import JobStatusResponse

router = APIRouter()


@router.get("/jobs/{job_id}", response_model=JobStatusResponse)
async def get_job(job_id: str, db: AsyncSession = Depends(get_db)) -> JobStatusResponse:
    job = await db.get(GradingJob, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="job not found")
    return JobStatusResponse(
        job_id=job.id,
        status=job.status,  # type: ignore[arg-type]
        current_stage=job.current_stage,
        error_message=job.error_message,
    )
