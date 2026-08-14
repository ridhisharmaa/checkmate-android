from typing import Literal

from pydantic import BaseModel

from app.schemas.document import GradableUnit
from app.schemas.student import StudentAnswerEntry


class MappedAnswer(BaseModel):
    unit: GradableUnit
    student_entry: StudentAnswerEntry | None  # None => student did not attempt this unit
    match_method: Literal["deterministic", "llm_assisted", "unmatched"]
    confidence: float = 1.0


class LLMMatchPair(BaseModel):
    unit_id: str
    entry_index: int  # index into the unmatched-entries list passed to the LLM
    confidence: float


class LLMMatchResult(BaseModel):
    pairs: list[LLMMatchPair]
