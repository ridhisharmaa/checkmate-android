"""Student-side OCR output. Deliberately flat — see document.py docstring."""
from pydantic import BaseModel, Field


class StudentAnswerEntry(BaseModel):
    raw_label: str  # whatever numbering the student wrote, verbatim ("Q2(b)", "2.", "", ...)
    answer_text: str
    attempted: bool = True
    has_diagram: bool = False
    has_table: bool = False
    has_code: bool = False


class ParsedStudentDocument(BaseModel):
    entries: list[StudentAnswerEntry] = Field(default_factory=list)
    handwriting_confidence: float = Field(
        default=0.8, ge=0.0, le=1.0, description="OCR model's own confidence in legibility, 0-1"
    )
