"""
FastAPI endpoint for the interview question generation service.
HTTP concerns only — all orchestration is delegated to InterviewOrchestrator.
"""
import csv
import logging
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from sentence_transformers import SentenceTransformer

import sys
sys.path.append(str(Path(__file__).parent.parent))

from pipelines.answer_evaluator import AnswerEvaluator
from pipelines.llm_loader import LLMLoader
from pipelines.orchestrator import InterviewOrchestrator
from pipelines.question_generator import QuestionGenerator

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Module-level singletons (populated during lifespan startup)
orchestrator: Optional[InterviewOrchestrator] = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global orchestrator

    logger.info("Initialising interview service…")

    llm = LLMLoader(model_type="openrouter").get_llm()
    logger.info("LLM loaded")

    embedder = SentenceTransformer("all-MiniLM-L6-v2", device="cpu")
    logger.info("Embedder loaded")

    dataset_path = Path("data/software_questions.csv")
    with open(dataset_path, newline="", encoding="latin1") as f:
        dataset = list(csv.DictReader(f))
    logger.info(f"Dataset loaded: {len(dataset)} questions")

    evaluator = AnswerEvaluator(embedder=embedder, model_type="openrouter")
    question_generator = QuestionGenerator(dataset_questions=dataset, model_type="openrouter")

    orchestrator = InterviewOrchestrator(
        evaluator=evaluator,
        question_generator=question_generator,
    )
    logger.info("Interview service ready")

    yield

    logger.info("Shutting down interview service…")


app = FastAPI(title="Interview Question Generation API", lifespan=lifespan)


# ------------------------------------------------------------------
# Request / Response schemas
# ------------------------------------------------------------------

class QA(BaseModel):
    Q: str
    A: str


class QuestionRequest(BaseModel):
    resume_json: Optional[Dict[str, Any]] = None
    previous_qa: Optional[List[QA]] = []
    difficulty: str = "medium"


# ------------------------------------------------------------------
# Endpoints
# ------------------------------------------------------------------

@app.post("/next-question")
async def get_next_question(req: QuestionRequest):
    """
    Generate the next interview question.

    Returns:
        {
            "question": str,
            "metadata": {
                "category": str,
                "difficulty": str,
                "is_followup": bool,
                "evaluation": {...},   # present when a follow-up is generated
                ...
            }
        }
    """
    try:
        previous_qa_list = (
            [{"Q": qa.Q, "A": qa.A} for qa in req.previous_qa]
            if req.previous_qa
            else None
        )

        logger.info(
            f"Generating question: history_length={len(previous_qa_list or [])}, "
            f"difficulty={req.difficulty}"
        )

        question, metadata = orchestrator.generate_next_question(
            resume_json=req.resume_json or {},
            previous_qa_list=previous_qa_list,
            difficulty=req.difficulty,
        )

        logger.info(
            f"Generated: category={metadata.get('category')}, "
            f"is_followup={metadata.get('is_followup')}"
        )

        return {"question": question, "metadata": metadata}

    except Exception as e:
        logger.error(f"Error generating question: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/health")
async def health():
    return {"status": "ok", "service": "interview-question-generation"}


# if __name__ == "__main__":
#     import uvicorn
#     uvicorn.run(app, host="localhost", port=8010)