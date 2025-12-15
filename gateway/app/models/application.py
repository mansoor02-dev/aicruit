from pydantic import BaseModel
from typing import Optional
from datetime import datetime
from uuid import UUID


# Base schema for shared properties
class ApplicationBase(BaseModel):
    resume_url: str


# Schema for CREATING an application (Candidate applies to job)
class ApplicationCreate(ApplicationBase):
    job_id: UUID


# Schema for READING an application (Backend Response)
class ApplicationResponse(ApplicationBase):
    id: UUID
    job_id: UUID
    candidate_id: UUID
    resume_id: Optional[UUID] = None
    status: str
    ai_match_score: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
