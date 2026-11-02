"""Banded marking: full / half / zero per question, no fractional awards."""
import asyncio

import pytest

from app.api.submissions import override_marks
from app.pipeline.answer_grader import LLMSemanticGrader
from app.pipeline.marking import banded_marks, half_marks
from app.schemas.document import GradableUnit
from app.schemas.grading import LLMQuestionScore, OverviewSummary, ScoringCallResult
from app.schemas.mapping import MappedAnswer
from app.schemas.student import StudentAnswerEntry


def test_bands_for_a_ten_mark_question():
    assert banded_marks(10, 100) == 10
    assert banded_marks(10, 70) == 10      # 70% exactly counts as "70% or more"
    assert banded_marks(10, 69.9) == 5
    assert banded_marks(10, 35) == 5       # 35% exactly counts as half
    assert banded_marks(10, 34.9) == 0
    assert banded_marks(10, 0) == 0


def test_half_marks_are_whole_numbers_rounded_half_up():
    assert half_marks(10) == 5
    assert half_marks(5) == 3      # 2.5 -> 3
    assert half_marks(7) == 4      # 3.5 -> 4
    assert half_marks(1) == 1      # 0.5 -> 1
    assert half_marks(2) == 1


def test_override_uses_the_same_numbers_as_the_bands():
    for max_marks in (1, 2, 5, 7, 10):
        assert override_marks(max_marks, "full") == max_marks
        assert override_marks(max_marks, "half") == banded_marks(max_marks, 50)
        assert override_marks(max_marks, "no_credit") == 0


class _FakeRouter:
    def __init__(self, llm_pct):
        self.llm_pct = llm_pct

    async def generate(self, capability, prompt, images, schema):
        return ScoringCallResult(
            scores=[LLMQuestionScore(unit_id="u1", score_percentage=self.llm_pct, feedback="ok")],
            overview=OverviewSummary(strengths=[], watch_for=[]),
        )


def _grade(llm_pct, sim, max_marks, *, attempted=True, flags=(False, False)):
    grader = LLMSemanticGrader(_FakeRouter(llm_pct), similarity_model=None)
    grader._similarity = lambda a, b: sim
    unit = GradableUnit(
        unit_id="u1", section_id="s1", section_title="S", selection_rule=None,
        path=["Q1"], label="1", question_text="q", model_answer="ref",
        max_marks=max_marks, has_diagram=flags[0],
    )
    entry = StudentAnswerEntry(raw_label="1", answer_text="ans", attempted=attempted, has_diagram=flags[1])
    mapped = [MappedAnswer(unit=unit, student_entry=entry, match_method="deterministic")]
    results, _ = asyncio.run(grader.grade(mapped))
    return results[0]


@pytest.mark.parametrize(
    "llm_pct, sim, expected",
    [(90, 0.8, 10), (60, 0.5, 5), (20, 0.1, 0)],
)
def test_grader_returns_only_full_half_or_zero(llm_pct, sim, expected):
    assert _grade(llm_pct, sim, 10).final_score == expected


def test_bonus_can_lift_an_answer_over_a_band_edge():
    # 0.35*0.6 + 0.65*0.5 = 53.5% -> half; a matching diagram adds 5 points -> still half
    assert _grade(50, 0.6, 10, flags=(True, True)).final_score == 5
    # 0.35*0.6 + 0.65*0.7 = 66.5% -> half; +5 points = 71.5% -> full
    assert _grade(70, 0.6, 10, flags=(False, False)).final_score == 5
    assert _grade(70, 0.6, 10, flags=(True, True)).final_score == 10


def test_unattempted_gets_zero_even_with_a_diagram_flag():
    assert _grade(90, 0.9, 10, attempted=False, flags=(True, True)).final_score == 0
