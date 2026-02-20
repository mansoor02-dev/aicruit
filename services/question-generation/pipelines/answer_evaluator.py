import re
import json
from typing import Any, Dict, Optional
import numpy as np
from sentence_transformers import SentenceTransformer
from pipelines.llm_loader import LLMLoader

class AnswerEvaluator:
    """
    Evaluates candidate answers with focus on:
    1. Is this answer sufficient? (pass/fail)
    2. How deep is their understanding? (depth_score)
    3. Should we follow-up? (needs_followup)
    """
    
    def __init__(
        self, 
        embedder: SentenceTransformer, 
        model_type: str = 'openrouter', 
        pass_threshold: float = 0.55
    ):
        self.embedder = embedder
        self.llm = LLMLoader(model_type=model_type).get_llm()
        self.pass_threshold = pass_threshold
    
    def evaluate(
        self,
        question: str,
        user_answer: str,
        reference_answer: Optional[str] = None,
        is_followup: bool = False
    ) -> Dict:
        """
        Main evaluation method
        Returns evaluation dict with:
        - pass: bool
        - depth_score: float 0-1
        - confidence: float 0-1
        - feedback: str
        - answer_length: int
        - needs_followup: bool
        """
        
        if not user_answer or len(user_answer.strip()) < 3:
            return {
                "pass": False,
                "depth_score": 0.0,
                "confidence": 1.0,
                "feedback": "Empty or very short answer",
                "answer_length": 0,
                "needs_followup": True
            }
        
        answer_length = len(user_answer.split())
        
        if is_followup or not reference_answer:
            return self._evaluate_without_reference(
                question,
                user_answer,
                answer_length
            )
        
        return self._evaluate_with_reference(
            question,
            user_answer,
            reference_answer,
            answer_length
        )
    
    def _evaluate_with_reference(
        self, question: str, user_answer: str, reference_answer: str, answer_length: int) -> Dict:
        """Evaluate using reference answer from dataset"""
        
        semantic_score = self._semantic_similarity(user_answer, reference_answer)
        keyword_score = self._keyword_overlap(user_answer, reference_answer)
        length_score = min(1.0, answer_length / 20)
        
        depth_score = (
            0.5 * semantic_score +
            0.3 * keyword_score +
            0.2 * length_score
        )
        
        depth_score = round(max(0.0, min(1.0, depth_score)), 3)
        passed = depth_score >= self.pass_threshold
        confidence = 0.7
        feedback = ""
        
        if 0.45 <= depth_score <= 0.65 or depth_score >= 0.85:
            llm_result = self._llm_quick_check(question, reference_answer, user_answer)
            
            if llm_result:
                llm_score = llm_result.get("score", depth_score)
                depth_score = round(0.6 * depth_score + 0.4 * llm_score, 3)
                passed = depth_score >= self.pass_threshold
                confidence = llm_result.get("confidence", 0.7)
                feedback = llm_result.get("feedback", "")
        
        if not feedback:
            if passed:
                feedback = "Answer demonstrates understanding"
            else:
                feedback = "Answer lacks key concepts or detail"
        
        return {
            "pass": passed,
            "depth_score": depth_score,
            "confidence": confidence,
            "feedback": feedback,
            "answer_length": answer_length,
            "needs_followup": not passed
        }
    
    def _evaluate_without_reference(
        self, question: str, user_answer: str, answer_length: int
    ) -> Dict:
        """Evaluate follow-up answers (no reference)"""
        
        if answer_length < 10:
            return {
                "pass": False,
                "depth_score": 0.3,
                "confidence": 0.8,
                "feedback": "Answer too brief",
                "answer_length": answer_length,
                "needs_followup": True
            }
        
        llm_result = self._llm_evaluate_no_reference(question, user_answer)
        
        if llm_result:
            depth_score = llm_result.get("score", 0.5)
            passed = depth_score >= self.pass_threshold
            
            return {
                "pass": passed,
                "depth_score": depth_score,
                "confidence": llm_result.get("confidence", 0.6),
                "feedback": llm_result.get("feedback", "Evaluated without reference"),
                "answer_length": answer_length,
                "needs_followup": not passed
            }
        
        return {
            "pass": answer_length >= 15,
            "depth_score": 0.5,
            "confidence": 0.4,
            "feedback": "Evaluation inconclusive",
            "answer_length": answer_length,
            "needs_followup": False
        }
    
    def _semantic_similarity(self, text1: str, text2: str) -> float:
        """Cosine similarity using embeddings"""
        try:
            emb1 = self.embedder.encode([text1], normalize_embeddings=True)[0]
            emb2 = self.embedder.encode([text2], normalize_embeddings=True)[0]
            
            sim = float(np.dot(emb1, emb2))
            return max(0.0, min(1.0, sim))
        except Exception:
            return 0.5
    
    def _keyword_overlap(self, user_answer: str, reference: str) -> float:
        """Jaccard similarity of technical keywords"""
        
        def extract_keywords(text):
            words = re.findall(r'\b[a-zA-Z0-9_]{3,}\b', text.lower())
            stop = {'the', 'and', 'for', 'this', 'that', 'with', 'from', 'are', 'was'}
            return set(w for w in words if w not in stop)
        
        user_kw = extract_keywords(user_answer)
        ref_kw = extract_keywords(reference)
        
        if not ref_kw:
            return 0.5
        
        intersection = len(user_kw & ref_kw)
        union = len(user_kw | ref_kw)
        
        if union == 0:
            return 0.0
        
        jaccard = intersection / union
        recall = intersection / len(ref_kw)
        
        return 0.5 * jaccard + 0.5 * recall
    
    def _llm_quick_check(
        self,
        question: str,
        reference: str,
        user_answer: str
    ) -> Optional[Dict]:
        """Quick LLM check for borderline answers"""
        
        prompt = f"""Evaluate this technical interview answer.

QUESTION: {question[:200]}

EXPECTED: {reference[:200]}

CANDIDATE: {user_answer[:200]}

Rate 0.0-1.0 (0=wrong, 0.5=partial, 1.0=correct).
Return JSON only: {{"score": 0.0-1.0, "confidence": 0.0-1.0, "feedback": "brief"}}

JSON:"""

        try:
            resp = self.llm(
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1,
                max_tokens=100
            )
            
            text = resp["choices"][0]["message"]["content"]
            
            match = re.search(r'\{[^{}]*\}', text)
            if match:
                parsed = json.loads(match.group(0))
                return {
                    "score": float(parsed.get("score", 0.5)),
                    "confidence": float(parsed.get("confidence", 0.5)),
                    "feedback": str(parsed.get("feedback", ""))[:100]
                }
        except Exception:
            pass
        
        return None
    
    def _llm_evaluate_no_reference(
        self,
        question: str,
        user_answer: str
    ) -> Optional[Dict]:
        """LLM evaluation when no reference answer exists"""
        
        prompt = f"""Evaluate this interview answer (no reference available).

QUESTION: {question[:200]}

CANDIDATE: {user_answer[:200]}

Assess clarity, depth, and technical accuracy.
Rate 0.0-1.0 (0=poor, 0.5=acceptable, 1.0=excellent).
Return JSON: {{"score": 0.0-1.0, "confidence": 0.0-1.0, "feedback": "brief"}}

JSON:"""

        try:
            resp = self.llm(
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1,
                max_tokens=100
            )
            
            text = resp["choices"][0]["message"]["content"]
            
            match = re.search(r'\{[^{}]*\}', text)
            if match:
                parsed = json.loads(match.group(0))
                return {
                    "score": float(parsed.get("score", 0.5)),
                    "confidence": float(parsed.get("confidence", 0.5)),
                    "feedback": str(parsed.get("feedback", ""))[:100]
                }
        except Exception:
            pass
        
        return None
    
    def evaluate_for_flow_decision(
        self,
        question: str,
        user_answer: str,
        reference_answer: Optional[str] = None
    ) -> Dict:
        """
        LLM-ONLY evaluation for orchestrator flow decision.
        
        Returns:
        {
            "decision": "new_topic" | "same_topic" | "deep_dive",
            "remarks": str,
            "score_value": float (0-1),
            "score_reason": str
        }
        """
        
        if not user_answer or len(user_answer.strip()) < 3:
            return {
                "decision": "same_topic",
                "remarks": "Answer too brief - follow-up needed",
                "score_value": 0.1,
                "score_reason": "Empty or minimal answer"
            }
        
        answer_length = len(user_answer.split())
        llm_result = self._llm_flow_decision(question, user_answer)
        
        if llm_result:
            return {
                "decision": llm_result.get("decision", "new_topic"),
                "remarks": llm_result.get("remarks", ""),
                "score_value": llm_result.get("score", 0.5),
                "score_reason": llm_result.get("score_reason", "LLM evaluation")
            }
        
        if answer_length < 10:
            decision = "same_topic"
        elif answer_length < 25:
            decision = "new_topic"
        else:
            decision = "new_topic"
        
        score = min(1.0, answer_length / 30)
        
        return {
            "decision": decision,
            "remarks": "Heuristic evaluation (LLM unavailable)",
            "score_value": score,
            "score_reason": f"Answer length: {answer_length} words"
        }
    
    def _llm_flow_decision(
        self,
        question: str,
        user_answer: str
    ) -> Optional[Dict]:
        """Use LLM to make flow decision"""
        
        prompt = f"""Evaluate this technical interview answer for flow decision.

QUESTION: {question[:250]}

CANDIDATE ANSWER: {user_answer[:400]}

Based on answer quality:
1. Score it 0.0-1.0 (0=wrong, 0.5=partial, 1.0=excellent)
2. Decide next action:
   - "deep_dive": Answer shows depth, probe deeper
   - "same_topic": Answer lacks depth/clarity, same topic follow-up
   - "new_topic": Answer is adequate, move to new topic

Return JSON only:
{{
  "decision": "deep_dive" | "same_topic" | "new_topic",
  "remarks": "brief reason for decision",
  "score": 0.0-1.0,
  "score_reason": "why this score"
}}

JSON:"""

        try:
            resp = self.llm(
                messages=[{"role": "user", "content": prompt}],
                temperature=0.2,
                max_tokens=150
            )
            
            text = resp["choices"][0]["message"]["content"]
            
            match = re.search(r'\{[^{}]*\}', text, re.DOTALL)
            if match:
                parsed = json.loads(match.group(0))
                
                decision = parsed.get("decision", "new_topic").lower()
                if decision not in ["deep_dive", "same_topic", "new_topic"]:
                    decision = "new_topic"
                
                return {
                    "decision": decision,
                    "remarks": str(parsed.get("remarks", ""))[:200],
                    "score": float(parsed.get("score", 0.5)),
                    "score_reason": str(parsed.get("score_reason", ""))[:200]
                }
        except Exception:
            pass
        
        return None