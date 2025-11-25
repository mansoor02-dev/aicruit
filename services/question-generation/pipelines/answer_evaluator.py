"""
Answer Evaluator - Assess answer quality and provide feedback

Simpler than new_qa.py, focused on flow decisions not metrics
"""
import re
import json
from typing import Dict, Optional
import numpy as np
from sentence_transformers import SentenceTransformer
from llama_cpp import Llama
from tests.utils import get_test_llm


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
        llm: Llama,
        pass_threshold: float = 0.55  # Lower than before for realistic interviewing
    ):
        self.embedder = embedder
        self.llm = llm
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
        - pass: bool (did they pass this question?)
        - depth_score: float 0-1 (how deep was their answer?)
        - confidence: float 0-1 (how confident are we?)
        - feedback: str (brief feedback for logs)
        - answer_length: int (word count)
        - needs_followup: bool (deprecated - FlowController decides now)
        """
        
        # Basic sanity checks
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
        
        # For follow-ups, we have no reference answer
        # Must use LLM or heuristics only
        if is_followup or not reference_answer:
            return self._evaluate_without_reference(
                question,
                user_answer,
                answer_length
            )
        
        # For new topic questions, use reference answer
        return self._evaluate_with_reference(
            question,
            user_answer,
            reference_answer,
            answer_length
        )
    
    def _evaluate_with_reference(
        self,
        question: str,
        user_answer: str,
        reference_answer: str,
        answer_length: int
    ) -> Dict:
        """
        Evaluate using reference answer from dataset
        
        Uses combination of:
        1. Semantic similarity (embeddings)
        2. Keyword overlap
        3. LLM judgment (for borderline cases)
        """
        
        # 1. Semantic similarity
        semantic_score = self._semantic_similarity(user_answer, reference_answer)
        
        # 2. Keyword overlap
        keyword_score = self._keyword_overlap(user_answer, reference_answer)
        
        # 3. Length penalty (too short = incomplete)
        length_score = min(1.0, answer_length / 20)  # Expect ~20 words minimum
        
        # Combine scores with weights
        # Semantic is most important, keywords second, length is penalty
        depth_score = (
            0.5 * semantic_score +
            0.3 * keyword_score +
            0.2 * length_score
        )
        
        depth_score = round(max(0.0, min(1.0, depth_score)), 3)
        
        # Determine pass/fail
        passed = depth_score >= self.pass_threshold
        
        # Use LLM for borderline cases or very high scores (double-check)
        confidence = 0.7  # Default confidence
        feedback = ""
        
        if 0.45 <= depth_score <= 0.65 or depth_score >= 0.85:
            # Borderline or suspiciously good - use LLM
            llm_result = self._llm_quick_check(question, reference_answer, user_answer)
            
            if llm_result:
                # Adjust depth_score based on LLM
                llm_score = llm_result.get("score", depth_score)
                
                # Weighted combination: favor computed score slightly
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
            "needs_followup": not passed  # Deprecated but kept for compatibility
        }
    
    def _evaluate_without_reference(
        self,
        question: str,
        user_answer: str,
        answer_length: int
    ) -> Dict:
        """
        Evaluate follow-up answers (no reference)
        
        Must rely on:
        1. Answer length (too short = bad)
        2. LLM judgment
        """
        
        # Length heuristic
        if answer_length < 10:
            return {
                "pass": False,
                "depth_score": 0.3,
                "confidence": 0.8,
                "feedback": "Answer too brief",
                "answer_length": answer_length,
                "needs_followup": True
            }
        
        # Use LLM for actual evaluation
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
        
        # Fallback if LLM fails
        # Assume medium quality for reasonable-length answers
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
        """
        Jaccard similarity of technical keywords
        
        Simplified from new_qa.py - just basic keyword matching
        """
        
        def extract_keywords(text):
            # Words 3+ chars, lowercase
            words = re.findall(r'\b[a-zA-Z0-9_]{3,}\b', text.lower())
            # Remove common words
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
        
        # Jaccard + recall bonus
        jaccard = intersection / union
        recall = intersection / len(ref_kw)
        
        return 0.5 * jaccard + 0.5 * recall
    
    def _llm_quick_check(
        self,
        question: str,
        reference: str,
        user_answer: str
    ) -> Optional[Dict]:
        """
        Quick LLM check for borderline answers
        
        Simplified prompt for speed
        """
        
        prompt = f"""Evaluate this technical interview answer.

QUESTION: {question[:200]}

EXPECTED: {reference[:200]}

CANDIDATE: {user_answer[:200]}

Rate 0.0-1.0 (0=wrong, 0.5=partial, 1.0=correct).
Return JSON only: {{"score": 0.0-1.0, "confidence": 0.0-1.0, "feedback": "brief"}}

JSON:"""

        try:
            resp = self.llm.create_chat_completion(
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1,
                max_tokens=100
            )
            
            text = resp["choices"][0]["message"]["content"]
            
            # Extract JSON
            match = re.search(r'\{[^{}]*\}', text)
            if match:
                parsed = json.loads(match.group(0))
                return {
                    "score": float(parsed.get("score", 0.5)),
                    "confidence": float(parsed.get("confidence", 0.5)),
                    "feedback": str(parsed.get("feedback", ""))[:100]
                }
        except Exception as e:
            print(f"⚠️ LLM check failed: {e}")
        
        return None
    
    def _llm_evaluate_no_reference(
        self,
        question: str,
        user_answer: str
    ) -> Optional[Dict]:
        """
        LLM evaluation when no reference answer exists
        (for follow-up questions)
        """
        
        prompt = f"""Evaluate this interview answer (no reference available).

QUESTION: {question[:200]}

CANDIDATE: {user_answer[:200]}

Assess clarity, depth, and technical accuracy.
Rate 0.0-1.0 (0=poor, 0.5=acceptable, 1.0=excellent).
Return JSON: {{"score": 0.0-1.0, "confidence": 0.0-1.0, "feedback": "brief"}}

JSON:"""

        try:
            resp = self.llm.create_chat_completion(
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


# ========== USAGE EXAMPLE ==========
if __name__ == "__main__":
    from sentence_transformers import SentenceTransformer
    
    
    embedder = SentenceTransformer("all-MiniLM-L6-v2", device='cpu')
    evaluator = AnswerEvaluator(embedder, get_test_llm())
    
    # Test with reference
    question = "What is polymorphism?"
    reference = "Polymorphism allows objects of different types to be treated uniformly through inheritance and interfaces."
    user_answer = "It's when different objects can be used interchangeably."
    
    result = evaluator.evaluate(question, user_answer, reference, is_followup=False)
    
    print("=== EVALUATION RESULT ===")
    print(f"Pass: {result['pass']}")
    print(f"Depth Score: {result['depth_score']:.2f}")
    print(f"Confidence: {result['confidence']:.2f}")
    print(f"Feedback: {result['feedback']}")