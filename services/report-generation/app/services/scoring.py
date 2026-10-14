"""Async Q&A scoring and deterministic report calculations."""

import asyncio
import logging
from typing import Dict, List, Tuple

from ..llm.client import LLMClient
from ..prompts.report_prompts import SCORE_PROMPT
from ..schemas.reports import QuestionEntry, ScoredEntry, ScoreResult
from ..utils.scores import clamp, scale_to_ten

logger = logging.getLogger(__name__)
MAX_CONCURRENT_SCORE_REQUESTS = 4


async def score_entry_with_llm(
    llm_client: LLMClient,
    entry: QuestionEntry,
    semaphore: asyncio.Semaphore | None = None,
) -> ScoredEntry:
    """Score one entry, preserving supplied scores and using a safe fallback."""
    supplied_score = entry.ai_score
    supplied_remark = (entry.remarks or "").strip()
    if supplied_score is not None and supplied_remark:
        return ScoredEntry(
            q=entry.q,
            a=entry.a,
            category=entry.category,
            score=scale_to_ten(float(supplied_score)),
            remark=supplied_remark[:250],
        )

    if not entry.a.strip():
        return ScoredEntry(
            q=entry.q,
            a=entry.a,
            category=entry.category,
            score=scale_to_ten(float(supplied_score or 1)),
            remark=supplied_remark or "No answer was provided.",
        )

    values = {
        "question": entry.q[:400],
        "answer": entry.a[:1200],
        "existing_score": supplied_score if supplied_score is not None else "none",
        "existing_remark": supplied_remark or "none",
    }
    try:
        if semaphore is None:
            result = await llm_client.complete_structured(
                SCORE_PROMPT,
                ScoreResult,
                values,
                max_tokens=300,
            )
        else:
            async with semaphore:
                result = await llm_client.complete_structured(
                    SCORE_PROMPT,
                    ScoreResult,
                    values,
                    max_tokens=300,
                )
        raw_score = supplied_score if supplied_score is not None else result.score
        remark = result.remark
    except Exception as exc:
        logger.warning(
            "Unable to generate a valid score for category %r (%s); "
            "using deterministic fallback",
            entry.category,
            type(exc).__name__,
        )
        raw_score = supplied_score if supplied_score is not None else 3
        remark = supplied_remark or (
            "Evaluation unavailable; a neutral score was used."
            if supplied_score is None
            else "Evaluation remark unavailable; the supplied score was retained."
        )

    return ScoredEntry(
        q=entry.q,
        a=entry.a,
        category=entry.category,
        score=clamp(scale_to_ten(float(raw_score))),
        remark=remark[:250],
    )


async def score_all_entries(
    llm_client: LLMClient,
    entries: List[QuestionEntry],
) -> List[ScoredEntry]:
    """Score entries with bounded concurrency, preserving request order."""
    semaphore = asyncio.Semaphore(MAX_CONCURRENT_SCORE_REQUESTS)
    return await asyncio.gather(
        *(
            score_entry_with_llm(llm_client, entry, semaphore)
            for entry in entries
        )
    )


def compute_overall_score(entries: List[ScoredEntry]) -> float:
    """Average normalized scores, rounded to one decimal place."""
    if not entries:
        raise ValueError("At least one scored entry is required")
    return round(sum(entry.score for entry in entries) / len(entries), 1)


def compute_category_scores(
    entries: List[ScoredEntry],
) -> List[Tuple[str, float]]:
    """Calculate deterministic per-category average scores."""
    buckets: Dict[str, List[float]] = {}
    for entry in entries:
        buckets.setdefault(entry.category, []).append(entry.score)
    return [
        (category, round(sum(scores) / len(scores), 1))
        for category, scores in buckets.items()
    ]
