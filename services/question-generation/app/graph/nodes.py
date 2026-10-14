from typing import Any

from app.services.answer_evaluator import AnswerEvaluator
from app.services.question_generator import QuestionGenerator

from .state import QuestionGraphState


class QuestionGraphNodes:
    def __init__(
        self,
        evaluator: AnswerEvaluator,
        question_generator: QuestionGenerator,
    ):
        self.evaluator = evaluator
        self.question_generator = question_generator

    async def evaluate_answer(self, state: QuestionGraphState) -> dict[str, Any]:
        last_qa = self._last_qa(state)
        evaluation, flow = await self.evaluator.evaluate_combined(
            question=last_qa["Q"],
            user_answer=last_qa["A"],
            reference_answer=last_qa.get("reference_answer"),
            is_followup=last_qa.get("is_followup", False),
        )
        return {"evaluation": evaluation, "flow": flow}

    def generate_introduction(self, state: QuestionGraphState) -> dict[str, Any]:
        question, metadata = self.question_generator.generate_introduction_question(
            resume_json=state.get("resume_json")
        )
        return {"question": question, "metadata": metadata}

    def generate_category_opener(
        self, state: QuestionGraphState
    ) -> dict[str, Any]:
        category = state.get("category")
        if not category:
            raise ValueError("Category-opener node requires a category")
        question, metadata = (
            self.question_generator.generate_category_opener_question(
                category=category
            )
        )
        return {"question": question, "metadata": metadata}

    async def generate_followup(self, state: QuestionGraphState) -> dict[str, Any]:
        last_qa = self._last_qa(state)
        question, metadata = await self.question_generator.generate_followup_question(
            previous_question=last_qa["Q"],
            previous_answer=last_qa["A"],
            evaluation_result=state.get("flow"),
            resume_json=state.get("resume_json"),
            difficulty=state.get("difficulty", "medium"),
            topic=state.get("category"),
        )
        metadata["evaluation"] = self._evaluation_metadata(state)
        return {"question": question, "metadata": metadata}

    async def generate_new_topic(self, state: QuestionGraphState) -> dict[str, Any]:
        question, metadata = (
            await self.question_generator.generate_new_topic_question(
                topics_covered=self._extract_topics(
                    state.get("previous_qa_list") or []
                ),
                difficulty=state.get("difficulty", "medium"),
                resume_json=state.get("resume_json"),
                category=state.get("category"),
            )
        )
        metadata["scenario"] = "question_with_same_category"
        metadata["evaluation"] = self._evaluation_metadata(state)
        return {"question": question, "metadata": metadata}

    @staticmethod
    def _last_qa(state: QuestionGraphState) -> dict[str, Any]:
        history = state.get("previous_qa_list")
        if not history:
            raise ValueError("Answer-processing node requires interview history")
        return history[-1]

    @staticmethod
    def _evaluation_metadata(state: QuestionGraphState) -> dict[str, Any]:
        evaluation = state.get("evaluation", {})
        flow = state.get("flow", {})
        return {
            "decision": flow.get("decision"),
            "score": flow.get("score_value"),
            "confidence": evaluation.get("confidence"),
            "remarks": flow.get("remarks"),
            "feedback": evaluation.get("feedback"),
        }

    @staticmethod
    def _extract_topics(previous_qa_list: list[dict[str, Any]]) -> list[str]:
        seen: set[str] = set()
        topics: list[str] = []
        for qa in previous_qa_list:
            topic = qa.get("category") or qa.get("topic")
            if topic and topic not in seen:
                seen.add(topic)
                topics.append(topic)
        return topics
