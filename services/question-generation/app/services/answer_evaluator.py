import asyncio
import logging
import re
from typing import Dict, Optional, Tuple

import numpy as np
from app.schemas.llm import AnswerEvaluation
from app.services.embedding import GeminiEmbedder
from app.services.llm_client import LLMClient

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# "I don't know" detection â€” short-circuit before any LLM / embedding call
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
    "needs_followup": False,   # No follow-up â€” just move on
}

_DONT_KNOW_FLOW: Dict = {
    "decision": "new_topic",
    "remarks": "Candidate is not familiar with this topic â€” moving on.",
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

    "I don't know" and very short answers are handled without LLM calls.
    """

    PASS_THRESHOLD = 0.55

    def __init__(
        self,
        embedder: GeminiEmbedder,
        pass_threshold: float = PASS_THRESHOLD,
        llm_client: Optional[LLMClient] = None,
    ):
        self.embedder = embedder
        self.llm_client = llm_client or LLMClient()
        self.pass_threshold = pass_threshold

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def evaluate_combined(
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

        # Very short but not "don't know" â€” skip LLM
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

        combined = await self._llm_combined_eval(
            question, user_answer, reference_answer, is_followup
        )

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
        ev = await self._heuristic_eval(
            user_answer, reference_answer, answer_length
        )
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

    async def _heuristic_eval(
        self,
        user_answer: str,
        reference_answer: Optional[str],
        answer_length: int,
    ) -> Dict:
        if reference_answer:
            sem = await asyncio.to_thread(
                self._semantic_similarity, user_answer, reference_answer
            )
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

    async def _call_llm_json(
        self,
        prompt: str,
        response_model: type[AnswerEvaluation],
        max_tokens: int = 150,
    ) -> Optional[Dict]:
        """Call the shared client and return a schema-validated response."""
        try:
            result = await self.llm_client.complete_json(
                prompt=prompt,
                response_model=response_model,
                max_tokens=max_tokens,
            )
            return result.model_dump()
        except Exception:
            logger.warning(
                "Structured answer evaluation failed (%s)",
                response_model.__name__,
                exc_info=True,
            )
        return None

    async def _llm_combined_eval(
        self,
        question: str,
        user_answer: str,
        reference_answer: Optional[str],
        is_followup: bool,
    ) -> Optional[Dict]:
        """
        Single LLM call â†’ score + feedback + flow decision.
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

        result = await self._call_llm_json(
            prompt, AnswerEvaluation, max_tokens=200
        )
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
