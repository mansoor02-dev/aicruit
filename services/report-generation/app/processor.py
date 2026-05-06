"""
Aggregation logic — works on ScoredEntry list (already scored 0–10).
Also handles LLM-based scoring of raw entries.
"""

import sys
sys.path.insert(0, "/app")

from typing import Dict, List, Tuple
import json
from pydantic import BaseModel

from .models import QuestionEntry, ScoredEntry
from .utils import clamp, scale_to_ten
from shared.llm_client import LLMClient


# ── LLM-based scoring ───────────────────────────────────────────────────────

_SCORE_PROMPT = """You are a senior technical interviewer.
Evaluate the candidate's answer to the interview question below.

QUESTION: {question}
CANDIDATE ANSWER: {answer}

Return JSON only (no other text):
{{
  "score": <integer 1-5>,
  "remark": "<one or two sentences explaining the score>"
}}

Scoring guide:
  1 = completely wrong or no real answer
  2 = mostly incorrect, major gaps
  3 = partially correct, some gaps
  4 = mostly correct, minor gaps
  5 = excellent, thorough answer"""


class ScoreResult(BaseModel):
    score: int
    remark: str


def score_entry_with_llm(llm_client: LLMClient, entry: QuestionEntry) -> ScoredEntry:
    """Score a single Q&A pair using the LLM. Falls back to the provided
    ai_score / remarks if the LLM call fails or if they were already supplied."""

    # If both score and remarks were supplied by the caller, honour them.
    if entry.ai_score is not None and entry.remarks is not None:
        return ScoredEntry(
            q=entry.q,
            a=entry.a,
            category=entry.category,
            score=scale_to_ten(float(entry.ai_score)),
            remark=entry.remarks,
        )

    # Ask the LLM
    prompt = _SCORE_PROMPT.format(question=entry.q[:400], answer=entry.a[:600])
    
    try:
        result = llm_client.complete(
            prompt=prompt,
            system="You are a technical interview evaluator. Respond with JSON only.",
            max_tokens=150
        )
        
        # Extract JSON from response
        try:
            parsed = json.loads(result.strip())
            raw_score = float(parsed.get("score", 3))
            remark = str(parsed.get("remark", "No remark."))[:250]
        except (json.JSONDecodeError, ValueError):
            raw_score = 3.0
            remark = "Unable to parse LLM response"
    except Exception:
        # Fallback: use provided values or sensible defaults
        raw_score = float(entry.ai_score) if entry.ai_score is not None else 3.0
        remark = entry.remarks if entry.remarks else "LLM unavailable — default evaluation."

    return ScoredEntry(
        q=entry.q,
        a=entry.a,
        category=entry.category,
        score=clamp(scale_to_ten(raw_score)),
        remark=remark,
    )


def score_all_entries(llm_client: LLMClient, entries: List[QuestionEntry]) -> List[ScoredEntry]:
    """Score every entry (via LLM when needed)."""
    return [score_entry_with_llm(llm_client, e) for e in entries]


# ── Aggregation ──────────────────────────────────────────────────────────────

def compute_overall_score(entries: List[ScoredEntry]) -> float:
    """Average of all scores (already /10)."""
    return round(sum(e.score for e in entries) / len(entries), 1)


def compute_category_scores(entries: List[ScoredEntry]) -> List[Tuple[str, float]]:
    """Group by category, return (name, avg_score) pairs."""
    buckets: Dict[str, List[float]] = {}
    for e in entries:
        buckets.setdefault(e.category, []).append(e.score)

    return [
        (cat, round(sum(scores) / len(scores), 1))
        for cat, scores in buckets.items()
    ]
