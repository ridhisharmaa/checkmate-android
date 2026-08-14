"""Stage: grade every mapped answer. Local sentence-transformers similarity is
computed first (free, instant); one batched LLM call scores every question's
rubric fit plus writes the overall overview, then the two are combined:
final = 35% similarity + 65% LLM rubric score, plus a small bonus if the student
included a diagram/table/code where the reference answer also had one.

The LLM call falls back through the text chain (cloud first, Ollama last) since
this stage is text-only — a lower-tier local model is an acceptable last resort
here in a way it isn't for OCR.
"""
from abc import ABC, abstractmethod

from sentence_transformers import SentenceTransformer, util

from app.routing.base import Capability
from app.routing.registry import ModelRouter, RouterExhaustedError
from app.schemas.grading import LLMQuestionScore, OverviewSummary, QuestionGradeResult, ScoringCallResult
from app.schemas.mapping import MappedAnswer

SIMILARITY_WEIGHT = 0.35
LLM_WEIGHT = 0.65
DIAGRAM_BONUS_FRACTION = 0.05  # of max_marks, per matching diagram/table/code

SCORING_PROMPT = """\
Grade each student answer against its reference answer, semantically — different
wording that conveys the same meaning should score highly. Do not penalize for
phrasing, only for missing/incorrect content relative to the reference answer.
If an answer was not attempted, score 0 with feedback noting it wasn't attempted.

Questions:
{questions_block}

For each, return unit_id, score_percentage (0-100, how much of the reference
answer's content the student answer covers/matches), and brief specific feedback.

Also return an overall overview: 2-4 strengths and 2-4 watch_for points, written
about the submission as a whole (patterns across answers, not question-by-question).
"""


class AnswerGrader(ABC):
    @abstractmethod
    async def grade(self, mapped: list[MappedAnswer]) -> tuple[list[QuestionGradeResult], OverviewSummary]: ...


class LLMSemanticGrader(AnswerGrader):
    def __init__(self, router: ModelRouter, similarity_model: SentenceTransformer):
        self._router = router
        self._similarity_model = similarity_model

    def _similarity(self, a: str, b: str) -> float:
        if not a.strip() or not b.strip():
            return 0.0
        emb = self._similarity_model.encode([a, b], convert_to_tensor=True)
        return max(0.0, min(1.0, float(util.cos_sim(emb[0], emb[1]).item())))

    async def grade(self, mapped: list[MappedAnswer]) -> tuple[list[QuestionGradeResult], OverviewSummary]:
        similarities: dict[str, float] = {}
        for m in mapped:
            student_text = m.student_entry.answer_text if m.student_entry else ""
            similarities[m.unit.unit_id] = self._similarity(student_text, m.unit.model_answer)

        questions_block = "\n\n".join(
            f"unit_id={m.unit.unit_id}\n"
            f"reference answer: {m.unit.model_answer}\n"
            f"student answer: {m.student_entry.answer_text if m.student_entry else '[NOT ATTEMPTED]'}\n"
            f"max_marks: {m.unit.max_marks}"
            for m in mapped
        )
        prompt = SCORING_PROMPT.format(questions_block=questions_block)

        try:
            scoring: ScoringCallResult = await self._router.generate(  # type: ignore[assignment]
                Capability.TEXT, prompt, None, ScoringCallResult
            )
        except RouterExhaustedError as e:
            raise RuntimeError(f"Answer grading failed completely: {e}") from e

        llm_scores_by_unit: dict[str, LLMQuestionScore] = {s.unit_id: s for s in scoring.scores}

        results: list[QuestionGradeResult] = []
        for m in mapped:
            unit = m.unit
            sim = similarities[unit.unit_id]
            llm_score = llm_scores_by_unit.get(unit.unit_id)
            llm_pct = llm_score.score_percentage if llm_score else 0.0
            feedback = llm_score.feedback if llm_score else "Not attempted."

            attempted = m.student_entry is not None and m.student_entry.attempted
            base_fraction = (SIMILARITY_WEIGHT * sim + LLM_WEIGHT * (llm_pct / 100)) if attempted else 0.0

            bonus_fraction = 0.0
            if attempted and m.student_entry:
                for teacher_flag, student_flag in (
                    (unit.has_diagram, m.student_entry.has_diagram),
                    (unit.has_table, m.student_entry.has_table),
                    (unit.has_code, m.student_entry.has_code),
                ):
                    if teacher_flag and student_flag:
                        bonus_fraction += DIAGRAM_BONUS_FRACTION

            final_score = min(unit.max_marks, unit.max_marks * base_fraction + unit.max_marks * bonus_fraction)

            results.append(
                QuestionGradeResult(
                    unit_id=unit.unit_id,
                    path=unit.path,
                    label=unit.label,
                    question_text=unit.question_text,
                    model_answer=unit.model_answer,
                    student_answer=m.student_entry.answer_text if m.student_entry else None,
                    attempted=attempted,
                    max_marks=unit.max_marks,
                    similarity_score=sim if attempted else None,
                    llm_score_pct=llm_pct if attempted else None,
                    final_score=round(final_score, 2),
                    feedback=feedback,
                    has_diagram=unit.has_diagram,
                    has_table=unit.has_table,
                    has_code=unit.has_code,
                )
            )

        return results, scoring.overview
