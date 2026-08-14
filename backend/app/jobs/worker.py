import asyncio
import logging

from app.db import session_factory as get_session_factory
from app.models.submission import GradingJob, QuestionResult, Submission
from app.pipeline.orchestrator import GradingOrchestrator

logger = logging.getLogger(__name__)


async def run_worker(worker_id: int, queue: asyncio.Queue[str], orchestrator: GradingOrchestrator) -> None:
    session_factory = get_session_factory()
    while True:
        job_id = await queue.get()
        try:
            await _process_job(job_id, orchestrator, session_factory)
        except Exception:
            logger.exception("worker %s: unhandled error processing job %s", worker_id, job_id)
        finally:
            queue.task_done()


async def _process_job(job_id: str, orchestrator: GradingOrchestrator, session_factory) -> None:
    async with session_factory() as session:
        job = await session.get(GradingJob, job_id)
        if job is None:
            logger.error("job %s not found, skipping", job_id)
            return
        submission = await session.get(Submission, job.submission_id)
        if submission is None:
            job.status = "failed"
            job.error_message = "submission record missing"
            await session.commit()
            return

        job.status = "running"
        submission.status = "running"
        await session.commit()

        async def on_stage(stage: str) -> None:
            job.current_stage = stage
            await session.commit()

        try:
            teacher_doc, result = await orchestrator.run(
                submission.teacher_file_paths, submission.student_file_paths, on_stage
            )
        except Exception as e:
            # Total-stage failure: raised loudly by the pipeline, surfaced here as a
            # visible failed job rather than a silent/meaningless zero score.
            logger.error("job %s failed: %s", job_id, e)
            job.status = "failed"
            job.error_message = str(e)
            job.current_stage = None
            submission.status = "failed"
            await session.commit()
            return

        submission.teacher_document_json = teacher_doc.model_dump()
        submission.overview_json = result.overview.model_dump()
        submission.handwriting_confidence = result.handwriting_confidence
        submission.total_score = result.total_score
        submission.max_score = result.max_score
        submission.grade_letter = result.grade_letter
        submission.status = "done"

        for r in result.results:
            session.add(
                QuestionResult(
                    submission_id=submission.id,
                    unit_id=r.unit_id,
                    path_json=r.path,
                    label=r.label,
                    question_text=r.question_text,
                    model_answer=r.model_answer,
                    student_answer=r.student_answer,
                    attempted=r.attempted,
                    max_marks=r.max_marks,
                    similarity_score=r.similarity_score,
                    llm_score_pct=r.llm_score_pct,
                    final_score=r.final_score,
                    feedback=r.feedback,
                    counted_toward_total=r.counted_toward_total,
                    has_diagram=r.has_diagram,
                    has_table=r.has_table,
                    has_code=r.has_code,
                )
            )

        job.status = "done"
        job.current_stage = None
        await session.commit()
