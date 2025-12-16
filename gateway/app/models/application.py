from pydantic import BaseModel
from typing import Optional
from datetime import datetime
from uuid import UUID


# Input schema: requires resume_url to create resume row
class ApplicationCreate(BaseModel):
    job_id: UUID
    resume_url: str


# Output schema: returns resume_id (stored), not the URL
class ApplicationResponse(BaseModel):
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
