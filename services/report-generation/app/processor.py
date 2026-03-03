"""
Aggregation logic — works on ScoredEntry list (already scored 0–10).
Also handles LLM-based scoring of raw entries.
"""

from typing import Any, Dict, List, Tuple

from .models import QuestionEntry, ScoredEntry
from .llm_loader import call_llm_json
from .utils import clamp, scale_to_ten


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
  5 = excellent, thorough answer

JSON:"""


def score_entry_with_llm(llm: Any, entry: QuestionEntry) -> ScoredEntry:
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
    result = call_llm_json(llm, prompt, max_tokens=150)

    if result:
        raw_score = float(result.get("score", 3))
        remark = str(result.get("remark", "No remark."))[:250]
    else:
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


def score_all_entries(llm: Any, entries: List[QuestionEntry]) -> List[ScoredEntry]:
    """Score every entry (via LLM when needed)."""
    return [score_entry_with_llm(llm, e) for e in entries]


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
