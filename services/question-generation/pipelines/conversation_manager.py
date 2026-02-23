from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, List, Optional


@dataclass
class Turn:
    """A single Q&A exchange in the interview."""
    question: str
    answer: str
    evaluation: Dict
    is_followup: bool
    topic: Optional[str] = None
    question_metadata: Optional[Dict] = None
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class ConversationManager:
    """
    Tracks interview state: question history, topic progression, and scoring.
    """

    _DIFFICULTY_POINTS = {"easy": 1.0, "medium": 2.0, "hard": 3.0}

    def __init__(self, total_questions: int = 3):
        self.total_questions = total_questions
        self.history: List[Turn] = []
        self.current_topic: Optional[str] = None
        self.topic_depth: int = 0           # follow-ups on the current topic
        self._topics_covered: List[str] = []
        self.total_points: float = 0.0
        self.max_possible: float = 0.0

    # ------------------------------------------------------------------
    # Mutation
    # ------------------------------------------------------------------

    def add_turn(
        self,
        question: str,
        answer: str,
        evaluation: Dict,
        is_followup: bool,
        topic: Optional[str] = None,
        metadata: Optional[Dict] = None,
    ) -> None:
        turn = Turn(
            question=question,
            answer=answer,
            evaluation=evaluation,
            is_followup=is_followup,
            topic=topic or self.current_topic,
            question_metadata=metadata,
        )
        self.history.append(turn)

        if not is_followup:
            if topic and topic != self.current_topic:
                if self.current_topic:
                    self._topics_covered.append(self.current_topic)
                self.current_topic = topic
            self.topic_depth = 0
        else:
            self.topic_depth += 1

        if metadata:
            difficulty = metadata.get("difficulty", "medium")
            points_possible = self._DIFFICULTY_POINTS.get(difficulty, 2.0)
            self.total_points += points_possible * evaluation.get("depth_score", 0.0)
            self.max_possible += points_possible

    # ------------------------------------------------------------------
    # Read-only state queries
    # ------------------------------------------------------------------

    def is_complete(self) -> bool:
        return self.get_questions_asked() >= self.total_questions

    def get_questions_asked(self) -> int:
        return sum(1 for t in self.history if not t.is_followup)

    def get_total_turns(self) -> int:
        return len(self.history)

    def get_last_turn(self) -> Optional[Turn]:
        return self.history[-1] if self.history else None

    def get_last_n_turns(self, n: int) -> List[Turn]:
        return self.history[-n:]

    def get_current_topic_depth(self) -> int:
        return self.topic_depth

    def get_topics_covered_list(self) -> List[str]:
        covered = list(self._topics_covered)
        if self.current_topic and self.current_topic not in covered:
            covered.append(self.current_topic)
        return covered

    def get_performance_summary(self) -> Dict:
        if not self.history:
            return {
                "questions_asked": 0, "total_turns": 0,
                "passed": 0, "failed": 0,
                "score": 0.0, "max_score": 0.0, "percentage": 0.0,
                "average_depth": 0.0, "topics_covered": 0,
            }

        passed = sum(1 for t in self.history if t.evaluation.get("pass", False))
        avg_depth = sum(t.evaluation.get("depth_score", 0) for t in self.history) / len(self.history)
        percentage = (self.total_points / self.max_possible * 100) if self.max_possible else 0.0

        return {
            "questions_asked": self.get_questions_asked(),
            "total_turns": self.get_total_turns(),
            "passed": passed,
            "failed": len(self.history) - passed,
            "score": round(self.total_points, 2),
            "max_score": round(self.max_possible, 2),
            "percentage": round(percentage, 1),
            "average_depth": round(avg_depth, 3),
            "topics_covered": len(self.get_topics_covered_list()),
        }

    def get_conversation_summary(self, last_n: int = 3) -> str:
        """Plain-text summary of the last N turns (used for LLM context)."""
        if not self.history:
            return "Interview just started — no history yet."

        lines = []
        for i, turn in enumerate(self.get_last_n_turns(last_n), 1):
            marker = "[FOLLOW-UP]" if turn.is_followup else "[NEW TOPIC]"
            depth = turn.evaluation.get("depth_score", 0)
            status = "✓" if turn.evaluation.get("pass", False) else "✗"
            lines += [
                f"{marker} Q{i}: {turn.question[:60]}...",
                f"  A{i}: {turn.answer[:60]}...",
                f"  Score: {status} {depth:.2f}\n",
            ]

        return "\n".join(lines)

    def to_dict(self) -> Dict:
        return {
            "session_metadata": {
                "total_questions_target": self.total_questions,
                "questions_asked": self.get_questions_asked(),
                "total_turns": self.get_total_turns(),
                "topics_covered": self.get_topics_covered_list(),
                "score": round(self.total_points, 3),
                "max_score": round(self.max_possible, 3),
            },
            "conversation_history": [
                {
                    "turn_number": i + 1,
                    "timestamp": t.timestamp,
                    "is_followup": t.is_followup,
                    "topic": t.topic,
                    "question": t.question,
                    "answer": t.answer,
                    "evaluation": t.evaluation,
                    "metadata": t.question_metadata,
                }
                for i, t in enumerate(self.history)
            ],
            "performance": self.get_performance_summary(),
        }

    def print_summary(self) -> None:
        perf = self.get_performance_summary()
        print("\n" + "=" * 60)
        print("   INTERVIEW SUMMARY")
        print("=" * 60)
        print(f"\nQuestions Asked:          {perf['questions_asked']}/{self.total_questions}")
        print(f"Total Turns (w/ follow-ups): {perf['total_turns']}")
        print(f"Passed: {perf['passed']} | Failed: {perf['failed']}")
        print(f"Score:  {perf['score']:.1f}/{perf['max_score']:.1f} ({perf['percentage']}%)")
        print(f"Avg Depth: {perf['average_depth']:.2f}")
        print(f"Topics Covered: {perf['topics_covered']}")
        if self.get_topics_covered_list():
            print(f"\nTopics: {', '.join(self.get_topics_covered_list())}")
        print("=" * 60 + "\n")