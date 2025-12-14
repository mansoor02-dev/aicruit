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

# Schema for CREATING a job (Frontend Input)
class JobCreate(JobBase):
    pass

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
        
