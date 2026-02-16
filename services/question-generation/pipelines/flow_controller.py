"""
Flow Controller - Decides when to follow-up vs ask new questions

This is the BRAIN of the realistic interviewer system.
"""
import random
from typing import Dict, Optional, Literal
from dataclasses import dataclass

@dataclass
class FlowDecision:
    """Decision about next question type"""
    action: Literal["followup", "new_topic", "end"]
    reason: str
    suggested_angle: Optional[str] = None  # For follow-ups: what to probe


class FlowController:
    """
    Determines interview progression using realistic interviewer logic
    
    Key Insight: Real interviewers follow-up when:
    - Answer is vague/incomplete
    - Topic is important and worth drilling
    - They want to test depth vs breadth of knowledge
    
    They move on when:
    - Answer is comprehensive
    - Already asked 2-3 follow-ups on this topic
    - Need to cover more ground
    """
    
    def __init__(
        self,
        max_followups_per_topic: int = 1,
        followup_probability_base: float = 0.6,  # 60% chance of follow-up if answer is weak
        variety_bonus: float = 0.3  # Increase new topic chance as topics get repetitive
    ):
        self.max_followups = max_followups_per_topic
        self.base_followup_prob = followup_probability_base
        self.variety_bonus = variety_bonus
    
    def decide_next_action(
        self,
        evaluation: Dict,
        topic_depth: int,  # How many follow-ups already on this topic
        questions_asked: int,  # Total main questions asked
        total_questions: int,  # Target total
        topics_covered: list  # What topics already discussed
    ) -> FlowDecision:
        """
        Main decision logic - realistic interviewer behavior
        
        Args:
            evaluation: Last answer evaluation {pass, depth_score, confidence}
            topic_depth: Follow-ups already asked on current topic
            questions_asked: Main topics covered so far
            total_questions: Target number of main topics
            topics_covered: List of topics already discussed
        """
        
        # ========== RULE 1: Interview Complete ==========
        if questions_asked >= total_questions:
            return FlowDecision(
                action="end",
                reason="Interview complete - all topics covered"
            )
        
        # ========== RULE 2: Max Follow-ups Reached ==========
        if topic_depth >= self.max_followups:
            return FlowDecision(
                action="new_topic",
                reason=f"Max follow-ups ({self.max_followups}) reached on this topic"
            )
        
        # ========== RULE 3: First Question (no history yet) ==========
        if questions_asked == 0:
            return FlowDecision(
                action="new_topic",
                reason="Starting interview with first question"
            )
        
        # ========== EXTRACT EVALUATION SIGNALS ==========
        passed = evaluation.get("pass", False)
        depth_score = evaluation.get("depth_score", 0.5)  # 0-1 scale
        confidence = evaluation.get("confidence", 0.5)
        answer_length = evaluation.get("answer_length", 0)  # words
        
        # ========== RULE 4: Answer Quality Assessment ==========
        # Strong answer: high score + confident + reasonable length
        is_strong_answer = (
            passed and 
            depth_score >= 0.7 and 
            confidence >= 0.6 and
            answer_length >= 15
        )
        
        # Weak answer: failed or very short or low depth
        is_weak_answer = (
            not passed or 
            depth_score < 0.4 or
            answer_length < 10
        )
        
        # ========== RULE 5: Strong Answer → Usually Move On ==========
        if is_strong_answer:
            # But sometimes follow-up even on good answers (realistic!)
            # Interviewers probe depth even when answer seems good
            if random.random() < 0.25 and topic_depth < self.max_followups:
                return FlowDecision(
                    action="followup",
                    reason="Answer good, but probing deeper to test mastery",
                    suggested_angle="implementation_details"  # How would you actually do this?
                )
            
            return FlowDecision(
                action="new_topic",
                reason="Answer comprehensive - moving to new topic"
            )
        
        # ========== RULE 6: Weak Answer → Follow-up (if not exhausted) ==========
        if is_weak_answer:
            if topic_depth < self.max_followups:
                # Decide WHAT to probe based on weakness
                if answer_length < 10:
                    angle = "elaboration"  # "Can you elaborate on that?"
                elif depth_score < 0.4:
                    angle = "clarification"  # "What do you mean by...?"
                else:
                    angle = "examples"  # "Can you give an example?"
                
                return FlowDecision(
                    action="followup",
                    reason=f"Answer unclear/incomplete (depth: {depth_score:.2f})",
                    suggested_angle=angle
                )
            else:
                # Exhausted follow-ups on weak topic - move on
                return FlowDecision(
                    action="new_topic",
                    reason="Multiple weak answers - moving to assess other areas"
                )
        
        # ========== RULE 7: Medium Answer → Probabilistic ==========
        # Answer is "okay" but not strong - realistic interviewer might probe OR move on
        
        # Calculate follow-up probability based on context
        followup_prob = self.base_followup_prob
        
        # Adjust based on depth score (lower score = higher follow-up chance)
        followup_prob += (0.7 - depth_score) * 0.3
        
        # Reduce if already asked follow-ups
        followup_prob -= topic_depth * 0.15
        
        # Increase if running low on questions (need to cover ground)
        progress = questions_asked / total_questions
        if progress > 0.7:  # 70% through interview
            followup_prob -= 0.2  # Less likely to follow-up near end
        
        # Decide with probability
        if random.random() < followup_prob and topic_depth < self.max_followups:
            return FlowDecision(
                action="followup",
                reason=f"Moderate answer - probing for depth (score: {depth_score:.2f})",
                suggested_angle="tradeoffs"  # "What are the trade-offs?"
            )
        else:
            return FlowDecision(
                action="new_topic",
                reason="Moderate answer acceptable - moving to next topic"
            )
    
    def get_followup_prompt_template(self, angle: str) -> str:
        """
        Get prompt template for different follow-up angles
        
        Returns a template that question_generator.py can use
        """
        templates = {
            "elaboration": (
                "The candidate's answer was brief. Ask them to elaborate and provide more details. "
                "Example: 'Can you elaborate on that?' or 'Can you explain that in more depth?'"
            ),
            "clarification": (
                "The candidate's answer was unclear or vague. Ask for clarification on specific points. "
                "Example: 'What exactly do you mean by X?' or 'Can you clarify your point about Y?'"
            ),
            "examples": (
                "The candidate gave a theoretical answer. Ask for concrete examples or use cases. "
                "Example: 'Can you give a practical example?' or 'When would you use this approach?'"
            ),
            "implementation_details": (
                "The candidate understands the concept. Now probe how they'd implement it. "
                "Example: 'How would you implement this?' or 'Walk me through your approach step-by-step.'"
            ),
            "tradeoffs": (
                "The candidate mentioned one approach. Ask about alternatives and trade-offs. "
                "Example: 'What are the trade-offs?' or 'How does this compare to alternative approaches?'"
            ),
            "edge_cases": (
                "The candidate explained the happy path. Ask about edge cases or failure scenarios. "
                "Example: 'What could go wrong?' or 'How would this handle edge cases?'"
            )
        }
        
        return templates.get(angle, templates["elaboration"])


# ========== USAGE EXAMPLE ==========
if __name__ == "__main__":
    controller = FlowController()
    
    # Scenario 1: Weak answer on first question
    evaluation1 = {
        "pass": False,
        "depth_score": 0.3,
        "confidence": 0.4,
        "answer_length": 8
    }
    
    decision1 = controller.decide_next_action(
        evaluation=evaluation1,
        topic_depth=0,
        questions_asked=1,
        total_questions=5,
        topics_covered=["algorithms"]
    )
    print(f"Scenario 1: {decision1.action} - {decision1.reason}")
    print(f"Follow-up angle: {decision1.suggested_angle}\n")
    
    # Scenario 2: Strong answer after 1 follow-up
    evaluation2 = {
        "pass": True,
        "depth_score": 0.85,
        "confidence": 0.8,
        "answer_length": 45
    }
    
    decision2 = controller.decide_next_action(
        evaluation=evaluation2,
        topic_depth=1,
        questions_asked=2,
        total_questions=5,
        topics_covered=["algorithms", "databases"]
    )
    print(f"Scenario 2: {decision2.action} - {decision2.reason}\n")
    
    # Scenario 3: Medium answer, already 2 follow-ups
    evaluation3 = {
        "pass": True,
        "depth_score": 0.55,
        "confidence": 0.6,
        "answer_length": 20
    }
    
    decision3 = controller.decide_next_action(
        evaluation=evaluation3,
        topic_depth=2,
        questions_asked=3,
        total_questions=5,
        topics_covered=["algorithms", "databases", "oop"]
    )
    print(f"Scenario 3: {decision3.action} - {decision3.reason}")