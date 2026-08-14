"""Stage: OCR + structural parsing of both the teacher's answer key and the
student's handwritten sheet. Cloud vision models only (see model_registry.yaml) —
handwriting OCR quality is the single highest-priority accuracy requirement in
this project, local vision models are a last resort, not a peer option.
"""
from abc import ABC, abstractmethod

from app.routing.base import Capability
from app.routing.registry import ModelRouter, RouterExhaustedError
from app.schemas.document import TeacherDocument
from app.schemas.student import ParsedStudentDocument

TEACHER_OCR_PROMPT = """\
You are reading a teacher's answer key / question paper (may be typed or handwritten,
may span multiple pages given as images in order). Extract its full structure:

- Sections (e.g. "Section A", "Part 2") if present. If the paper has no explicit
  sections, put everything in a single section titled "Questions".
- If a section says something like "Attempt any N of M questions", set its
  selection_rule to {type: "attempt_n_of_m", n: N}. Otherwise leave it null.
- Every question: its label (as written, e.g. "1", "Q7"), full question text,
  max marks allocated, and the model/reference answer.
- Subparts (a), (b), (c) etc: extract each as its own subpart with its own marks
  and model answer. If a question has subparts, leave the parent question's
  model_answer null (marks and answer live on the subparts instead).
- MCQs: set is_mcq true, capture mcq_options and mcq_correct.
- Flag has_diagram / has_table / has_code true wherever the *reference answer*
  itself includes one (used later to give students credit for including their own).

Return ONLY the structured data — do not invent questions that aren't on the page.
"""

STUDENT_OCR_PROMPT = """\
You are reading a student's handwritten answer sheet (images given in page order).
You are given the teacher's already-extracted question list below as context, ONLY
to help you recognize what a given answer is likely responding to — do not force-fit
structure the student didn't write.

Teacher's questions (for context only):
{teacher_context}

For each answer you find on the sheet, extract one entry:
- raw_label: the question number/label EXACTLY as the student wrote it (or as best
  you can make out) — do not normalize or correct it. Empty string if illegible/missing.
- answer_text: the transcribed handwritten answer, as faithfully as possible.
- attempted: false only if the question is clearly listed/numbered but left blank.
- has_diagram / has_table / has_code: true if the student included one for that answer.

If a page or portion is genuinely illegible, transcribe what you can and note
"[ILLEGIBLE]" inline for the parts you cannot read — do not fabricate content.
Also return handwriting_confidence (0-1): your own estimate of how legible the
handwriting was overall.
"""


class OCRParser(ABC):
    @abstractmethod
    async def parse_teacher(self, file_paths: list[str]) -> TeacherDocument: ...

    @abstractmethod
    async def parse_student(self, file_paths: list[str], teacher_doc: TeacherDocument) -> ParsedStudentDocument: ...


class LLMOCRParser(OCRParser):
    def __init__(self, router: ModelRouter, load_images):
        self._router = router
        self._load_images = load_images  # injected for testability

    async def parse_teacher(self, file_paths: list[str]) -> TeacherDocument:
        images = self._load_images(file_paths)
        try:
            result = await self._router.generate(
                Capability.VISION, TEACHER_OCR_PROMPT, images, TeacherDocument
            )
        except RouterExhaustedError as e:
            raise RuntimeError(f"Teacher answer-key OCR failed completely: {e}") from e
        return result  # type: ignore[return-value]

    async def parse_student(self, file_paths: list[str], teacher_doc: TeacherDocument) -> ParsedStudentDocument:
        images = self._load_images(file_paths)
        context_lines = [
            f"- {q.label}: {q.question_text[:120]}"
            for section in teacher_doc.sections
            for q in section.questions
        ]
        prompt = STUDENT_OCR_PROMPT.format(teacher_context="\n".join(context_lines))
        try:
            result = await self._router.generate(Capability.VISION, prompt, images, ParsedStudentDocument)
        except RouterExhaustedError as e:
            raise RuntimeError(f"Student sheet OCR failed completely: {e}") from e
        return result  # type: ignore[return-value]
