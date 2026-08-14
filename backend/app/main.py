import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from sentence_transformers import SentenceTransformer

from app.api import jobs, submissions
from app.config import get_settings
from app.db import init_db
from app.jobs.queue import start_workers, stop_workers
from app.pipeline.answer_grader import LLMSemanticGrader
from app.pipeline.file_utils import load_pages_as_images
from app.pipeline.ocr_parser import LLMOCRParser
from app.pipeline.orchestrator import GradingOrchestrator
from app.pipeline.question_mapper import HybridQuestionMapper
from app.routing.registry import build_router

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

_TESTUI_DIR = Path(__file__).resolve().parent.parent / "devtools" / "testui"


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    await init_db()

    model_router = build_router(settings)
    # Loaded once at startup, not per-request — sentence-transformers model load is
    # a multi-second operation and the model is stateless/reusable across requests.
    similarity_model = SentenceTransformer("all-MiniLM-L6-v2")

    orchestrator = GradingOrchestrator(
        ocr_parser=LLMOCRParser(model_router, load_pages_as_images),
        mapper=HybridQuestionMapper(model_router),
        grader=LLMSemanticGrader(model_router, similarity_model),
    )
    app.state.orchestrator = orchestrator

    start_workers(settings.worker_count, orchestrator)
    logger.info("started %d grading worker(s)", settings.worker_count)

    yield

    await stop_workers()


app = FastAPI(title="CheckMate API", version="0.1.0", lifespan=lifespan)

app.include_router(submissions.router, tags=["submissions"])
app.include_router(jobs.router, tags=["jobs"])

if _TESTUI_DIR.exists():
    app.mount("/testui", StaticFiles(directory=str(_TESTUI_DIR), html=True), name="testui")


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
