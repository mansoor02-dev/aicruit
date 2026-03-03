import random
from dataclasses import dataclass
from typing import Dict, List, Literal, Optional


@dataclass
class FlowDecision:
    """Decision about the next question type."""
    action: Literal["followup", "new_topic", "end"]
    reason: str
    suggested_angle: Optional[str] = None


class FlowController:
    """
    Determines interview progression using realistic interviewer logic.

    Real interviewers follow-up when the answer is vague/incomplete or the
    topic is worth drilling.  They move on when the answer is comprehensive or
    enough follow-ups have already been asked.
    """

    def __init__(
        self,
        max_followups_per_topic: int = 1,
        followup_probability_base: float = 0.6,
    ):
        self.max_followups = max_followups_per_topic
        self.base_followup_prob = followup_probability_base

    def decide_next_action(
        self,
        evaluation: Dict,
        topic_depth: int,
        total_questions: int,
        topics_covered: List[str],
        questions_asked: int = 0,
    ) -> FlowDecision:
        """
        Decide the next action based on the last evaluation and interview state.

        Args:
            evaluation:      Last answer evaluation {pass, depth_score, confidence, answer_length}.
            topic_depth:     Number of follow-ups already asked on the current topic.
            questions_asked: Total main (non-follow-up) questions asked so far.
            total_questions: Target number of main questions.
            topics_covered:  Topics already discussed.
        """
        # --- Terminal conditions ---
        if questions_asked >= total_questions:
            return FlowDecision(action="end", reason="Interview complete — all topics covered")

        # --- "I don't know" — skip elaboration, move to a new topic ---
        if (
            not evaluation.get("needs_followup", True)
            and evaluation.get("depth_score", 1.0) == 0.0
        ):
            return FlowDecision(
                action="new_topic",
                reason="Candidate unfamiliar with topic — moving on",
            )

        if topic_depth >= self.max_followups:
            return FlowDecision(
                action="new_topic",
                reason=f"Max follow-ups ({self.max_followups}) reached on this topic",
            )

        if questions_asked == 0:
            return FlowDecision(action="new_topic", reason="Starting interview with first question")

        # --- Extract signals ---
        passed = evaluation.get("pass", False)
        depth_score: float = evaluation.get("depth_score", 0.5)
        confidence: float = evaluation.get("confidence", 0.5)
        answer_length: int = evaluation.get("answer_length", 0)

        is_strong = passed and depth_score >= 0.7 and confidence >= 0.6 and answer_length >= 15
        is_weak = not passed or depth_score < 0.4 or answer_length < 10

        # --- Strong answer ---
        if is_strong:
            # Occasionally probe deeper even on a good answer (25% chance)
            if random.random() < 0.25:
                return FlowDecision(
                    action="followup",
                    reason="Good answer — probing deeper to test mastery",
                    suggested_angle="implementation_details",
                )
            return FlowDecision(action="new_topic", reason="Comprehensive answer — moving on")

        # --- Weak answer ---
        if is_weak:
            angle = "elaboration" if answer_length < 10 else ("clarification" if depth_score < 0.4 else "examples")
            return FlowDecision(
                action="followup",
                reason=f"Incomplete/unclear answer (depth: {depth_score:.2f})",
                suggested_angle=angle,
            )

        # --- Medium answer: probabilistic ---
        prob = self.base_followup_prob
        prob += (0.7 - depth_score) * 0.3          # lower score → higher follow-up chance
        prob -= topic_depth * 0.15                  # penalise repeated follow-ups
        if questions_asked / total_questions > 0.7:  # near end → prefer moving on
            prob -= 0.2

        if random.random() < prob:
            return FlowDecision(
                action="followup",
                reason=f"Moderate answer — probing for depth (score: {depth_score:.2f})",
                suggested_angle="tradeoffs",
            )

        return FlowDecision(action="new_topic", reason="Moderate answer acceptable — moving on")