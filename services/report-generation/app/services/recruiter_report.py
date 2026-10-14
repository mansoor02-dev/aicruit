"""Recruiter-facing summary generation."""

import logging
from typing import List

from ..llm.client import LLMClient
from ..prompts.report_prompts import RECRUITER_PROMPT
from ..schemas.reports import (
    CategoryScore,
    RecruiterReport,
    RecruiterSummary,
    ScoredEntry,
)
from .scoring import compute_category_scores, compute_overall_score

logger = logging.getLogger(__name__)


def _format_entries(entries: List[ScoredEntry]) -> str:
    return "\n".join(
        f"- [{entry.category}] Q: {entry.q[:80]} | "
        f"Score: {entry.score}/10 | {entry.remark[:150]}"
        for entry in entries
    )


async def build_recruiter_report(
    llm_client: LLMClient,
    entries: List[ScoredEntry],
) -> RecruiterReport:
    """Build deterministic score fields and a validated narrative remark."""
    overall_score = compute_overall_score(entries)
    category_scores = [
        CategoryScore(category=category, score=score)
        for category, score in compute_category_scores(entries)
    ]
    try:
        result = await llm_client.complete_structured(
            RECRUITER_PROMPT,
            RecruiterSummary,
            {
                "entries_text": _format_entries(entries),
                "overall_score": overall_score,
                "category_scores": [score.model_dump() for score in category_scores],
            },
            max_tokens=400,
        )
        remark = result.overall_remark
    except Exception as exc:
        logger.warning(
            "Unable to generate a valid recruiter summary (%s); "
            "using deterministic fallback",
            type(exc).__name__,
        )
        remark = _fallback_remark(overall_score)

    return RecruiterReport(
        overall_score=overall_score,
        category_scores=category_scores,
        overall_remark=remark,
    )


def _fallback_remark(overall_score: float) -> str:
    if overall_score >= 8.0:
        return "Excellent performance across the evaluated areas."
    if overall_score >= 6.0:
        return "Solid understanding with some areas for growth."
    if overall_score >= 4.0:
        return "Basic understanding with notable areas for improvement."
    return "Significant gaps were observed in the evaluated responses."
