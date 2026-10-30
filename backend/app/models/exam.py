import uuid
from datetime import datetime, timezone

from sqlalchemy import JSON, DateTime, Float, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


def _uuid() -> str:
    return uuid.uuid4().hex


def _now() -> datetime:
    return datetime.now(timezone.utc)


class Exam(Base):
    __tablename__ = "exams"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    teacher_id: Mapped[str] = mapped_column(ForeignKey("teachers.id"), index=True)
    title: Mapped[str] = mapped_column(String(255))
    subject: Mapped[str] = mapped_column(String(255), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    # The answer key is parsed once, here — not per student submission.
    teacher_file_paths: Mapped[list] = mapped_column(JSON, default=list)
    teacher_document_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    max_marks: Mapped[float | None] = mapped_column(Float, nullable=True)

    students: Mapped[list["Student"]] = relationship(back_populates="exam", cascade="all, delete-orphan")


class Student(Base):
    """A roll number enrolled in one exam. No name field — rosters are pure roll-number
    lists, generated via a start/end range and edited individually from there."""

    __tablename__ = "students"
    __table_args__ = (UniqueConstraint("exam_id", "roll_number", name="uq_student_exam_roll"),)

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    exam_id: Mapped[str] = mapped_column(ForeignKey("exams.id"), index=True)
    roll_number: Mapped[str] = mapped_column(String(32))

    exam: Mapped["Exam"] = relationship(back_populates="students")
