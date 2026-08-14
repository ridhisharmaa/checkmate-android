from typing import Literal

from pydantic import BaseModel

from app.schemas.grading import SubmissionResult


class SubmissionCreateResponse(BaseModel):
    submission_id: str
    job_id: str


class JobStatusResponse(BaseModel):
    job_id: str
    status: Literal["queued", "running", "done", "failed"]
    current_stage: str | None
    error_message: str | None


class SubmissionDetailResponse(BaseModel):
    submission_id: str
    status: Literal["queued", "running", "done", "failed"]
    result: SubmissionResult | None


class QuestionOverridePatchRequest(BaseModel):
    override: Literal["full", "half", "no_credit"]
