"""Regression tests for label matching across sections that restart numbering.

The bug these pin down: units were keyed in a flat dict by normalized label, so on a
paper with "Section A: 1, 2" and "Section B: 1, 2" the later section overwrote the
earlier one. Section A scored zero AND Section B was graded against Section A's answers.
"""
import asyncio

from app.pipeline.question_mapper import HybridQuestionMapper, normalize_label
from app.schemas.document import Question, Section, TeacherDocument, flatten_to_units
from app.schemas.mapping import LLMMatchResult
from app.schemas.student import StudentAnswerEntry


class NoMatchRouter:
    """Stands in for the LLM content-matching stage, finding nothing.

    Using this asserts the deterministic path alone got the mapping right — anything
    it fails to match shows up as unmatched rather than being quietly rescued.
    """

    def __init__(self):
        self.called = False

    async def generate(self, *args, **kwargs):
        self.called = True
        return LLMMatchResult(pairs=[])


TWO_SECTION_PAPER = TeacherDocument(
    sections=[
        Section(
            id="a",
            title="Section A",
            questions=[
                Question(label="1", question_text="Define osmosis", max_marks=5, model_answer="..."),
                Question(label="2", question_text="Define diffusion", max_marks=5, model_answer="..."),
            ],
        ),
        Section(
            id="b",
            title="Section B",
            questions=[
                Question(label="1", question_text="Explain photosynthesis", max_marks=10, model_answer="..."),
                Question(label="2", question_text="Explain respiration", max_marks=10, model_answer="..."),
            ],
        ),
    ]
)


def _map(units, entries, router=None):
    return asyncio.run(HybridQuestionMapper(router or NoMatchRouter()).map(units, entries))


def test_labels_repeated_across_sections_map_in_written_order():
    units = flatten_to_units(TWO_SECTION_PAPER)
    entries = [
        StudentAnswerEntry(raw_label="1", answer_text="osmosis is..."),
        StudentAnswerEntry(raw_label="2", answer_text="diffusion is..."),
        StudentAnswerEntry(raw_label="1", answer_text="photosynthesis is..."),
        StudentAnswerEntry(raw_label="2", answer_text="respiration is..."),
    ]

    mapped = _map(units, entries)

    by_path = {"/".join(m.unit.path): m for m in mapped}
    assert by_path["Section A/1"].student_entry.answer_text == "osmosis is..."
    assert by_path["Section A/2"].student_entry.answer_text == "diffusion is..."
    assert by_path["Section B/1"].student_entry.answer_text == "photosynthesis is..."
    assert by_path["Section B/2"].student_entry.answer_text == "respiration is..."
    assert all(m.match_method == "deterministic" for m in mapped)


def test_no_answer_is_silently_graded_against_the_wrong_section():
    """The dangerous half of the old bug: Section B graded using Section A's text."""
    units = flatten_to_units(TWO_SECTION_PAPER)
    entries = [
        StudentAnswerEntry(raw_label="1", answer_text="osmosis is..."),
        StudentAnswerEntry(raw_label="2", answer_text="diffusion is..."),
    ]

    mapped = _map(units, entries)
    by_path = {"/".join(m.unit.path): m for m in mapped}

    # Only Section A was answered; Section B must not inherit those answers.
    assert by_path["Section B/1"].student_entry is None
    assert by_path["Section B/2"].student_entry is None


def test_ambiguous_counts_defer_to_content_matching_instead_of_guessing():
    units = flatten_to_units(TWO_SECTION_PAPER)
    # One answer labelled "1" but two questions numbered "1" — genuinely ambiguous.
    entries = [StudentAnswerEntry(raw_label="1", answer_text="photosynthesis is...")]
    router = NoMatchRouter()

    _map(units, entries, router)

    assert router.called, "ambiguous label should be handed to the LLM content matcher"


def test_unique_labels_still_match_deterministically():
    doc = TeacherDocument(
        sections=[
            Section(
                id="a",
                title="Questions",
                questions=[
                    Question(label="1", question_text="Q1", max_marks=5, model_answer="..."),
                    Question(label="2", question_text="Q2", max_marks=5, model_answer="..."),
                ],
            )
        ]
    )
    units = flatten_to_units(doc)
    entries = [
        StudentAnswerEntry(raw_label="Q.2", answer_text="second"),
        StudentAnswerEntry(raw_label="1)", answer_text="first"),
    ]
    router = NoMatchRouter()

    mapped = _map(units, entries, router)

    assert [m.student_entry.answer_text for m in mapped] == ["first", "second"]
    assert not router.called, "unambiguous labels should never need the LLM"


def test_normalize_label_variants():
    assert {normalize_label(s) for s in ("Q2(b)", "2.b", "2 b", "Q.2.b")} == {"2b"}


def test_teacher_q_prefix_matches_student_bare_number():
    """Answer keys write "Q1"; students write "1". These must match without an LLM."""
    doc = TeacherDocument(
        sections=[
            Section(
                id="a",
                title="Questions",
                questions=[
                    Question(label="Q1", question_text="First", max_marks=5, model_answer="..."),
                    Question(label="Q2", question_text="Second", max_marks=5, model_answer="..."),
                ],
            )
        ]
    )
    router = NoMatchRouter()
    mapped = _map(
        flatten_to_units(doc),
        [
            StudentAnswerEntry(raw_label="1", answer_text="first"),
            StudentAnswerEntry(raw_label="2.", answer_text="second"),
        ],
        router,
    )

    assert [m.student_entry.answer_text for m in mapped] == ["first", "second"]
    assert not router.called
