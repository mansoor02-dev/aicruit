"""
Interview Orchestrator

Consolidates the entire interview flow into a single module:
1. Evaluation (LLM-only, no resume context)
2. Flow decision (based on evaluation output only)
3. Question generation (resume injected at generation time)

This is the ONLY module that coordinates multiple pipeline steps.
All other modules are independently callable.
"""

import logging
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class EvaluationResult:
    """Standardized evaluation output (LLM-only)"""
    decision: str  # "new_topic" | "same_topic" | "deep_dive"
    remarks: str
    score: Dict[str, Any]  # {"value": float, "reason": str}


@dataclass
class OrchestrationDecision:
    """Decision about next question generation"""
    action: str  # "followup" | "new_topic" | "end"
    include_previous_qa: bool  # Whether to pass prev Q/A to generator
    evaluation_result: EvaluationResult


class InterviewOrchestrator:
    """
    Coordinates the entire single-question generation flow.
    
    Flow:
    1. First question → Skip evaluation, return question
    2. Subsequent questions:
       a) Evaluate previous answer (LLM-only)
       b) Decide next action (based on evaluation.decision)
       c) Generate question (with/without previous Q/A)
    
    No resume data reaches the evaluator.
    All context is stateless (provided per call).
    """
    
    def __init__(
        self,
        evaluator: Any,  # AnswerEvaluator
        flow_controller: Any,  # FlowController
        question_generator: Any,  # QuestionGenerator
    ):
        """
        Args:
            evaluator: LLM-based answer evaluator
            flow_controller: Decision maker for interview flow
            question_generator: Question generation engine
        """
        self.evaluator = evaluator
        self.flow_controller = flow_controller
        self.generator = question_generator
    
    def generate_next_question(
        self,
        resume_json: Dict,
        previous_qa_list: Optional[List[Dict]] = None,
        difficulty: str = "medium"
    ) -> Tuple[str, Dict]:
        """
        Main orchestration entry point.
        Generates exactly ONE question based on interview state.
        
        Args:
            resume_json: Candidate resume (dict)
            previous_qa_list: List of {"Q": str, "A": str} dicts (or None for first question)
            difficulty: Difficulty level
        
        Returns:
            (question_text, metadata_dict)
        """
        
        # ========== CASE 1: FIRST QUESTION ==========
        if not previous_qa_list or len(previous_qa_list) == 0:
            logger.info("Generating first question")
            question, metadata = self.generator.generate_new_topic_question(
                topics_covered=[],
                difficulty=difficulty
            )
            logger.info(f"Generated first question with category={metadata.get('category')}")
            return question, metadata
        
        # ========== CASE 2: EVALUATE & DECIDE ==========
        last_qa = previous_qa_list[-1]
        
        # STEP 1: Evaluate previous answer (LLM-only, NO resume)
        evaluation_result = self._evaluate_previous_answer(
            question=last_qa["Q"],
            answer=last_qa["A"]
        )
        logger.info(
            f"Evaluation decision={evaluation_result.decision}, "
            f"score={evaluation_result.score['value']:.2f}"
        )
        
        # STEP 2: Decide orchestration action
        orchestration_decision = self._decide_next_action(
            evaluation_result=evaluation_result,
            previous_qa_count=len(previous_qa_list),
            difficulty=difficulty
        )
        logger.info(
            f"Orchestration action={orchestration_decision.action}, "
            f"include_prev_qa={orchestration_decision.include_previous_qa}"
        )
        
        # STEP 3: Generate question based on decision
        # At this point, we inject resume + decision context
        if orchestration_decision.action == "followup":
            question, metadata = self.generator.generate_followup_question(
                resume_json=resume_json,
                previous_question=last_qa["Q"],
                previous_answer=last_qa["A"],
                evaluation_result=evaluation_result,
                difficulty=difficulty
            )
            metadata["include_previous_qa"] = True
        else:
            # Generate new topic (may still consider evaluation context)
            question, metadata = self.generator.generate_new_topic_question(
                resume_json=resume_json,
                topics_covered=self._extract_topics(previous_qa_list),
                evaluation_result=evaluation_result,
                difficulty=difficulty
            )
            metadata["include_previous_qa"] = False
        
        # Attach evaluation to metadata for logging/reporting
        metadata["evaluation"] = {
            "decision": evaluation_result.decision,
            "score": evaluation_result.score["value"],
            "remarks": evaluation_result.remarks
        }
        
        return question, metadata
    
    def _evaluate_previous_answer(
        self,
        question: str,
        answer: str
    ) -> EvaluationResult:
        """
        Evaluate the previous answer using LLM only.
        
        This is the ONLY place evaluation happens.
        No resume data is provided.
        
        Args:
            question: Previous question
            answer: Candidate's answer
        
        Returns:
            EvaluationResult with decision/remarks/score
        """
        
        # Call the LLM evaluator
        # The evaluator should use ONLY question + answer context
        evaluation_dict = self.evaluator.evaluate_for_flow_decision(
            question=question,
            user_answer=answer,
            reference_answer=None  # LLM-only evaluation
        )
        
        # Convert to standardized format
        result = EvaluationResult(
            decision=evaluation_dict.get("decision", "new_topic"),
            remarks=evaluation_dict.get("remarks", ""),
            score={
                "value": evaluation_dict.get("score_value", 0.5),
                "reason": evaluation_dict.get("score_reason", "")
            }
        )
        
        return result
    
    def _decide_next_action(
        self,
        evaluation_result: EvaluationResult,
        previous_qa_count: int,
        difficulty: str
    ) -> OrchestrationDecision:
        """
        Decide orchestration action based on evaluation ONLY.
        
        Rules:
        1. If evaluation.decision == "deep_dive" → followup
        2. If evaluation.decision == "same_topic" → followup  
        3. If evaluation.decision == "new_topic" → new_topic
        4. If too many previous Q/A → consider end (caller decides)
        
        Args:
            evaluation_result: Output from evaluation
            previous_qa_count: How many Q/A pairs so far
            difficulty: Current difficulty level
        
        Returns:
            OrchestrationDecision with action and whether to include prev Q/A
        """
        
        decision_map = evaluation_result.decision.lower()
        
        if decision_map == "deep_dive":
            return OrchestrationDecision(
                action="followup",
                include_previous_qa=True,
                evaluation_result=evaluation_result
            )
        elif decision_map == "same_topic":
            return OrchestrationDecision(
                action="followup",
                include_previous_qa=True,
                evaluation_result=evaluation_result
            )
        else:  # "new_topic" or default
            return OrchestrationDecision(
                action="new_topic",
                include_previous_qa=False,
                evaluation_result=evaluation_result
            )
    
    def _extract_topics(self, previous_qa_list: List[Dict]) -> List[str]:
        """
        Extract unique topics covered from previous Q/A history.
        Used to avoid repeating topics.
        
        Args:
            previous_qa_list: List of previous Q/A pairs
        
        Returns:
            List of topic strings
        """
        # Placeholder: in real implementation, would extract from metadata
        # or use other signals from the Q/A history
        return []
