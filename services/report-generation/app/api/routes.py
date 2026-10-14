"""HTTP routes for interview report generation."""

import logging

from fastapi import APIRouter, Depends, HTTPException

from ..llm.dependencies import get_llm_client
from ..llm.client import LLMClient
from ..schemas.reports import ReportRequest, ReportResponse
from ..services.report_service import generate_report as build_report

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post(
    "/generate-report",
    response_model=ReportResponse,
    summary="Generate interview reports",
)
async def generate_report(
    request: ReportRequest,
    llm_client: LLMClient = Depends(get_llm_client),
) -> ReportResponse:
    """Score Q&A and return recruiter and candidate reports."""
    try:
        return await build_report(llm_client, request.data)
    except Exception as exc:
        logger.exception("Report generation failed")
        raise HTTPException(
            status_code=500,
            detail="Report generation failed",
        ) from exc


@router.get("/health", summary="Health check", include_in_schema=False)
async def health():
    return {"status": "ok"}
