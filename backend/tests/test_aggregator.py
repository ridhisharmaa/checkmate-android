"""Regression tests for choice-group ("attempt any N of M") scoring.

The bug these pin down: unattempted units in a choice group kept the default
counted_toward_total=True, so their max_marks inflated the denominator. A student
who answered exactly the required 2 of 4 questions perfectly scored 20/40 (D)
instead of 20/20 (A+).
"""
from app.pipeline.aggregator import aggregate
from app.schemas.document import Question, Section, SelectionRule, TeacherDocument, flatten_to_units
from app.schemas.grading import OverviewSummary, QuestionGradeResult

EMPTY_OVERVIEW = OverviewSummary(strengths=[], watch_for=[])


def _paper(n_questions: int, marks: float = 10.0, rule: SelectionRule | None = None) -> TeacherDocument:
    return TeacherDocument(
        sections=[
            Section(
                id="s1",
                title="Section B",
                selection_rule=rule,
                questions=[
                    Question(
                        label=str(i), question_text=f"Question {i}", max_marks=marks, model_answer="reference"
                    )
                    for i in range(1, n_questions + 1)
                ],
            )
        ]
    )


def _results(doc: TeacherDocument, scores: list[float | None]) -> list[QuestionGradeResult]:
    """scores[i] is the mark awarded, or None for a question the student skipped."""
    out = []
    for unit, score in zip(flatten_to_units(doc), scores):
        attempted = score is not None
        out.append(
            QuestionGradeResult(
                unit_id=unit.unit_id,
                path=unit.path,
                label=unit.label,
                question_text=unit.question_text,
                model_answer=unit.model_answer,
                student_answer="answer" if attempted else None,
                attempted=attempted,
                max_marks=unit.max_marks,
                final_score=score or 0.0,
                feedback="ok",
            )
        )
    return out


def test_answering_exactly_the_required_count_is_scored_out_of_that_count():
    doc = _paper(4, rule=SelectionRule(n=2))
    result = aggregate(doc, _results(doc, [10.0, 10.0, None, None]), EMPTY_OVERVIEW, 0.9)

    assert (result.total_score, result.max_score) == (20.0, 20.0)
    assert result.grade_letter == "A+"


def test_extra_attempts_beyond_n_do_not_inflate_the_denominator():
    doc = _paper(4, rule=SelectionRule(n=2))
    # Attempted three; only the best two may count, toward score AND max.
    result = aggregate(doc, _results(doc, [4.0, 10.0, 9.0, None]), EMPTY_OVERVIEW, 0.9)

    assert (result.total_score, result.max_score) == (19.0, 20.0)
    counted = [r for r in result.results if r.counted_toward_total]
    assert sorted(r.final_score for r in counted) == [9.0, 10.0]


def test_attempting_fewer_than_n_still_scores_out_of_n():
    doc = _paper(4, rule=SelectionRule(n=2))
    # Only one answered: the skipped requirement must still cost marks.
    result = aggregate(doc, _results(doc, [10.0, None, None, None]), EMPTY_OVERVIEW, 0.9)

    assert (result.total_score, result.max_score) == (10.0, 20.0)
    assert result.grade_letter == "D"  # 50%


def test_section_without_a_selection_rule_counts_every_question():
    doc = _paper(4, rule=None)
    result = aggregate(doc, _results(doc, [10.0, 10.0, None, None]), EMPTY_OVERVIEW, 0.9)

    # No choice offered, so the two skipped questions rightly count against the student.
    assert (result.total_score, result.max_score) == (20.0, 40.0)


def test_unattempted_choice_questions_are_excluded_from_the_response_totals():
    doc = _paper(3, rule=SelectionRule(n=1))
    result = aggregate(doc, _results(doc, [7.0, None, None]), EMPTY_OVERVIEW, 0.9)

    assert result.max_score == 10.0
    assert sum(1 for r in result.results if r.counted_toward_total) == 1
    # Excluded questions stay in the payload for display, just uncounted.
    assert len(result.results) == 3
