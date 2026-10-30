"""Regression test for the exam/submission split: parse_answer_key() is called once
(from exam creation) and grade_submission() must reuse that already-parsed
TeacherDocument rather than re-parsing the answer key for every student submission.
Before this split, orchestrator.run() always called parse_teacher() itself, which
would mean an LLM OCR call on the identical answer key for every student in a class.
"""
import asyncio

from app.pipeline.orchestrator import GradingOrchestrator
from app.schemas.document import Question, Section, TeacherDocument
from app.schemas.grading import OverviewSummary, QuestionGradeResult
from app.schemas.mapping import MappedAnswer
from app.schemas.student import ParsedStudentDocument, StudentAnswerEntry

TEACHER_DOC = TeacherDocument(
    sections=[
        Section(
            id="s1",
            title="Questions",
            questions=[Question(label="1", question_text="Q1?", max_marks=5.0, model_answer="ref")],
        )
    ]
)


class FakeOCRParser:
    def __init__(self):
        self.parse_teacher_calls = 0
        self.parse_student_calls = 0

    async def parse_teacher(self, file_paths):
        self.parse_teacher_calls += 1
        return TEACHER_DOC

    async def parse_student(self, file_paths, teacher_doc):
        self.parse_student_calls += 1
        return ParsedStudentDocument(
            entries=[StudentAnswerEntry(raw_label="1", answer_text="student answer")],
            handwriting_confidence=0.9,
        )


class FakeMapper:
    async def map(self, units, entries):
        return [MappedAnswer(unit=units[0], student_entry=entries[0], match_method="deterministic")]


class FakeGrader:
    async def grade(self, mapped):
        results = [
            QuestionGradeResult(
                unit_id=mapped[0].unit.unit_id,
                path=mapped[0].unit.path,
                label=mapped[0].unit.label,
                question_text=mapped[0].unit.question_text,
                model_answer=mapped[0].unit.model_answer,
                student_answer="student answer",
                attempted=True,
                max_marks=mapped[0].unit.max_marks,
                final_score=5.0,
                feedback="great",
            )
        ]
        return results, OverviewSummary(strengths=[], watch_for=[])


async def _noop_stage(stage: str) -> None:
    pass


def test_grade_submission_does_not_reparse_the_answer_key():
    ocr = FakeOCRParser()
    orchestrator = GradingOrchestrator(ocr_parser=ocr, mapper=FakeMapper(), grader=FakeGrader())

    teacher_doc = asyncio.run(orchestrator.parse_answer_key(["answer_key.pdf"]))
    assert ocr.parse_teacher_calls == 1

    result = asyncio.run(orchestrator.grade_submission(teacher_doc, ["student1.pdf"], _noop_stage))
    result2 = asyncio.run(orchestrator.grade_submission(teacher_doc, ["student2.pdf"], _noop_stage))

    # Two students graded, but the answer key was only ever parsed the one time above.
    assert ocr.parse_teacher_calls == 1
    assert ocr.parse_student_calls == 2
    assert result.total_score == result2.total_score == 5.0
