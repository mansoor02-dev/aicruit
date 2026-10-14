"""Orchestrate scoring and report assembly without owning persistence."""

import asyncio
from typing import Sequence

from ..llm.client import LLMClient
from ..schemas.reports import QuestionEntry, ReportResponse
from .candidate_report import build_candidate_report
from .recruiter_report import build_recruiter_report
from .scoring import score_all_entries


async def generate_report(
    llm_client: LLMClient,
    entries: Sequence[QuestionEntry],
) -> ReportResponse:
    """Score Q&A, calculate aggregates, then build both audience reports."""
    scored = await score_all_entries(llm_client, list(entries))
    recruiter_report, candidate_report = await asyncio.gather(
        build_recruiter_report(llm_client, scored),
        build_candidate_report(llm_client, scored),
    )
    return ReportResponse(
        recruiter_report=recruiter_report,
        candidate_report=candidate_report,
    )
