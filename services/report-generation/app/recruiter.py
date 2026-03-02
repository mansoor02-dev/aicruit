"""
Recruiter report generation logic — uses LLM for personalised overall remark.
"""

from typing import Any, List

from .models import ScoredEntry, RecruiterReport, CategoryScore
from .processor import compute_overall_score, compute_category_scores
from .llm_loader import call_llm_json


_REMARK_PROMPT = """You are an expert HR analyst writing a concise summary for a recruiter.

Below is the interview evaluation data (score is out of 10):

{entries_text}

Overall score: {overall_score}/10

Write a 2-3 sentence professional summary for the recruiter.
Return JSON only:
{{
  "overall_remark": "<your summary>"
}}

JSON:"""


def _format_entries_for_prompt(entries: List[ScoredEntry]) -> str:
    lines = []
    for e in entries:
        lines.append(f"- [{e.category}] Q: {e.q[:80]}  |  Score: {e.score}/10  |  {e.remark[:100]}")
    return "\n".join(lines)


def _generate_overall_remark(llm: Any, entries: List[ScoredEntry], overall_score: float) -> str:
    """Ask the LLM for a professional recruiter summary. Falls back to a
    score-based template if the LLM is unavailable."""
    prompt = _REMARK_PROMPT.format(
        entries_text=_format_entries_for_prompt(entries),
        overall_score=overall_score,
    )
    result = call_llm_json(llm, prompt, max_tokens=250)

    if result and result.get("overall_remark"):
        return str(result["overall_remark"])[:500]

    # Fallback
    if overall_score >= 8.0:
        return "Excellent performance across all areas. Strongly recommended."
    if overall_score >= 6.0:
        return "Solid understanding with some areas for growth. Good potential."
    if overall_score >= 4.0:
        return "Basic grasp with notable gaps. Further evaluation recommended."
    return "Significant gaps identified. Further development needed."


def build_recruiter_report(llm: Any, entries: List[ScoredEntry]) -> RecruiterReport:
    """Assemble the full recruiter report."""
    overall_score = compute_overall_score(entries)
    category_scores = [
        CategoryScore(category=cat, score=score)
        for cat, score in compute_category_scores(entries)
    ]
    overall_remark = _generate_overall_remark(llm, entries, overall_score)

    return RecruiterReport(
        overall_score=overall_score,
        category_scores=category_scores,
        overall_remark=overall_remark,
    )
