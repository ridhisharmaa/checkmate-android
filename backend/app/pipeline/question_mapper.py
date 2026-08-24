"""Stage: match student answer entries to teacher gradable units.

Deterministic label-normalization runs first (free, exact when numbering is intact).
Whatever's left over — missing/garbled/ambiguous numbering — goes to a single LLM
call that only sees the *remaining* unmatched units and entries, matched by content.
Accuracy over speed here, per explicit product decision: this is the highest-risk
step in the whole pipeline.
"""
import re
from collections import defaultdict
from abc import ABC, abstractmethod

from app.routing.base import Capability
from app.routing.registry import ModelRouter, RouterExhaustedError
from app.schemas.document import GradableUnit
from app.schemas.mapping import LLMMatchResult, MappedAnswer
from app.schemas.student import StudentAnswerEntry

_LABEL_STRIP_RE = re.compile(r"[^a-z0-9]+")
# A leading "Q" is a question marker, not part of the number. Stripping punctuation
# alone left "Q1" as "q1" while a student's bare "1" stayed "1", so the two never
# matched and every such question fell through to the LLM content matcher.
# Only stripped before a digit, so a subpart labelled just "q" survives intact.
_LEADING_Q_RE = re.compile(r"^q(?=\d)")


def normalize_label(raw: str) -> str:
    """'Q2(b)', '2.b', '2 b', 'Q.2.b' all normalize to '2b'."""
    return _LEADING_Q_RE.sub("", _LABEL_STRIP_RE.sub("", raw.lower()))


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
        # Labels are NOT unique across a paper — sections routinely restart numbering,
        # so "1" can mean Section A Q1 and Section B Q1 on the same sheet. Keyed by a
        # bare label (as this used to be) the later section silently overwrites the
        # earlier one, which both zeroes Section A and grades Section B against
        # Section A's answers. Group by label and disambiguate below instead.
        by_norm_label: dict[str, list[GradableUnit]] = defaultdict(list)
        for u in units:
            by_norm_label[normalize_label(u.label)].append(u)

        # How many times the student wrote each label, and which occurrence each entry is.
        # Keyed by id() rather than the entry itself: two answers can be byte-identical
        # (same label, same text) and would otherwise collapse to one occurrence.
        label_counts: dict[str, int] = defaultdict(int)
        occurrence_of: dict[int, int] = {}
        for e in entries:
            key = normalize_label(e.raw_label)
            if key:
                occurrence_of[id(e)] = label_counts[key]
                label_counts[key] += 1

        matched: dict[str, MappedAnswer] = {}
        unmatched_entries: list[StudentAnswerEntry] = []

        for entry in entries:
            key = normalize_label(entry.raw_label)
            candidates = by_norm_label.get(key, []) if key else []

            if len(candidates) == 1:
                unit = candidates[0]
            elif len(candidates) > 1 and label_counts[key] == len(candidates):
                # Ambiguous label, but the student wrote it exactly as many times as the
                # paper uses it — pair them up in order (k-th written "1" answers the
                # k-th "1" on the paper). Safe because the counts line up exactly.
                unit = candidates[occurrence_of[id(entry)]]
            else:
                # Genuinely ambiguous (counts disagree) — hand it to content matching
                # rather than guessing, since a wrong guess grades the wrong question.
                unit = None

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
