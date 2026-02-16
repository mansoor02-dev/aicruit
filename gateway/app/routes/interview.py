from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from ..core.db import get_db_session
from ..models.interview_model import InterviewModel
from ..models.application_model import ApplicationModel
from ..models.user import UserModel
from ..models.interview import InterviewScheduleRequest, InterviewScheduleResponse
from ..core.security import RoleChecker

router = APIRouter()

# Only RECRUITER and ADMIN can schedule interviews
allow_recruiters = RoleChecker(["RECRUITER", "ADMIN"])


# =========================================================
# SCHEDULE INTERVIEW (Recruiters / Admins Only)
# =========================================================
@router.post("/schedule", response_model=InterviewScheduleResponse, status_code=status.HTTP_200_OK)
def schedule_interview(
    payload: InterviewScheduleRequest,
    db: Session = Depends(get_db_session),
    current_user: UserModel = Depends(allow_recruiters),
):
    # 1. Verify the application exists
    application = db.query(ApplicationModel).filter(
        ApplicationModel.id == payload.application_id
    ).first()

    if not application:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Application not found",
        )

    # 2. Create the interview record
    new_interview = InterviewModel(
        application_id=payload.application_id,
        scheduled_at=payload.scheduled_at,
        status="scheduled",
    )
    db.add(new_interview)

    # 3. Update application status to INTERVIEW_SCHEDULED
    application.status = "INTERVIEW_SCHEDULED"

    db.commit()
    db.refresh(new_interview)

    return new_interview
