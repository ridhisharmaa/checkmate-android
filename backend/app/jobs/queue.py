"""In-process asyncio job queue — no Celery/Redis. A small worker pool started in
FastAPI's lifespan pulls job ids and runs the grading pipeline, writing progress to
the GradingJob row as it goes. Swappable for a real broker later without changing
the API contract (POST /submissions just enqueues an id, GET /jobs polls a row).
"""
import asyncio

from app.pipeline.orchestrator import GradingOrchestrator

_queue: asyncio.Queue[str] | None = None
_workers: list[asyncio.Task] = []


def get_queue() -> asyncio.Queue[str]:
    global _queue
    if _queue is None:
        _queue = asyncio.Queue()
    return _queue


async def enqueue(job_id: str) -> None:
    await get_queue().put(job_id)


def start_workers(count: int, orchestrator: GradingOrchestrator) -> None:
    from app.jobs.worker import run_worker

    queue = get_queue()
    for i in range(count):
        _workers.append(asyncio.create_task(run_worker(i, queue, orchestrator)))


async def stop_workers() -> None:
    for w in _workers:
        w.cancel()
    _workers.clear()
