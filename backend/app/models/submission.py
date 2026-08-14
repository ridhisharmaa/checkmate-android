import uuid
from datetime import datetime, timezone

from sqlalchemy import JSON, Boolean, DateTime, Float, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


def _uuid() -> str:
    return uuid.uuid4().hex


def _now() -> datetime:
    return datetime.now(timezone.utc)


class Submission(Base):
    __tablename__ = "submissions"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, onupdate=_now)

    teacher_file_paths: Mapped[list] = mapped_column(JSON, default=list)
    student_file_paths: Mapped[list] = mapped_column(JSON, default=list)

    status: Mapped[str] = mapped_column(String(16), default="queued")  # queued|running|done|failed
    teacher_document_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    overview_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    handwriting_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)

    total_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    max_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    grade_letter: Mapped[str | None] = mapped_column(String(4), nullable=True)

    question_results: Mapped[list["QuestionResult"]] = relationship(
        back_populates="submission", cascade="all, delete-orphan"
    )
    job: Mapped["GradingJob"] = relationship(back_populates="submission", uselist=False, cascade="all, delete-orphan")


class GradingJob(Base):
    __tablename__ = "grading_jobs"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    submission_id: Mapped[str] = mapped_column(ForeignKey("submissions.id"))
    status: Mapped[str] = mapped_column(String(16), default="queued")  # queued|running|done|failed
    current_stage: Mapped[str | None] = mapped_column(String(64), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, onupdate=_now)

    submission: Mapped["Submission"] = relationship(back_populates="job")


class QuestionResult(Base):
    __tablename__ = "question_results"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    submission_id: Mapped[str] = mapped_column(ForeignKey("submissions.id"))

    unit_id: Mapped[str] = mapped_column(String(32))
    path_json: Mapped[list] = mapped_column(JSON, default=list)
    label: Mapped[str] = mapped_column(String(32))
    question_text: Mapped[str] = mapped_column(Text)
    model_answer: Mapped[str] = mapped_column(Text)
    student_answer: Mapped[str | None] = mapped_column(Text, nullable=True)
    attempted: Mapped[bool] = mapped_column(Boolean, default=True)
    max_marks: Mapped[float] = mapped_column(Float)

    similarity_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    llm_score_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    final_score: Mapped[float] = mapped_column(Float)
    feedback: Mapped[str] = mapped_column(Text)
    counted_toward_total: Mapped[bool] = mapped_column(Boolean, default=True)
    teacher_override: Mapped[str | None] = mapped_column(String(16), nullable=True)  # full|half|no_credit

    has_diagram: Mapped[bool] = mapped_column(Boolean, default=False)
    has_table: Mapped[bool] = mapped_column(Boolean, default=False)
    has_code: Mapped[bool] = mapped_column(Boolean, default=False)

    submission: Mapped["Submission"] = relationship(back_populates="question_results")
