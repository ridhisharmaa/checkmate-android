from typing import Literal

from pydantic import BaseModel, Field


class LLMQuestionScore(BaseModel):
    """One question's slice of the batched scoring call's response."""

    unit_id: str
    score_percentage: float = Field(ge=0, le=100)
    feedback: str


class OverviewSummary(BaseModel):
    strengths: list[str]
    watch_for: list[str]


class ScoringCallResult(BaseModel):
    """Schema for the single batched Gemini scoring call: every question's score
    plus the overall overview, in one response."""

    scores: list[LLMQuestionScore]
    overview: OverviewSummary


class QuestionGradeResult(BaseModel):
    id: str | None = None  # QuestionResult row id; unset until persisted, needed for PATCH overrides
    unit_id: str
    path: list[str]
    label: str
    question_text: str
    model_answer: str
    student_answer: str | None
    attempted: bool
    max_marks: float
    similarity_score: float | None = None
    llm_score_pct: float | None = None
    final_score: float
    feedback: str
    counted_toward_total: bool = True
    teacher_override: Literal["full", "half", "no_credit"] | None = None
    has_diagram: bool = False
    has_table: bool = False
    has_code: bool = False


class SubmissionResult(BaseModel):
    overview: OverviewSummary
    handwriting_confidence: float
    results: list[QuestionGradeResult]
    total_score: float
    max_score: float
    grade_letter: str
