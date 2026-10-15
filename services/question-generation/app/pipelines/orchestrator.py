"""Compatibility facade for the LangGraph-based question flow."""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple


class InterviewOrchestrator:
    """Invokes the compiled question-generation graph."""

    def __init__(self, graph):
        self.graph = graph

    async def generate_next_question(
        self,
        resume_json: Optional[Dict] = None,
        previous_qa_list: Optional[List[Dict]] = None,
        difficulty: str = "medium",
        category: Optional[str] = None,
        pool: Optional[List[Dict[str, Any]]] = None,
        used_pool_questions: Optional[List[str]] = None,
    ) -> Tuple[str, Dict]:
        result = await self.graph.ainvoke(
            {
                "resume_json": resume_json or {},
                "previous_qa_list": previous_qa_list,
                "difficulty": difficulty,
                "category": category,
                "pool": pool or [],
                "used_pool_questions": used_pool_questions or [],
            }
        )
        return result["question"], result["metadata"]
