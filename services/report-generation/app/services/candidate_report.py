"""Candidate-facing feedback generation."""

import logging
from typing import List

from ..llm.client import LLMClient
from ..prompts.report_prompts import CANDIDATE_PROMPT
from ..schemas.reports import CandidateReport, ScoredEntry

logger = logging.getLogger(__name__)


def _format_entries(entries: List[ScoredEntry]) -> str:
    return "\n".join(
        f"- [{entry.category}] Question: {entry.q[:100]} | "
        f"Evidence: {entry.remark[:180]}"
        for entry in entries
    )


async def build_candidate_report(
    llm_client: LLMClient,
    entries: List[ScoredEntry],
) -> CandidateReport:
    """Generate validated feedback, falling back to evidence-based templates."""
    try:
        return await llm_client.complete_structured(
            CANDIDATE_PROMPT,
            CandidateReport,
            {"entries_text": _format_entries(entries)},
            max_tokens=500,
        )
    except Exception as exc:
        logger.warning(
            "Unable to generate valid candidate feedback (%s); "
            "using deterministic fallback",
            type(exc).__name__,
        )
        return _fallback_report(entries)


def _fallback_report(entries: List[ScoredEntry]) -> CandidateReport:
    strengths = [
        f"Your response on {entry.category} showed solid understanding."
        for entry in entries
        if entry.score >= 7.0
    ]
    improvements = [
        f"Practise explaining key concepts in {entry.category} with specific examples."
        for entry in entries
        if entry.score < 5.0
    ]
    return CandidateReport(
        strengths=(
            strengths
            or ["You made an effort to respond to the interview questions."]
        )[:3],
        improvements=(
            improvements
            or ["Continue practising technical questions and explaining your reasoning."]
        )[:3],
    )
