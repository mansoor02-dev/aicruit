import logging
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


class InterviewOrchestrator:
    """
    Coordinates the interview loop:
    evaluates the last answer → decides flow → generates the next question.

    Uses evaluate_combined() to get scoring + flow decision in one LLM call.
    """

    def __init__(self, evaluator, question_generator, flow_controller=None):
        self.evaluator = evaluator
        self.generator = question_generator
        # flow_controller reserved for future use

    def generate_next_question(
        self,
        resume_json: Optional[Dict] = None,
        previous_qa_list: Optional[List[Dict]] = None,
        difficulty: str = "medium",
        category: Optional[str] = None,
    ) -> Tuple[str, Dict]:
        """
        Route to the correct generation strategy based on three scenarios:

        1. 1st_question   — no history, no category  → introduction question
        2. new_question   — no history, category set → fresh dataset question
        3. question_with_same_category
                          — history + category       → evaluate last answer,
                            then follow-up or new question within same category

        Returns:
            (question_text, metadata)
        """
        has_history = bool(previous_qa_list)
        has_category = bool(category)

        # ------------------------------------------------------------------
        # Scenario 1: 1st_question
        # ------------------------------------------------------------------
        if not has_history and not has_category:
            logger.info("Scenario: 1st_question — generating introduction question")
            return self.generator.generate_introduction_question(resume_json=resume_json)

        # ------------------------------------------------------------------
        # Scenario 2: new_question
        # ------------------------------------------------------------------
        if not has_history and has_category:
            logger.info(f"Scenario: new_question (category opener) — category={category}, difficulty={difficulty}")
            # Always start a category with a general easy question to warm the
            # candidate up.  Resume-contextual questions begin in scenario 3.
            return self.generator.generate_category_opener_question(
                category=category,
            )

        # ------------------------------------------------------------------
        # Scenario 3: question_with_same_category
        # ------------------------------------------------------------------
        logger.info(
            f"Scenario: question_with_same_category — category={category}, "
            f"history_length={len(previous_qa_list)}"
        )

        last_qa = previous_qa_list[-1]

        # Evaluate the last answer to decide follow-up vs. new question
        evaluation, flow = self.evaluator.evaluate_combined(
            question=last_qa["Q"],
            user_answer=last_qa["A"],
            reference_answer=last_qa.get("reference_answer"),
            is_followup=last_qa.get("is_followup", False),
        )

        decision = flow.get("decision", "new_topic")
        logger.info(
            f"Evaluation: decision={decision}, score={flow.get('score_value', 0):.2f}"
        )

        if decision in ("deep_dive", "same_topic"):
            question, metadata = self.generator.generate_followup_question(
                previous_question=last_qa["Q"],
                previous_answer=last_qa["A"],
                evaluation_result=flow,
                resume_json=resume_json,
                difficulty=difficulty,
                topic=category,
            )
        else:
            topics_covered = self._extract_topics(previous_qa_list)
            question, metadata = self.generator.generate_new_topic_question(
                topics_covered=topics_covered,
                difficulty=difficulty,
                resume_json=resume_json,
                category=category,  # always stay in the provided category
            )
            # Override scenario tag — still within same category session
            metadata["scenario"] = "question_with_same_category"

        metadata["evaluation"] = {
            "decision":   decision,
            "score":      flow.get("score_value"),
            "confidence": evaluation.get("confidence"),
            "remarks":    flow.get("remarks"),
            "feedback":   evaluation.get("feedback"),
        }
        return question, metadata

    @staticmethod
    def _extract_topics(previous_qa_list: List[Dict]) -> List[str]:
        """Pull distinct topic/category values from previous QA entries."""
        seen, topics = set(), []
        for qa in previous_qa_list:
            topic = qa.get("category") or qa.get("topic")
            if topic and topic not in seen:
                seen.add(topic)
                topics.append(topic)
        return topics