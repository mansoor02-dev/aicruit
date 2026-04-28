from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from uuid import UUID

from ..core.db import get_db_session
from ..core.security import RoleChecker
from ..models.job_model import JobModel
from ..models.user import UserModel
from ..models.job_interview_settings_model import JobInterviewSettingsModel
from ..models.job_interview_settings import (
    JobInterviewSettingsResponse,
    JobInterviewSettingsUpdate,
)

router = APIRouter()
allow_recruiters = RoleChecker(["RECRUITER", "ADMIN"])


def _ensure_job_owned(db: Session, job_id: UUID, current_user: UserModel) -> JobModel:
    job = db.query(JobModel).filter(JobModel.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if not current_user.recruiter or job.company_id != current_user.recruiter.company_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only access settings for jobs from your company",
        )
    return job


def _to_response(job_id: UUID, settings: JobInterviewSettingsModel | None) -> JobInterviewSettingsResponse:
    if settings is None:
        return JobInterviewSettingsResponse(
            job_id=job_id,
            ai_interview_enabled=False,
            uploaded_questions=None,
            topics=[],
            fixed_question_count=False,
            number_of_questions=None,
            max_questions=None,
            difficulty_level=None,
            interview_stages=1,
        )
    return JobInterviewSettingsResponse(
        id=settings.id,
        job_id=settings.job_id,
        ai_interview_enabled=settings.ai_interview_enabled,
        uploaded_questions=settings.uploaded_questions,
        topics=settings.topics or [],
        fixed_question_count=settings.fixed_question_count,
        number_of_questions=settings.number_of_questions,
        max_questions=settings.max_questions,
        difficulty_level=settings.difficulty_level,
        interview_stages=settings.interview_stages,
        created_at=settings.created_at,
        updated_at=settings.updated_at,
    )


@router.get("/{job_id}/interview-settings", response_model=JobInterviewSettingsResponse)
def get_interview_settings(
    job_id: UUID,
    db: Session = Depends(get_db_session),
    current_user: UserModel = Depends(allow_recruiters),
):
    _ensure_job_owned(db, job_id, current_user)
    settings = db.query(JobInterviewSettingsModel).filter(
        JobInterviewSettingsModel.job_id == job_id
    ).first()
    return _to_response(job_id, settings)


@router.put("/{job_id}/interview-settings", response_model=JobInterviewSettingsResponse)
def upsert_interview_settings(
    job_id: UUID,
    payload: JobInterviewSettingsUpdate,
    db: Session = Depends(get_db_session),
    current_user: UserModel = Depends(allow_recruiters),
):
    _ensure_job_owned(db, job_id, current_user)

    if payload.ai_interview_enabled:
        if payload.fixed_question_count:
            if payload.number_of_questions is None or payload.number_of_questions <= 0:
                raise HTTPException(
                    status_code=400,
                    detail="number_of_questions is required when fixed_question_count is enabled",
                )
        else:
            if payload.max_questions is None or payload.max_questions <= 0:
                raise HTTPException(
                    status_code=400,
                    detail="max_questions is required when fixed_question_count is disabled",
                )

    if payload.interview_stages is None or payload.interview_stages < 1:
        raise HTTPException(status_code=400, detail="interview_stages must be >= 1")

    uploaded = None
    if payload.uploaded_questions is not None:
        uploaded = [
            q.dict() if hasattr(q, "dict") else q
            for q in payload.uploaded_questions
        ]

    settings = db.query(JobInterviewSettingsModel).filter(
        JobInterviewSettingsModel.job_id == job_id
    ).first()

    if settings is None:
        settings = JobInterviewSettingsModel(
            job_id=job_id,
            ai_interview_enabled=payload.ai_interview_enabled,
            uploaded_questions=uploaded,
            topics=payload.topics or [],
            fixed_question_count=payload.fixed_question_count,
            number_of_questions=payload.number_of_questions,
            max_questions=payload.max_questions,
            difficulty_level=payload.difficulty_level,
            interview_stages=payload.interview_stages,
        )
        db.add(settings)
    else:
        settings.ai_interview_enabled = payload.ai_interview_enabled
        settings.uploaded_questions = uploaded
        settings.topics = payload.topics or []
        settings.fixed_question_count = payload.fixed_question_count
        settings.number_of_questions = payload.number_of_questions
        settings.max_questions = payload.max_questions
        settings.difficulty_level = payload.difficulty_level
        settings.interview_stages = payload.interview_stages

    db.commit()
    db.refresh(settings)
    return _to_response(job_id, settings)
