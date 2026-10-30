from typing import Literal

from pydantic import BaseModel


class RollRangeRequest(BaseModel):
    start: int
    end: int


class AddRollNumberRequest(BaseModel):
    roll_number: str


class StudentSummary(BaseModel):
    id: str
    roll_number: str
    submission_id: str | None = None
    status: Literal["not_uploaded", "queued", "running", "done", "failed"] = "not_uploaded"
    total_score: float | None = None
    max_score: float | None = None
    grade_letter: str | None = None


class ExamSummary(BaseModel):
    id: str
    title: str
    subject: str
    max_marks: float | None
    student_count: int
    graded_count: int


class ExamDetailResponse(BaseModel):
    id: str
    title: str
    subject: str
    max_marks: float | None
    students: list[StudentSummary]
