"""Pure evaluation helpers: regexes, constants, short-circuits and scoring.

All functions here are deterministic and side-effect free. The async
heuristic orchestration (which needs embeddings) lives in ``app.llm.chains``.
"""

from __future__ import annotations

import re
from typing import Any

from app.schemas.llm import AnswerEvaluation

PASS_THRESHOLD = 0.55

# "I don't know" detection - short-circuit before any LLM / embedding call.
# Kept verbatim from the original implementation.
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

_STOP_WORDS = {"the", "and", "for", "this", "that", "with", "from", "are", "was"}

_DONT_KNOW_EVAL: dict[str, Any] = {
    "pass": False,
    "depth_score": 0.0,
    "confidence": 1.0,
    "feedback": "Candidate is not familiar with this topic.",
    "answer_length": 0,
    "needs_followup": False,  # No follow-up - just move on
}

_DONT_KNOW_FLOW: dict[str, Any] = {
    "decision": "new_topic",
    "remarks": "Candidate is not familiar with this topic - moving on.",
    "score_value": 0.0,
    "score_reason": "Explicit unfamiliarity stated",
}


def is_empty_answer(inputs: dict[str, Any]) -> bool:
    """Branch condition: answer shorter than 3 chars (no LLM)."""
    answer = inputs.get("user_answer") or ""
    return len(answer.strip()) < 3


def is_dont_know_answer(inputs: dict[str, Any]) -> bool:
    """Branch condition: explicit unfamiliarity (no LLM)."""
    answer = inputs.get("user_answer") or ""
    return bool(_DONT_KNOW_RE.search(answer.strip()))


def is_brief_answer(inputs: dict[str, Any]) -> bool:
    """Branch condition: fewer than 5 words (no LLM)."""
    answer = inputs.get("user_answer") or ""
    return len(answer.split()) < 5


def empty_answer_result() -> tuple[dict[str, Any], dict[str, Any]]:
    """Fixed (evaluation, flow) pair for empty/minimal answers."""
    evaluation = {
        "pass": False,
        "depth_score": 0.0,
        "confidence": 1.0,
        "feedback": "Empty or very short answer.",
        "answer_length": 0,
        "needs_followup": True,
    }
    flow = {
        "decision": "same_topic",
        "remarks": "Answer too brief",
        "score_value": 0.1,
        "score_reason": "Empty or minimal answer",
    }
    return evaluation, flow


def dont_know_result() -> tuple[dict[str, Any], dict[str, Any]]:
    """Fixed (evaluation, flow) pair for explicit unfamiliarity."""
    return _DONT_KNOW_EVAL.copy(), _DONT_KNOW_FLOW.copy()


def brief_answer_result(answer_length: int) -> tuple[dict[str, Any], dict[str, Any]]:
    """Fixed (evaluation, flow) pair for answers shorter than 5 words."""
    evaluation = {
        "pass": False,
        "depth_score": 0.2,
        "confidence": 0.9,
        "feedback": "Answer too brief to evaluate properly.",
        "answer_length": answer_length,
        "needs_followup": True,
    }
    flow = {
        "decision": "same_topic",
        "remarks": "Answer too brief",
        "score_value": 0.2,
        "score_reason": f"Only {answer_length} words",
    }
    return evaluation, flow


def neutral_result() -> tuple[dict[str, Any], dict[str, Any]]:
    """Neutral (evaluation, flow) pair when evaluation itself errors.

    Used by the graph node so one unexpected failure never breaks question
    delivery; it routes to a new topic.
    """
    evaluation = {
        "pass": True,
        "depth_score": 0.5,
        "confidence": 0.0,
        "feedback": "Evaluation unavailable.",
        "answer_length": 0,
        "needs_followup": False,
    }
    flow = {
        "decision": "new_topic",
        "remarks": "Evaluation unavailable",
        "score_value": 0.5,
        "score_reason": "Evaluation unavailable",
    }
    return evaluation, flow


def map_llm_evaluation(
    result: AnswerEvaluation | dict[str, Any],
    answer_length: int,
    pass_threshold: float = PASS_THRESHOLD,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Map a structured LLM evaluation to the (evaluation, flow) shape."""
    if isinstance(result, dict):
        data = dict(result)
    else:
        data = result.model_dump()
    decision = str(data.get("decision", "new_topic")).lower()
    if decision not in ("deep_dive", "same_topic", "new_topic"):
        decision = "new_topic"
    score = float(data.get("score", 0.5))
    passed = score >= pass_threshold
    evaluation = {
        "pass": passed,
        "depth_score": round(score, 3),
        "confidence": float(data.get("confidence", 0.6)),
        "feedback": str(data.get("feedback", "")),
        "answer_length": answer_length,
        "needs_followup": not passed,
    }
    flow = {
        "decision": decision,
        "remarks": str(data.get("remarks", "")),
        "score_value": score,
        "score_reason": str(data.get("score_reason", "LLM evaluation")),
    }
    return evaluation, flow


def keyword_overlap(user_answer: str, reference: str) -> float:
    """Keyword overlap between an answer and a reference answer."""

    def extract(text: str) -> set[str]:
        words = re.findall(r"\b[a-zA-Z0-9_]{3,}\b", text.lower())
        return {w for w in words if w not in _STOP_WORDS}

    user_kw = extract(user_answer)
    ref_kw = extract(reference)
    if not ref_kw:
        return 0.5

    intersection = len(user_kw & ref_kw)
    union = len(user_kw | ref_kw)
    return 0.5 * (intersection / union if union else 0.0) + 0.5 * (
        intersection / len(ref_kw)
    )


def heuristic_result(
    depth_score: float, answer_length: int, passed: bool
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Build the (evaluation, flow) pair for a heuristic depth score."""
    evaluation = {
        "pass": passed,
        "depth_score": depth_score,
        "confidence": 0.5,
        "feedback": (
            "Answer demonstrates understanding."
            if passed
            else "Answer lacks key concepts."
        ),
        "answer_length": answer_length,
        "needs_followup": not passed,
    }
    flow = {
        "decision": "new_topic" if passed else "same_topic",
        "remarks": "Heuristic evaluation (LLM unavailable)",
        "score_value": depth_score,
        "score_reason": "Embedding + keyword score",
    }
    return evaluation, flow
