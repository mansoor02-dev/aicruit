"""Compatibility facade for the LangGraph-based question flow."""

from typing import Dict, List, Optional, Tuple

from app.graph.builder import build_question_graph
from app.services.answer_evaluator import AnswerEvaluator
from app.services.question_generator import QuestionGenerator


class InterviewOrchestrator:
    """Invokes the compiled question-generation graph."""

    def __init__(
        self,
        evaluator: AnswerEvaluator,
        question_generator: QuestionGenerator,
    ):
        self.evaluator = evaluator
        self.generator = question_generator
        self.graph = build_question_graph(evaluator, question_generator)

    async def generate_next_question(
        self,
        resume_json: Optional[Dict] = None,
        previous_qa_list: Optional[List[Dict]] = None,
        difficulty: str = "medium",
        category: Optional[str] = None,
    ) -> Tuple[str, Dict]:
        result = await self.graph.ainvoke(
            {
                "resume_json": resume_json or {},
                "previous_qa_list": previous_qa_list,
                "difficulty": difficulty,
                "category": category,
            }
        )
        return result["question"], result["metadata"]
