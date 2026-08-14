"""Stage: match student answer entries to teacher gradable units.

Deterministic label-normalization runs first (free, exact when numbering is intact).
Whatever's left over — missing/garbled/ambiguous numbering — goes to a single LLM
call that only sees the *remaining* unmatched units and entries, matched by content.
Accuracy over speed here, per explicit product decision: this is the highest-risk
step in the whole pipeline.
"""
import re
from abc import ABC, abstractmethod

from app.routing.base import Capability
from app.routing.registry import ModelRouter, RouterExhaustedError
from app.schemas.document import GradableUnit
from app.schemas.mapping import LLMMatchResult, MappedAnswer
from app.schemas.student import StudentAnswerEntry

_LABEL_STRIP_RE = re.compile(r"[^a-z0-9]+")


def normalize_label(raw: str) -> str:
    """'Q2(b)', '2.b', '2 b', 'Q.2.b' all normalize to '2b'."""
    return _LABEL_STRIP_RE.sub("", raw.lower())


LLM_MATCH_PROMPT = """\
Some student answers could not be matched to a question by their written number
(missing, illegible, or ambiguous numbering). Match each unmatched answer to the
unmatched question it most likely responds to, based on content.

Unmatched questions:
{units_block}

Unmatched student answers (0-indexed):
{entries_block}

Only return a pair if you are reasonably confident of the match — do not force a
match for answers that don't clearly correspond to any listed question. It's fine
for some units or entries to be left with no match.
"""


class QuestionMapper(ABC):
    @abstractmethod
    async def map(self, units: list[GradableUnit], entries: list[StudentAnswerEntry]) -> list[MappedAnswer]: ...


class HybridQuestionMapper(QuestionMapper):
    def __init__(self, router: ModelRouter):
        self._router = router

    async def map(self, units: list[GradableUnit], entries: list[StudentAnswerEntry]) -> list[MappedAnswer]:
        by_norm_label: dict[str, GradableUnit] = {normalize_label(u.label): u for u in units}

        matched: dict[str, MappedAnswer] = {}
        unmatched_entries: list[StudentAnswerEntry] = []

        for entry in entries:
            key = normalize_label(entry.raw_label)
            unit = by_norm_label.get(key) if key else None
            if unit is not None and unit.unit_id not in matched:
                matched[unit.unit_id] = MappedAnswer(
                    unit=unit, student_entry=entry, match_method="deterministic", confidence=1.0
                )
            else:
                unmatched_entries.append(entry)

        unmatched_units = [u for u in units if u.unit_id not in matched]

        if unmatched_units and unmatched_entries:
            try:
                llm_pairs = await self._llm_assisted_match(unmatched_units, unmatched_entries)
            except RouterExhaustedError:
                llm_pairs = []  # degrade: leave these as unmatched rather than failing the whole submission
            for pair in llm_pairs:
                unit = next((u for u in unmatched_units if u.unit_id == pair.unit_id), None)
                if unit is None or unit.unit_id in matched:
                    continue
                if not (0 <= pair.entry_index < len(unmatched_entries)):
                    continue
                matched[unit.unit_id] = MappedAnswer(
                    unit=unit,
                    student_entry=unmatched_entries[pair.entry_index],
                    match_method="llm_assisted",
                    confidence=pair.confidence,
                )

        for unit in units:
            if unit.unit_id not in matched:
                matched[unit.unit_id] = MappedAnswer(
                    unit=unit, student_entry=None, match_method="unmatched", confidence=0.0
                )

        return [matched[u.unit_id] for u in units]

    async def _llm_assisted_match(self, units: list[GradableUnit], entries: list[StudentAnswerEntry]):
        units_block = "\n".join(f"- unit_id={u.unit_id}: {u.question_text[:200]}" for u in units)
        entries_block = "\n".join(f"[{i}] {e.answer_text[:200]}" for i, e in enumerate(entries))
        prompt = LLM_MATCH_PROMPT.format(units_block=units_block, entries_block=entries_block)
        result = await self._router.generate(Capability.TEXT, prompt, None, LLMMatchResult)
        return result.pairs  # type: ignore[union-attr]
