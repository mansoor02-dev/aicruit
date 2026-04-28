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


import sys
sys.path.insert(0, "/app")
sys.path.append(str(Path(__file__).parent.parent))

from shared.llm_client import LLMClient
from shared.embedding_provider import get_provider
from pipelines.answer_evaluator import AnswerEvaluator
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

    # LLM and embedder are now lazy-loaded from shared/ on first use
    logger.info("Shared LLM and embedding providers configured")

    dataset_path = Path("data/software_questions.csv")
    with open(dataset_path, newline="", encoding="latin1") as f:
        dataset = list(csv.DictReader(f))
    logger.info(f"Dataset loaded: {len(dataset)} questions")

    evaluator = AnswerEvaluator(embedder=get_provider())
    question_generator = QuestionGenerator(dataset_questions=dataset)

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


class PoolQuestion(BaseModel):
    question: str
    topic: Optional[str] = None


class QuestionRequest(BaseModel):
    resume_json: Optional[Dict[str | None, Any]] = None
    previous_qa: Optional[List[QA]] = []
    difficulty: str = "medium"
    category: Optional[str] = None
    question_pool: Optional[List[PoolQuestion]] = None
    used_pool_questions: Optional[List[str]] = None


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
            f"difficulty={req.difficulty}, category={req.category}, "
            f"pool_size={len(req.question_pool or [])}"
        )

        # If a recruiter-uploaded pool exists, prefer picking from it.
        if req.question_pool:
            used = set(req.used_pool_questions or [])
            target_topic = (req.category or "").strip().lower()

            def _topic_match(q: PoolQuestion) -> bool:
                if not target_topic:
                    return True
                t = (q.topic or "").strip().lower()
                return t == target_topic

            unused = [q for q in req.question_pool if q.question not in used]
            preferred = [q for q in unused if _topic_match(q)]

            chosen = None
            if preferred:
                chosen = preferred[0]
            elif unused:
                chosen = unused[0]

            if chosen is not None:
                metadata = {
                    "source": "recruiter_pool",
                    "scenario": "new_question",
                    "question_id": None,
                    "category": chosen.topic or req.category or "Unknown",
                    "difficulty": req.difficulty,
                    "reference_answer": "",
                    "is_followup": False,
                    "evaluation": {},
                }
                # Still evaluate prior answer if there is history, to populate scores
                if previous_qa_list:
                    last_qa = previous_qa_list[-1]
                    try:
                        evaluation, flow = orchestrator.evaluator.evaluate_combined(
                            question=last_qa["Q"],
                            user_answer=last_qa["A"],
                            reference_answer=last_qa.get("reference_answer"),
                            is_followup=last_qa.get("is_followup", False),
                        )
                        metadata["evaluation"] = {
                            "decision":   flow.get("decision"),
                            "score":      flow.get("score_value"),
                            "confidence": evaluation.get("confidence"),
                            "remarks":    flow.get("remarks"),
                            "feedback":   evaluation.get("feedback"),
                        }
                    except Exception as eval_exc:
                        logger.warning(f"Pool path evaluator failed: {eval_exc}")
                return {"question": chosen.question, "metadata": metadata}

        question, metadata = orchestrator.generate_next_question(
            resume_json=req.resume_json or {},
            previous_qa_list=previous_qa_list,
            difficulty=req.difficulty,
            category=req.category,
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