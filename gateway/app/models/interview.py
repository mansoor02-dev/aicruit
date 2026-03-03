from pydantic import BaseModel
from datetime import datetime
from uuid import UUID
from typing import Optional


class InterviewScheduleRequest(BaseModel):
    application_id: UUID
    scheduled_at: datetime


class InterviewScheduleResponse(BaseModel):
    id: UUID
    application_id: UUID
    scheduled_at: datetime
    status: str
    created_at: datetime

    class Config:
        from_attributes = True


class StartInterviewRequest(BaseModel):
    application_id: UUID

