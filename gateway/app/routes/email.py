"""
Email routes — drafting (LLM-powered) and sending (SMTP).

All routes are RECRUITER/ADMIN only.
"""
from __future__ import annotations

import logging
import os
from typing import Any, Dict, List, Optional
from uuid import UUID

import httpx
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr
from sqlalchemy.orm import Session

from ..core.db import get_db_session
from ..core.security import RoleChecker
from ..models.application_model import ApplicationModel
from ..models.company import CompanyModel
from ..models.interview_model import InterviewModel
from ..models.job_model import JobModel
from ..models.job_stage_model import JobStageModel
from ..models.recruiter import RecruiterModel
from ..models.report_model import ReportModel
from ..models.user import UserModel
from ..services.email import send_email

logger = logging.getLogger(__name__)

router = APIRouter()
allow_recruiters = RoleChecker(["RECRUITER", "ADMIN"])

QUESTION_GEN_URL = os.getenv("QUESTION_GEN_URL", "http://localhost:8010")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


class _SafeDict(dict):
    """dict subclass for str.format_map: missing keys → '{key}' literal."""

    def __missing__(self, key):  # type: ignore[override]
        return "{" + key + "}"


def _render_template(template: str, vars: Dict[str, Any]) -> str:
    if not template:
        return ""
    try:
        return template.format_map(_SafeDict({k: ("" if v is None else str(v)) for k, v in vars.items()}))
    except Exception as e:
        logger.warning(f"Template render failed ({e}); returning raw template")
        return template


def _get_recruiter_company(db: Session, user: UserModel) -> Optional[CompanyModel]:
    rec = db.query(RecruiterModel).filter(RecruiterModel.id == user.id).first()
    if not rec:
        return None
    return db.query(CompanyModel).filter(CompanyModel.id == rec.company_id).first()


def _load_application_context(
    db: Session,
    application_id: UUID,
    include_interview_score: bool = False,
) -> Dict[str, Any]:
    """Load candidate + job context (and optional report scores) for an application."""
    app_row = (
        db.query(ApplicationModel)
        .filter(ApplicationModel.id == application_id)
        .first()
    )
    if not app_row:
        raise HTTPException(status_code=404, detail="Application not found")

    job = db.query(JobModel).filter(JobModel.id == app_row.job_id).first()
    company = (
        db.query(CompanyModel).filter(CompanyModel.id == job.company_id).first()
        if job else None
    )

    stage_name: Optional[str] = None
    if app_row.stage_id:
        stage = (
            db.query(JobStageModel)
            .filter(JobStageModel.id == app_row.stage_id)
            .first()
        )
        if stage:
            stage_name = stage.name

    scheduled_at: Optional[str] = None
    interview = (
        db.query(InterviewModel)
        .filter(InterviewModel.application_id == application_id)
        .order_by(InterviewModel.scheduled_at.desc())
        .first()
    )
    if interview and interview.scheduled_at:
        scheduled_at = interview.scheduled_at.isoformat()

    category_scores: Optional[List[Dict[str, Any]]] = None
    overall_score: Optional[float] = None
    if include_interview_score and interview is not None:
        report = (
            db.query(ReportModel)
            .filter(ReportModel.interview_id == interview.id)
            .order_by(ReportModel.created_at.desc())
            .first()
        )
        if report is not None:
            if report.category_scores:
                # category_scores stored as JSONB list of {category, score}
                cs = report.category_scores
                if isinstance(cs, list):
                    category_scores = [
                        {
                            "category": str(item.get("category", "")),
                            "score": float(item.get("score", 0) or 0),
                        }
                        for item in cs
                        if isinstance(item, dict)
                    ]
            if report.overall_score is not None:
                try:
                    overall_score = float(report.overall_score)
                except (TypeError, ValueError):
                    overall_score = None

    return {
        "application": app_row,
        "job": job,
        "company": company,
        "candidate_name": app_row.applicant_name or "Candidate",
        "candidate_email": app_row.applicant_email or "",
        "job_title": job.title if job else "",
        "company_name": company.name if company else "AIcruit",
        "stage_name": stage_name,
        "scheduled_at": scheduled_at,
        "category_scores": category_scores,
        "overall_score": overall_score,
    }


def _call_question_gen_draft(payload: Dict[str, Any]) -> Dict[str, str]:
    """Call question-generation /draft-email and return {subject, body}."""
    try:
        with httpx.Client(timeout=60.0) as client:
            resp = client.post(f"{QUESTION_GEN_URL}/draft-email", json=payload)
            resp.raise_for_status()
            return resp.json()
    except httpx.HTTPStatusError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Email drafting service error: {exc.response.status_code} – {exc.response.text}",
        )
    except httpx.RequestError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Could not reach email drafting service: {exc}",
        )


def _append_performance_summary(body: str, category_scores: Optional[List[Dict[str, Any]]]) -> str:
    """Append a 'Performance Summary' section to a body using category scores."""
    if not category_scores:
        return body
    lines = ["", "Performance Summary:"]
    for cs in category_scores:
        cat = str(cs.get("category", "")).strip()
        try:
            score = float(cs.get("score", 0) or 0)
        except (TypeError, ValueError):
            score = 0.0
        if cat:
            lines.append(f"- {cat}: {score:.1f}/10")
    return f"{body.rstrip()}\n" + "\n".join(lines)


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class DraftRequest(BaseModel):
    scenario: str
    application_id: Optional[UUID] = None
    custom_instructions: Optional[str] = None
    include_interview_score: bool = False


class DraftResponse(BaseModel):
    subject: str
    body: str


class SendRequest(BaseModel):
    to: List[EmailStr]
    subject: str
    body: str
    application_id: Optional[UUID] = None


class SendResponse(BaseModel):
    sent: bool
    to: List[str]


class BulkSendRequest(BaseModel):
    job_id: UUID
    status: Optional[str] = None
    stage_id: Optional[UUID] = None
    subject_template: str
    body_template: str
    include_interview_score: bool = False


class BulkSendResponse(BaseModel):
    sent: int
    failed: int
    errors: List[Dict[str, Any]]


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@router.post("/draft", response_model=DraftResponse)
def draft_email(
    payload: DraftRequest,
    db: Session = Depends(get_db_session),
    current_user: UserModel = Depends(allow_recruiters),
):
    qg_payload: Dict[str, Any] = {
        "scenario": payload.scenario,
        "candidate_name": "Candidate",
        "job_title": "the role",
        "company_name": "AIcruit",
        "custom_instructions": payload.custom_instructions,
    }

    if payload.application_id:
        ctx = _load_application_context(
            db, payload.application_id, include_interview_score=payload.include_interview_score
        )
        qg_payload.update({
            "candidate_name": ctx["candidate_name"],
            "job_title": ctx["job_title"] or "the role",
            "company_name": ctx["company_name"],
            "scheduled_at": ctx["scheduled_at"],
            "stage_name": ctx["stage_name"],
        })
        if payload.include_interview_score:
            qg_payload["category_scores"] = ctx["category_scores"]
            qg_payload["overall_score"] = ctx["overall_score"]
    else:
        # Fall back to the recruiter's own company name when no application is given
        company = _get_recruiter_company(db, current_user)
        if company:
            qg_payload["company_name"] = company.name

    result = _call_question_gen_draft(qg_payload)
    return DraftResponse(subject=result.get("subject", ""), body=result.get("body", ""))


@router.post("/send", response_model=SendResponse)
def send_email_route(
    payload: SendRequest,
    db: Session = Depends(get_db_session),
    current_user: UserModel = Depends(allow_recruiters),
):
    try:
        result = send_email(
            to=[str(addr) for addr in payload.to],
            subject=payload.subject,
            body=payload.body,
        )
    except RuntimeError as exc:
        # SMTP not configured / misconfigured → 503 so dev can mock
        raise HTTPException(status_code=503, detail=str(exc))
    except Exception as exc:
        logger.error(f"send_email failed: {exc}")
        raise HTTPException(status_code=502, detail=f"Email send failed: {exc}")

    # Best-effort audit log (silent if no audit table)
    if payload.application_id:
        try:
            logger.info(
                f"AUDIT email sent: application_id={payload.application_id} "
                f"by user={current_user.id} to={result.get('to')}"
            )
        except Exception:
            pass

    return SendResponse(sent=bool(result.get("sent")), to=result.get("to", []))


@router.post("/bulk-send", response_model=BulkSendResponse)
def bulk_send(
    payload: BulkSendRequest,
    db: Session = Depends(get_db_session),
    current_user: UserModel = Depends(allow_recruiters),
):
    # Resolve recruiter's company for scoping
    company = _get_recruiter_company(db, current_user)
    if not company:
        raise HTTPException(status_code=403, detail="Recruiter company not found")

    job = (
        db.query(JobModel)
        .filter(JobModel.id == payload.job_id, JobModel.company_id == company.id)
        .first()
    )
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    q = db.query(ApplicationModel).filter(ApplicationModel.job_id == job.id)
    if payload.status:
        q = q.filter(ApplicationModel.status == payload.status)
    if payload.stage_id:
        q = q.filter(ApplicationModel.stage_id == payload.stage_id)
    applications = q.all()

    stage_name_by_id: Dict[str, str] = {}
    for s in db.query(JobStageModel).filter(JobStageModel.job_id == job.id).all():
        stage_name_by_id[str(s.id)] = s.name

    sent = 0
    failed = 0
    errors: List[Dict[str, Any]] = []

    for app_row in applications:
        recipient = (app_row.applicant_email or "").strip()
        if not recipient:
            failed += 1
            errors.append({
                "application_id": str(app_row.id),
                "error": "missing candidate email",
            })
            continue

        # Per-candidate context
        scheduled_at_str = ""
        interview = (
            db.query(InterviewModel)
            .filter(InterviewModel.application_id == app_row.id)
            .order_by(InterviewModel.scheduled_at.desc())
            .first()
        )
        if interview and interview.scheduled_at:
            scheduled_at_str = interview.scheduled_at.isoformat()

        stage_name = stage_name_by_id.get(str(app_row.stage_id)) if app_row.stage_id else ""

        vars = {
            "candidate_name": app_row.applicant_name or "Candidate",
            "job_title": job.title or "",
            "company_name": company.name,
            "stage_name": stage_name or "",
            "scheduled_at": scheduled_at_str,
        }

        subject = _render_template(payload.subject_template, vars)
        body = _render_template(payload.body_template, vars)

        if payload.include_interview_score and interview is not None:
            report = (
                db.query(ReportModel)
                .filter(ReportModel.interview_id == interview.id)
                .order_by(ReportModel.created_at.desc())
                .first()
            )
            if report and report.category_scores and isinstance(report.category_scores, list):
                body = _append_performance_summary(body, report.category_scores)

        try:
            send_email(to=recipient, subject=subject, body=body)
            sent += 1
        except RuntimeError as exc:
            # SMTP not configured — fail-fast, no point looping
            raise HTTPException(status_code=503, detail=str(exc))
        except Exception as exc:
            failed += 1
            errors.append({
                "application_id": str(app_row.id),
                "to": recipient,
                "error": str(exc),
            })

    return BulkSendResponse(sent=sent, failed=failed, errors=errors)
