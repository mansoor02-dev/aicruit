"""
FastAPI endpoint for the interview question generation service.

This layer handles HTTP concerns only.
All orchestration logic is delegated to InterviewOrchestrator.
"""
import logging
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from pathlib import Path
import csv
from sentence_transformers import SentenceTransformer
from contextlib import asynccontextmanager

import sys
sys.path.append(str(Path(__file__).parent.parent))

from pipelines.llm_loader import LLMLoader
from pipelines.question_generator import QuestionGenerator
from pipelines.answer_evaluator import AnswerEvaluator
from pipelines.orchestrator import InterviewOrchestrator

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

llm = None
embedder = None
evaluator = None
question_generator = None
orchestrator = None
dataset = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager for startup and shutdown"""
    global llm, embedder, evaluator, question_generator, orchestrator, dataset
    
    logger.info("Initializing interview service...")
    
    try:
        llm = LLMLoader(model_type="openrouter").get_llm()
        logger.info("LLM loaded")
        
        embedder = SentenceTransformer("all-MiniLM-L6-v2", device='cpu')
        logger.info("Embedder loaded")
        
        evaluator = AnswerEvaluator(embedder, llm)
        logger.info("Evaluator initialized")
        
        dataset_path = Path("data/software_questions.csv")
        with open(dataset_path) as f:
            dataset = list(csv.DictReader(f))
        logger.info(f"Dataset loaded: {len(dataset)} questions")
        
        question_generator = QuestionGenerator(
            dataset_questions=dataset,
            model_type="openrouter",
            candidate_resume="",
            difficulty="medium"
        )
        logger.info("Question generator initialized")
        
        orchestrator = InterviewOrchestrator(
            evaluator=evaluator,
            flow_controller=None,
            question_generator=question_generator
        )
        logger.info("Orchestrator initialized")
        
        logger.info("Interview service ready")
    
    except Exception as e:
        logger.error(f"Startup failed: {e}", exc_info=True)
        raise
    
    yield
    
    logger.info("Shutting down interview service...")


app = FastAPI(title="Interview Question Generation API", lifespan=lifespan)


class QA(BaseModel):
    """Single Q&A pair"""
    Q: str
    A: str


class QuestionRequest(BaseModel):
    """Request to generate next question"""
    resume_json: Optional[Dict[str, Any]] = None
    previous_qa: Optional[List[QA]] = []
    difficulty: str = "medium"


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
                "evaluation": {...} (if followup),
                ...
            }
        }
    """
    try:
        logger.info(
            f"Generating question: history_length={len(req.previous_qa or [])}, "
            f"difficulty={req.difficulty}"
        )
        
        previous_qa_list = None
        if req.previous_qa:
            previous_qa_list = [{"Q": qa.Q, "A": qa.A} for qa in req.previous_qa]
        
        question, metadata = orchestrator.generate_next_question(
            resume_json=req.resume_json or {},
            previous_qa_list=previous_qa_list,
            difficulty=req.difficulty
        )
        
        logger.info(
            f"Generated question: category={metadata.get('category')}, "
            f"is_followup={metadata.get('is_followup')}"
        )
        
        return {
            "question": question,
            "metadata": metadata
        }
    
    except Exception as e:
        logger.error(f"Error generating question: {e}", exc_info=True)
        raise HTTPException(500, f"Error: {str(e)}")


@app.get("/health")
async def health():
    """Health check endpoint"""
    return {
        "status": "ok",
        "service": "interview-question-generation"
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="localhost", port=8008, reload=True)