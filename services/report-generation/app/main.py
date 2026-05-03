"""
Report Generation Microservice — FastAPI entry point.
Scoring and remarks are LLM-powered (Gemini / OpenRouter).
"""

import asyncio
import logging
from functools import partial

from fastapi import FastAPI, HTTPException

import sys
sys.path.insert(0, "/app")

from .models import ReportRequest, ReportResponse
from .processor import score_all_entries
from .recruiter import build_recruiter_report
from .candidate import build_candidate_report
from shared.llm_client import LLMClient

# ── Logging ──────────────────────────────────────────────────────────────────
logging.basicConfig(level=logging.INFO)

# ── App ──────────────────────────────────────────────────────────────────────

app = FastAPI(
    title="Interview Report Generator",
    description="LLM-powered interview report generation.",
    version="2.0.0",
)

# LLM is lazy-loaded from shared/ on first request
_llm_client = None

# ── Routes ───────────────────────────────────────────────────────────────────

@app.post("/generate-report", response_model=ReportResponse, summary="Generate interview reports")
async def generate_report(request: ReportRequest) -> ReportResponse:
    """Score Q&A via LLM, then generate recruiter + candidate reports."""
    global _llm_client
    if _llm_client is None:
        _llm_client = LLMClient()
    
    loop = asyncio.get_event_loop()

    try:
        # 1. Score every entry (LLM calls are blocking -> run in thread)
        scored = await loop.run_in_executor(
            None, partial(score_all_entries, _llm_client, request.data)
        )

        # 2. Build reports (also involve LLM calls)
        recruiter_report = await loop.run_in_executor(
            None, partial(build_recruiter_report, _llm_client, scored)
        )
        candidate_report = await loop.run_in_executor(
            None, partial(build_candidate_report, _llm_client, scored)
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Report generation failed: {e}")

    return ReportResponse(
        recruiter_report=recruiter_report,
        candidate_report=candidate_report,
    )


@app.get("/health", summary="Health check", include_in_schema=False)
async def health():
    return {"status": "ok"}
