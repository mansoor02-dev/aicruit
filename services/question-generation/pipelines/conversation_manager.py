from typing import List, Dict, Optional
from dataclasses import dataclass, field
from datetime import datetime, timezone

@dataclass
class Turn:
    """Single Q&A turn in the conversation"""
    question: str
    answer: str
    evaluation: Dict  
    is_followup: bool
    topic: Optional[str] = None
    question_metadata: Optional[Dict] = None  # From question generator
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class ConversationManager:
    """
    Manages interview conversation state and flow
    
    Enhanced to track:
    - Main questions vs follow-ups
    - Topic depth and transitions
    - Performance metrics
    """
    
    def __init__(self, total_questions: int = 3):
        self.total_questions = total_questions
        self.history: List[Turn] = []
        self.current_topic: Optional[str] = None
        self.topic_depth = 0  # Follow-ups on current topic
        self.topics_covered = []
        
        # Performance tracking
        self.total_points = 0.0
        self.max_possible = 0.0
        
    def add_turn(
        self,
        question: str,
        answer: str,
        evaluation: Dict,
        is_followup: bool,
        topic: Optional[str] = None,
        metadata: Optional[Dict] = None
    ):
        """
        Add a Q&A turn to conversation history
        
        Args:
            question: Question text
            answer: User's answer
            evaluation: Evaluation results from AnswerEvaluator
            is_followup: Is this a follow-up question?
            topic: Topic/category (for new questions)
            metadata: Additional metadata from question generator
        """
        
        turn = Turn(
            question=question,
            answer=answer,
            evaluation=evaluation,
            is_followup=is_followup,
            topic=topic or self.current_topic,
            question_metadata=metadata
        )
        self.history.append(turn)
        
        # Update state
        if not is_followup:
            # New topic started
            if topic:
                if self.current_topic and self.current_topic != topic:
                    # Topic changed
                    self.topics_covered.append(self.current_topic)
                self.current_topic = topic
            self.topic_depth = 0
        else:
            # Follow-up question
            self.topic_depth += 1
        
        # Update scoring (if metadata available)
        if metadata:
            difficulty = metadata.get("difficulty", "medium")
            points_map = {"easy": 1.0, "medium": 2.0, "hard": 3.0}
            points_possible = points_map.get(difficulty, 2.0)
            points_earned = points_possible * evaluation.get("depth_score", 0.0)
            
            self.total_points += points_earned
            self.max_possible += points_possible
    
    def get_questions_asked(self) -> int:
        """Count main questions (not follow-ups)"""
        return sum(1 for turn in self.history if not turn.is_followup)
    
    def get_total_turns(self) -> int:
        """Count all turns (questions + follow-ups)"""
        return len(self.history)
    
    def get_last_turn(self) -> Optional[Turn]:
        """Get most recent turn"""
        return self.history[-1] if self.history else None
    
    def get_last_n_turns(self, n: int) -> List[Turn]:
        """Get last N turns for context"""
        return self.history[-n:] if self.history else []
    
    def is_complete(self) -> bool:
        """Check if interview target is met"""
        return self.get_questions_asked() >= self.total_questions
    
    def get_current_topic_depth(self) -> int:
        """How many follow-ups on current topic"""
        return self.topic_depth
    
    def get_topics_covered_list(self) -> List[str]:
        """Get all topics discussed (including current)"""
        covered = list(self.topics_covered)
        if self.current_topic and self.current_topic not in covered:
            covered.append(self.current_topic)
        return covered
    
    def get_conversation_summary(self, last_n: int = 3) -> str:
        """
        Generate text summary of recent conversation
        
        Used for context in question generation
        """
        if not self.history:
            return "Interview just started - no history yet."
        
        turns = self.get_last_n_turns(last_n)
        
        lines = []
        for i, turn in enumerate(turns, 1):
            marker = "[FOLLOW-UP]" if turn.is_followup else "[NEW TOPIC]"
            depth = turn.evaluation.get("depth_score", 0)
            passed = "✓" if turn.evaluation.get("pass", False) else "✗"
            
            lines.append(f"{marker} Q{i}: {turn.question[:60]}...")
            lines.append(f"  A{i}: {turn.answer[:60]}...")
            lines.append(f"  Score: {passed} {depth:.2f}\n")
        
        return "\n".join(lines)
    
    def get_performance_summary(self) -> Dict:
        """Get overall performance statistics"""
        
        if not self.history:
            return {
                "questions_asked": 0,
                "total_turns": 0,
                "score": 0.0,
                "percentage": 0.0,
                "topics_covered": 0
            }
        passed_count = sum(1 for t in self.history if t.evaluation.get("pass", False))
        avg_depth = sum(t.evaluation.get("depth_score", 0) for t in self.history) / len(self.history)
        
        percentage = (self.total_points / self.max_possible * 100) if self.max_possible > 0 else 0.0
        
        return {
            "questions_asked": self.get_questions_asked(),
            "total_turns": self.get_total_turns(),
            "passed": passed_count,
            "failed": len(self.history) - passed_count,
            "score": round(self.total_points, 2),
            "max_score": round(self.max_possible, 2),
            "percentage": round(percentage, 1),
            "average_depth": round(avg_depth, 3),
            "topics_covered": len(self.get_topics_covered_list())
        }
    
    def to_dict(self) -> Dict:
        """Export complete state for logging"""
        return {
            "session_metadata": {
                "total_questions_target": self.total_questions,
                "questions_asked": self.get_questions_asked(),
                "total_turns": self.get_total_turns(),
                "topics_covered": self.get_topics_covered_list(),
                "score": round(self.total_points, 3),
                "max_score": round(self.max_possible, 3)
            },
            "conversation_history": [
                {
                    "turn_number": i + 1,
                    "timestamp": turn.timestamp,
                    "is_followup": turn.is_followup,
                    "topic": turn.topic,
                    "question": turn.question,
                    "answer": turn.answer,
                    "evaluation": turn.evaluation,
                    "metadata": turn.question_metadata
                }
                for i, turn in enumerate(self.history)
            ],
            "performance": self.get_performance_summary()
        }
    
    def print_summary(self):
        """Print formatted summary to console"""
        perf = self.get_performance_summary()
        
        print("\n" + "=" * 60)
        print("   INTERVIEW SUMMARY")
        print("=" * 60)
        print(f"\nQuestions Asked: {perf['questions_asked']}/{self.total_questions}")
        print(f"Total Turns (w/ follow-ups): {perf['total_turns']}")
        print(f"Passed: {perf['passed']} | Failed: {perf['failed']}")
        print(f"Score: {perf['score']:.1f}/{perf['max_score']:.1f} ({perf['percentage']}%)")
        print(f"Average Depth: {perf['average_depth']:.2f}")
        print(f"Topics Covered: {perf['topics_covered']}")
        
        if self.topics_covered:
            print(f"\nTopics: {', '.join(self.get_topics_covered_list())}")
        
        print("=" * 60 + "\n")


# ========== USAGE EXAMPLE ==========
if __name__ == "__main__":
    manager = ConversationManager(total_questions=3)

    print("=== SIMULATED INTERVIEW ===\n")

    manager.add_turn(
        question="What is polymorphism in OOP?",
        answer="It's when objects can take multiple forms.",
        evaluation={"pass": False, "depth_score": 0.4, "confidence": 0.7, "feedback": "Too brief", "answer_length": 7},
        is_followup=False,
        topic="Object-Oriented Programming",
        metadata={"difficulty": "medium", "category": "OOP"}
    )    
    manager.add_turn(
        question="Can you give me a concrete example?",
        answer="Like a shape class that can be a circle or square.",
        evaluation={"pass": True, "depth_score": 0.7, "confidence": 0.6, "feedback": "Better", "answer_length": 10},
        is_followup=True
    )
    manager.add_turn(
        question="What is a linked list?",
        answer="A data structure where elements are connected with pointers to next element.",
        evaluation={"pass": True, "depth_score": 0.8, "confidence": 0.8, "feedback": "Good", "answer_length": 12},
        is_followup=False,
        topic="Data Structures",
        metadata={"difficulty": "easy", "category": "Data Structures"}
    )
    print(f"Questions asked: {manager.get_questions_asked()}/3")
    print(f"Current topic: {manager.current_topic}")
    print(f"Topic depth: {manager.get_current_topic_depth()}")
    print(f"Complete: {manager.is_complete()}")
    manager.print_summary()
    print("\n=== RECENT CONVERSATION ===")
    print(manager.get_conversation_summary(last_n=2))