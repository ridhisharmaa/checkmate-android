"""Wires the 4 pipeline stages together and reports real per-stage progress via an
injected callback — no client-side fake timer, the Android grading-progress screen
polls GET /jobs/{id} and this is what actually drives current_stage.

Stage names match the approved UI checklist (minus "uploading", which the caller/
worker marks complete before invoking this — file upload isn't part of the pipeline).
"""
from collections.abc import Awaitable, Callable

from app.pipeline.answer_grader import AnswerGrader
from app.pipeline.aggregator import aggregate
from app.pipeline.ocr_parser import OCRParser
from app.pipeline.question_mapper import QuestionMapper
from app.schemas.document import flatten_to_units
from app.schemas.document import TeacherDocument
from app.schemas.grading import SubmissionResult

STAGE_DETECTING_HANDWRITING = "detecting_handwriting"
STAGE_MATCHING = "matching_to_answer_key"
STAGE_GRADING = "grading_responses"
STAGE_SUMMARIZING = "generating_summary"

StageCallback = Callable[[str], Awaitable[None]]


class GradingOrchestrator:
    def __init__(self, ocr_parser: OCRParser, mapper: QuestionMapper, grader: AnswerGrader):
        self._ocr_parser = ocr_parser
        self._mapper = mapper
        self._grader = grader

    async def parse_answer_key(self, teacher_file_paths: list[str]) -> TeacherDocument:
        """Parses the teacher's answer key. Called once per exam (from the exam-creation
        endpoint), not once per student submission — OCR-ing the same answer key for
        every student in a class would be redundant LLM calls for identical input."""
        return await self._ocr_parser.parse_teacher(teacher_file_paths)

    async def grade_submission(
        self,
        teacher_doc: TeacherDocument,
        student_file_paths: list[str],
        on_stage: StageCallback,
    ) -> SubmissionResult:
        await on_stage(STAGE_DETECTING_HANDWRITING)
        student_doc = await self._ocr_parser.parse_student(student_file_paths, teacher_doc)

        await on_stage(STAGE_MATCHING)
        units = flatten_to_units(teacher_doc)
        mapped = await self._mapper.map(units, student_doc.entries)

        await on_stage(STAGE_GRADING)
        results, overview = await self._grader.grade(mapped)

        await on_stage(STAGE_SUMMARIZING)
        return aggregate(teacher_doc, results, overview, student_doc.handwriting_confidence)
