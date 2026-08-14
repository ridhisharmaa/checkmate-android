"""Teacher-side document hierarchy: Section -> Question -> Subpart.

This is the only side of the pipeline that gets a real tree. Handwritten student
numbering is too unreliable to force into the same structure at OCR time (see
student.py) — reconciling the two is what the question-mapping stage is for.
"""
from __future__ import annotations

from typing import Literal
from uuid import uuid4

from pydantic import BaseModel, Field


class SelectionRule(BaseModel):
    """Represents an 'Attempt any N of M' instruction on a section."""

    type: Literal["attempt_n_of_m"] = "attempt_n_of_m"
    n: int


class Subpart(BaseModel):
    label: str  # "a", "b", "c"
    question_text: str
    model_answer: str
    max_marks: float
    has_diagram: bool = False
    has_table: bool = False
    has_code: bool = False


class Question(BaseModel):
    label: str  # "1", "Q7"
    question_text: str
    max_marks: float
    is_mcq: bool = False
    mcq_options: list[str] | None = None
    mcq_correct: str | None = None
    # Only set when the question has no subparts (i.e. it is itself a gradable leaf).
    model_answer: str | None = None
    has_diagram: bool = False
    has_table: bool = False
    has_code: bool = False
    subparts: list[Subpart] = Field(default_factory=list)


class Section(BaseModel):
    id: str = Field(default_factory=lambda: uuid4().hex[:8])
    title: str
    selection_rule: SelectionRule | None = None
    questions: list[Question] = Field(default_factory=list)


class TeacherDocument(BaseModel):
    sections: list[Section] = Field(default_factory=list)


class GradableUnit(BaseModel):
    """A leaf of the teacher tree: a subpart, an MCQ, or a subpart-less question.

    This is what mapping and grading actually operate on — the tree only matters
    for display and for resolving 'attempt any N of M' choice groups afterwards.
    """

    unit_id: str
    section_id: str
    section_title: str
    selection_rule: SelectionRule | None
    path: list[str]  # e.g. ["Section A", "Q2", "b"]
    label: str
    question_text: str
    model_answer: str
    max_marks: float
    is_mcq: bool = False
    mcq_options: list[str] | None = None
    mcq_correct: str | None = None
    has_diagram: bool = False
    has_table: bool = False
    has_code: bool = False


def flatten_to_units(doc: TeacherDocument) -> list[GradableUnit]:
    units: list[GradableUnit] = []
    for section in doc.sections:
        for question in section.questions:
            if question.subparts:
                for sub in question.subparts:
                    units.append(
                        GradableUnit(
                            unit_id=uuid4().hex[:12],
                            section_id=section.id,
                            section_title=section.title,
                            selection_rule=section.selection_rule,
                            path=[section.title, question.label, sub.label],
                            label=f"{question.label}({sub.label})",
                            question_text=sub.question_text,
                            model_answer=sub.model_answer,
                            max_marks=sub.max_marks,
                            has_diagram=sub.has_diagram,
                            has_table=sub.has_table,
                            has_code=sub.has_code,
                        )
                    )
            else:
                units.append(
                    GradableUnit(
                        unit_id=uuid4().hex[:12],
                        section_id=section.id,
                        section_title=section.title,
                        selection_rule=section.selection_rule,
                        path=[section.title, question.label],
                        label=question.label,
                        question_text=question.question_text,
                        model_answer=question.model_answer or "",
                        max_marks=question.max_marks,
                        is_mcq=question.is_mcq,
                        mcq_options=question.mcq_options,
                        mcq_correct=question.mcq_correct,
                        has_diagram=question.has_diagram,
                        has_table=question.has_table,
                        has_code=question.has_code,
                    )
                )
    return units
