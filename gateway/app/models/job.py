from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime
from uuid import UUID

# Base schema for shared properties
class JobBase(BaseModel):
    title: str
    description: str
    location: Optional[str] = "Remote"
    type: Optional[str] = "Full Time"
    salary_min: Optional[int] = None
    salary_max: Optional[int] = None
    required_skills: List[str] = [] # e.g. ["Flutter", "FastAPI"]
    experience_level: str
    last_date_to_apply: Optional[datetime] = None

# Schema for CREATING a job (Frontend Input)
class JobCreate(JobBase):
    pass

# Schema for UPDATING a job (Partial updates allowed)
class JobUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    location: Optional[str] = None
    type: Optional[str] = None
    salary_min: Optional[int] = None
    salary_max: Optional[int] = None
    required_skills: Optional[List[str]] = None
    experience_level: Optional[str] = None
    last_date_to_apply: Optional[datetime] = None
    status: Optional[str] = None

# Schema for READING a job (Backend Response)
class JobResponse(JobBase):
    id: UUID
    company_id: UUID
    recruiter_id: UUID
    status: str
    created_at: datetime
    
    # Optional: Helper to show company name nicely
    company_name: Optional[str] = None 

    class Config:
        from_attributes = True
        
