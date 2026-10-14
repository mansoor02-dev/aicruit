"""Application composition and service lifecycle."""

import csv
import logging
from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncIterator

from fastapi import FastAPI

from app.api.routes import router
from app.pipelines.orchestrator import InterviewOrchestrator
from app.services.answer_evaluator import AnswerEvaluator
from app.services.embedding import get_embedder
from app.services.llm_client import LLMClient
from app.services.question_generator import QuestionGenerator

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    logger.info("Initialising interview service")

    llm_client = LLMClient()
    dataset_path = (
        Path(__file__).resolve().parents[1] / "data" / "software_questions.csv"
    )
    with dataset_path.open(newline="", encoding="latin1") as dataset_file:
        dataset = list(csv.DictReader(dataset_file))
    logger.info("Dataset loaded: %s questions", len(dataset))

    evaluator = AnswerEvaluator(embedder=get_embedder(), llm_client=llm_client)
    question_generator = QuestionGenerator(
        dataset_questions=dataset,
        llm_client=llm_client,
    )
    app.state.llm_client = llm_client
    app.state.orchestrator = InterviewOrchestrator(
        evaluator=evaluator,
        question_generator=question_generator,
    )
    logger.info("Interview service ready")

    yield

    logger.info("Shutting down interview service")


app = FastAPI(title="Interview Question Generation API", lifespan=lifespan)
app.include_router(router)
