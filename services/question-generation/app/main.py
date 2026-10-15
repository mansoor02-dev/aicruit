"""Application composition and service lifecycle."""

import logging
import random
from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncIterator

from fastapi import FastAPI

from app.api.routes import router
from app.config import Settings
from app.graph.builder import Dependencies, build_question_graph
from app.llm.chains import build_chains
from app.llm.embeddings import EmbeddingProvider
from app.llm.models import make_chat_models
from app.pipelines.orchestrator import InterviewOrchestrator
from app.services.dataset import DatasetRepository

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    logger.info("Initialising interview service")

    settings = Settings.from_env()
    models = make_chat_models(settings)
    # Embeddings stay lazy: no client is built and no network call is made
    # here, so OpenRouter-only deployments start cleanly.
    embeddings = EmbeddingProvider(settings)
    chains = build_chains(models, settings, embeddings)
    dataset_path = (
        Path(__file__).resolve().parents[1] / "data" / "software_questions.csv"
    )
    dataset = DatasetRepository.load_csv(dataset_path)
    graph = build_question_graph(
        Dependencies(
            chains=chains,
            dataset=dataset,
            settings=settings,
            rng=random.Random(),
        )
    )

    app.state.settings = settings
    app.state.models = models
    app.state.chains = chains
    app.state.dataset = dataset
    app.state.graph = graph
    app.state.orchestrator = InterviewOrchestrator(graph)
    logger.info("Interview service ready")

    yield

    logger.info("Shutting down interview service")


app = FastAPI(title="Interview Question Generation API", lifespan=lifespan)
app.include_router(router)
