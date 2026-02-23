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
    ) -> Tuple[str, Dict]:
        """
        Generate the next interview question.

        Args:
            resume_json:       Candidate resume (optional).
            previous_qa_list:  List of {"Q": ..., "A": ...} dicts.
            difficulty:        Desired difficulty for new-topic questions.

        Returns:
            (question_text, metadata)
        """
        if not previous_qa_list:
            logger.info("Generating first question")
            return self.generator.generate_new_topic_question(
                topics_covered=[], difficulty=difficulty, resume_json=resume_json
            )

        last_qa = previous_qa_list[-1]

        # Single LLM call → evaluation + flow decision
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
            )
        else:
            topics_covered = self._extract_topics(previous_qa_list)
            question, metadata = self.generator.generate_new_topic_question(
                topics_covered=topics_covered,
                difficulty=difficulty,
                resume_json=resume_json,
            )

        metadata["evaluation"] = {
            "decision":  decision,
            "score":     flow.get("score_value"),
            "remarks":   flow.get("remarks"),
            "feedback":  evaluation.get("feedback"),
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