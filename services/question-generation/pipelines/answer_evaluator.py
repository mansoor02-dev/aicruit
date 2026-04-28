import json
import re
import sys
from typing import Dict, Optional, Tuple

sys.path.insert(0, "/app")

import numpy as np
from sentence_transformers import SentenceTransformer

from shared.llm_client import LLMClient


# ---------------------------------------------------------------------------
# "I don't know" detection — short-circuit before any LLM / embedding call
# ---------------------------------------------------------------------------
_DONT_KNOW_RE = re.compile(
    r"\b("
    r"i (don'?t|do not|dont) know"
    r"|not (familiar|sure|aware|certain)"
    r"|i('?m| am) not (familiar|sure|aware|certain)"
    r"|no (idea|clue|knowledge)"
    r"|haven'?t (heard|learned|studied|used|seen)"
    r"|unfamiliar (with)?"
    r"|never (heard|used|seen|worked)"
    r"|i('?ll| will) (look|read|study|check) (it|that|this)? ?(up|later|in future|into it)?"
    r"|will look into"
    r"|need to (learn|study|read up)"
    r"|i (have no|lack) (knowledge|experience|understanding)"
    r"|sorry,? i (don'?t|do not)"
    r")\b",
    re.IGNORECASE,
)

_DONT_KNOW_EVAL: Dict = {
    "pass": False,
    "depth_score": 0.0,
    "confidence": 1.0,
    "feedback": "Candidate is not familiar with this topic.",
    "answer_length": 0,
    "needs_followup": False,   # No follow-up — just move on
}

_DONT_KNOW_FLOW: Dict = {
    "decision": "new_topic",
    "remarks": "Candidate is not familiar with this topic — moving on.",
    "score_value": 0.0,
    "score_reason": "Explicit unfamiliarity stated",
}

_STOP_WORDS = {"the", "and", "for", "this", "that", "with", "from", "are", "was"}


def _is_dont_know(text: str) -> bool:
    return bool(_DONT_KNOW_RE.search(text.strip()))


# ---------------------------------------------------------------------------
# Evaluator
# ---------------------------------------------------------------------------

class AnswerEvaluator:
    """
    Evaluates candidate answers.

    Key design decisions for speed:
    - "I don't know" answers are caught instantly by regex — zero LLM/embedding cost.
    - evaluate_combined() merges the scoring + flow-decision into ONE LLM call,
      cutting latency roughly in half compared to calling evaluate() and
      evaluate_for_flow_decision() separately.
    """

    PASS_THRESHOLD = 0.55

    def __init__(
        self,
        embedder: SentenceTransformer,
        model_type: str = "openrouter",
        pass_threshold: float = PASS_THRESHOLD,
    ):
        self.embedder = embedder
        self.llm = LLMLoader(model_type=model_type).get_llm()
        self.pass_threshold = pass_threshold

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def evaluate(
        self,
        question: str,
        user_answer: str,
        reference_answer: Optional[str] = None,
        is_followup: bool = False,
    ) -> Dict:
        """
        Full per-turn evaluation.
        Returns: pass, depth_score, confidence, feedback, answer_length, needs_followup
        """
        if not user_answer or len(user_answer.strip()) < 3:
            return self._empty_answer_result()

        if _is_dont_know(user_answer):
            return _DONT_KNOW_EVAL.copy()

        answer_length = len(user_answer.split())

        if is_followup or not reference_answer:
            return self._evaluate_without_reference(question, user_answer, answer_length)

        return self._evaluate_with_reference(question, user_answer, reference_answer, answer_length)

    def evaluate_for_flow_decision(self, question: str, user_answer: str) -> Dict:
        """
        Lightweight check used by the orchestrator to pick the next action.
        Returns: decision, remarks, score_value, score_reason
        """
        if not user_answer or len(user_answer.strip()) < 3:
            return {
                "decision": "same_topic",
                "remarks": "Answer too brief — follow-up needed",
                "score_value": 0.1,
                "score_reason": "Empty or minimal answer",
            }

        if _is_dont_know(user_answer):
            return _DONT_KNOW_FLOW.copy()

        answer_length = len(user_answer.split())
        llm_result = self._llm_flow_decision(question, user_answer)

        if llm_result:
            return {
                "decision":     llm_result["decision"],
                "remarks":      llm_result["remarks"],
                "score_value":  llm_result["score"],
                "score_reason": llm_result["score_reason"],
            }

        # Heuristic fallback
        return {
            "decision":     "same_topic" if answer_length < 10 else "new_topic",
            "remarks":      "Heuristic evaluation (LLM unavailable)",
            "score_value":  min(1.0, answer_length / 30),
            "score_reason": f"Answer length: {answer_length} words",
        }

    def evaluate_combined(
        self,
        question: str,
        user_answer: str,
        reference_answer: Optional[str] = None,
        is_followup: bool = False,
    ) -> Tuple[Dict, Dict]:
        """
        Produce BOTH the per-turn evaluation AND the flow decision in a single
        LLM call.  Use this in main.py / orchestrator to cut round-trips by half.

        Returns: (evaluation_dict, flow_dict)
        """
        if not user_answer or len(user_answer.strip()) < 3:
            flow = {
                "decision": "same_topic", "remarks": "Answer too brief",
                "score_value": 0.1, "score_reason": "Empty or minimal answer",
            }
            return self._empty_answer_result(), flow

        if _is_dont_know(user_answer):
            return _DONT_KNOW_EVAL.copy(), _DONT_KNOW_FLOW.copy()

        answer_length = len(user_answer.split())

        # Very short but not "don't know" — skip LLM
        if answer_length < 5:
            ev = {
                "pass": False, "depth_score": 0.2, "confidence": 0.9,
                "feedback": "Answer too brief to evaluate properly.",
                "answer_length": answer_length, "needs_followup": True,
            }
            fl = {
                "decision": "same_topic", "remarks": "Answer too brief",
                "score_value": 0.2, "score_reason": f"Only {answer_length} words",
            }
            return ev, fl

        combined = self._llm_combined_eval(question, user_answer, reference_answer, is_followup)

        if combined:
            score  = combined["score"]
            passed = score >= self.pass_threshold
            ev = {
                "pass": passed, "depth_score": round(score, 3),
                "confidence": combined["confidence"], "feedback": combined["feedback"],
                "answer_length": answer_length, "needs_followup": not passed,
            }
            fl = {
                "decision":     combined["decision"],
                "remarks":      combined["remarks"],
                "score_value":  score,
                "score_reason": combined.get("score_reason", "LLM evaluation"),
            }
            return ev, fl

        # Pure heuristic fallback
        ev = self._heuristic_eval(question, user_answer, reference_answer, answer_length)
        fl = {
            "decision":     "new_topic" if ev["pass"] else "same_topic",
            "remarks":      "Heuristic evaluation (LLM unavailable)",
            "score_value":  ev["depth_score"],
            "score_reason": "Embedding + keyword score",
        }
        return ev, fl

    # ------------------------------------------------------------------
    # Internal evaluation helpers
    # ------------------------------------------------------------------

    def _empty_answer_result(self) -> Dict:
        return {
            "pass": False, "depth_score": 0.0, "confidence": 1.0,
            "feedback": "Empty or very short answer.",
            "answer_length": 0, "needs_followup": True,
        }

    def _heuristic_eval(
        self,
        question: str,
        user_answer: str,
        reference_answer: Optional[str],
        answer_length: int,
    ) -> Dict:
        if reference_answer:
            sem  = self._semantic_similarity(user_answer, reference_answer)
            kw   = self._keyword_overlap(user_answer, reference_answer)
            lsco = min(1.0, answer_length / 20)
            depth_score = round(max(0.0, min(1.0, 0.5*sem + 0.3*kw + 0.2*lsco)), 3)
        else:
            depth_score = round(min(1.0, answer_length / 30), 3)

        passed = depth_score >= self.pass_threshold
        return {
            "pass": passed, "depth_score": depth_score, "confidence": 0.5,
            "feedback": "Answer demonstrates understanding." if passed else "Answer lacks key concepts.",
            "answer_length": answer_length, "needs_followup": not passed,
        }

    def _evaluate_with_reference(
        self, question: str, user_answer: str, reference_answer: str, answer_length: int
    ) -> Dict:
        sem  = self._semantic_similarity(user_answer, reference_answer)
        kw   = self._keyword_overlap(user_answer, reference_answer)
        lsco = min(1.0, answer_length / 20)

        depth_score = round(max(0.0, min(1.0, 0.5*sem + 0.3*kw + 0.2*lsco)), 3)
        passed      = depth_score >= self.pass_threshold
        confidence  = 0.7
        feedback    = ""

        # Call LLM only for borderline or very high scores
        if 0.45 <= depth_score <= 0.65 or depth_score >= 0.85:
            llm = self._llm_quick_check(question, reference_answer, user_answer)
            if llm:
                depth_score = round(0.6 * depth_score + 0.4 * llm["score"], 3)
                passed      = depth_score >= self.pass_threshold
                confidence  = llm["confidence"]
                feedback    = llm["feedback"]

        if not feedback:
            feedback = "Answer demonstrates understanding." if passed else "Answer lacks key concepts."

        return {
            "pass": passed, "depth_score": depth_score, "confidence": confidence,
            "feedback": feedback, "answer_length": answer_length, "needs_followup": not passed,
        }

    def _evaluate_without_reference(
        self, question: str, user_answer: str, answer_length: int
    ) -> Dict:
        if answer_length < 10:
            return {
                "pass": False, "depth_score": 0.3, "confidence": 0.8,
                "feedback": "Answer too brief.",
                "answer_length": answer_length, "needs_followup": True,
            }

        llm = self._llm_evaluate_no_reference(question, user_answer)
        if llm:
            passed = llm["score"] >= self.pass_threshold
            return {
                "pass": passed, "depth_score": llm["score"], "confidence": llm["confidence"],
                "feedback": llm["feedback"],
                "answer_length": answer_length, "needs_followup": not passed,
            }

        return {
            "pass": answer_length >= 15, "depth_score": 0.5, "confidence": 0.4,
            "feedback": "Evaluation inconclusive.",
            "answer_length": answer_length, "needs_followup": False,
        }

    # ------------------------------------------------------------------
    # Similarity helpers
    # ------------------------------------------------------------------

    def _semantic_similarity(self, text1: str, text2: str) -> float:
        try:
            emb1, emb2 = self.embedder.encode(
                [text1, text2], normalize_embeddings=True, convert_to_numpy=True
            )
            return float(max(0.0, min(1.0, np.dot(emb1, emb2))))
        except Exception:
            return 0.5

    def _keyword_overlap(self, user_answer: str, reference: str) -> float:
        def extract(text: str):
            words = re.findall(r"\b[a-zA-Z0-9_]{3,}\b", text.lower())
            return {w for w in words if w not in _STOP_WORDS}

        user_kw = extract(user_answer)
        ref_kw  = extract(reference)
        if not ref_kw:
            return 0.5

        intersection = len(user_kw & ref_kw)
        union        = len(user_kw | ref_kw)
        return 0.5 * (intersection / union if union else 0.0) + 0.5 * (intersection / len(ref_kw))

    # ------------------------------------------------------------------
    # LLM calls
    # ------------------------------------------------------------------

    def _call_llm_json(self, prompt: str, max_tokens: int = 150) -> Optional[Dict]:
        """Call LLM, parse and return the first JSON object in the response."""
        try:
            resp  = self.llm(
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1,
                max_tokens=max_tokens,
            )
            text  = resp["choices"][0]["message"]["content"]
            match = re.search(r"\{.*?\}", text, re.DOTALL)
            if match:
                return json.loads(match.group(0))
        except Exception:
            pass
        return None

    def _llm_combined_eval(
        self,
        question: str,
        user_answer: str,
        reference_answer: Optional[str],
        is_followup: bool,
    ) -> Optional[Dict]:
        """
        Single LLM call → score + feedback + flow decision.
        Replaces the two separate LLM calls used previously.
        """
        ref_line = (
            f"EXPECTED ANSWER: {reference_answer[:300]}\n"
            if reference_answer and not is_followup else ""
        )
        prompt = f"""You are a senior technical interviewer evaluating a candidate's answer.

QUESTION: {question[:300]}
{ref_line}CANDIDATE ANSWER: {user_answer[:400]}

Return JSON only (no other text):
{{
  "score": <float 0.0-1.0>,
  "confidence": <float 0.0-1.0>,
  "feedback": "<one sentence>",
  "decision": "<new_topic|same_topic|deep_dive>",
  "remarks": "<one sentence reason>",
  "score_reason": "<brief reason>"
}}

Scoring: 0.0=wrong, 0.3=partial, 0.6=adequate, 0.8=good, 1.0=excellent
Decision:
  deep_dive  = strong answer, worth probing deeper
  same_topic = weak/vague, needs follow-up on same topic
  new_topic  = adequate or better, move on

JSON:"""

        result = self._call_llm_json(prompt, max_tokens=200)
        if result:
            decision = str(result.get("decision", "new_topic")).lower()
            if decision not in ("deep_dive", "same_topic", "new_topic"):
                decision = "new_topic"
            return {
                "score":        float(result.get("score", 0.5)),
                "confidence":   float(result.get("confidence", 0.6)),
                "feedback":     str(result.get("feedback", ""))[:150],
                "decision":     decision,
                "remarks":      str(result.get("remarks", ""))[:200],
                "score_reason": str(result.get("score_reason", ""))[:200],
            }
        return None

    def _llm_quick_check(self, question: str, reference: str, user_answer: str) -> Optional[Dict]:
        prompt = f"""Evaluate this technical interview answer.

QUESTION: {question[:200]}
EXPECTED: {reference[:200]}
CANDIDATE: {user_answer[:200]}

Rate 0.0-1.0. Return JSON only: {{"score": 0.0, "confidence": 0.0, "feedback": "brief"}}

JSON:"""
        result = self._call_llm_json(prompt, max_tokens=100)
        if result:
            return {
                "score":      float(result.get("score", 0.5)),
                "confidence": float(result.get("confidence", 0.5)),
                "feedback":   str(result.get("feedback", ""))[:100],
            }
        return None

    def _llm_evaluate_no_reference(self, question: str, user_answer: str) -> Optional[Dict]:
        prompt = f"""Evaluate this interview answer (no reference available).

QUESTION: {question[:200]}
CANDIDATE: {user_answer[:200]}

Rate 0.0-1.0. Return JSON: {{"score": 0.0, "confidence": 0.0, "feedback": "brief"}}

JSON:"""
        result = self._call_llm_json(prompt, max_tokens=100)
        if result:
            return {
                "score":      float(result.get("score", 0.5)),
                "confidence": float(result.get("confidence", 0.5)),
                "feedback":   str(result.get("feedback", ""))[:100],
            }
        return None

    def _llm_flow_decision(self, question: str, user_answer: str) -> Optional[Dict]:
        prompt = f"""Evaluate this technical interview answer for flow decision.

QUESTION: {question[:250]}
CANDIDATE ANSWER: {user_answer[:400]}

Score 0.0-1.0 and decide:
  deep_dive=strong, same_topic=weak/vague, new_topic=adequate

Return JSON only:
{{"decision": "...", "remarks": "brief", "score": 0.0, "score_reason": "brief"}}

JSON:"""
        result = self._call_llm_json(prompt, max_tokens=120)
        if result:
            decision = str(result.get("decision", "new_topic")).lower()
            if decision not in ("deep_dive", "same_topic", "new_topic"):
                decision = "new_topic"
            return {
                "decision":     decision,
                "remarks":      str(result.get("remarks", ""))[:200],
                "score":        float(result.get("score", 0.5)),
                "score_reason": str(result.get("score_reason", ""))[:200],
            }
        return None