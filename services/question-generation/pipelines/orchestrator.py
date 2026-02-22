import logging
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


class InterviewOrchestrator:
    
    def __init__(self, evaluator, question_generator, flow_controller=None):
        self.evaluator = evaluator
        self.generator = question_generator
    
    def generate_next_question(self, resume_json: Dict = None, previous_qa_list: Optional[List[Dict]] = None, difficulty: str = "medium") -> Tuple[str, Dict]:
        if not previous_qa_list or len(previous_qa_list) == 0:
            logger.info("Generating first question")
            question, metadata = self.generator.generate_new_topic_question(topics_covered=[], difficulty=difficulty, resume_json=resume_json)
            logger.info(f"Generated first question: category={metadata.get('category')}")
            return question, metadata
        
        last_qa = previous_qa_list[-1]
        
        evaluation_result = self._evaluate_previous_answer(last_qa["Q"], last_qa["A"])
        logger.info(f"Evaluation: decision={evaluation_result.get('decision')}, score={evaluation_result.get('score_value'):.2f}")
        
        decision = evaluation_result.get("decision", "new_topic")
        
        if decision in ["deep_dive", "same_topic"]:
            question, metadata = self.generator.generate_followup_question(
                previous_question=last_qa["Q"],
                previous_answer=last_qa["A"],
                evaluation_result=evaluation_result,
                resume_json=resume_json
            )
            metadata["evaluation"] = {
                "decision": evaluation_result.get("decision"),
                "score": evaluation_result.get("score_value"),
                "remarks": evaluation_result.get("remarks")
            }
        else:
            topics_covered = self._extract_topics(previous_qa_list)
            question, metadata = self.generator.generate_new_topic_question(
                topics_covered=topics_covered,
                difficulty=difficulty,
                resume_json=resume_json
            )
            metadata["evaluation"] = {
                "decision": evaluation_result.get("decision"),
                "score": evaluation_result.get("score_value"),
                "remarks": evaluation_result.get("remarks")
            }
        
        return question, metadata
    
    def _evaluate_previous_answer(self, question: str, answer: str) -> Dict:
        return self.evaluator.evaluate_for_flow_decision(question=question, user_answer=answer, reference_answer=None)
    
    def _extract_topics(self, previous_qa_list: List[Dict]) -> List[str]:
        return []