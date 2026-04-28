from pydantic import BaseModel
from typing import Optional, List, Any
from datetime import datetime
from uuid import UUID


# Sub-schemas for structured form data
class EducationEntry(BaseModel):
    university: str = ""
    degree: str = ""
    field: str = ""
    start_year: str = ""
    end_year: str = ""

class ExperienceEntry(BaseModel):
    title: str = ""
    company: str = ""
    start_date: str = ""
    end_date: str = ""
    description: str = ""

class ProjectEntry(BaseModel):
    title: str = ""
    description: str = ""


class QuestionResponse(BaseModel):
    """Candidate's answer to one of the recruiter-defined application questions."""
    question_id: str
    label: Optional[str] = None
    type: Optional[str] = None
    value: Any = None  # text/number/date/bool/string-of-option


# Input schema: includes all candidate-submitted form data
class ApplicationCreate(BaseModel):
    job_id: UUID
    resume_id: UUID
    # Candidate form data
    applicant_name: str = ""
    applicant_email: str = ""
    applicant_phone: str = ""
    applicant_location: str = ""
    summary: str = ""
    skills: List[str] = []
    education: List[EducationEntry] = []
    experience: List[ExperienceEntry] = []
    projects: List[ProjectEntry] = []
    # Recruiter-defined custom questions: candidate's answers
    question_responses: List[QuestionResponse] = []


# Output schema
class ApplicationResponse(BaseModel):
    id: UUID
    job_id: UUID
    candidate_id: UUID
    resume_id: Optional[UUID] = None
    applicant_name: Optional[str] = None
    applicant_email: Optional[str] = None
    applicant_phone: Optional[str] = None
    applicant_location: Optional[str] = None
    summary: Optional[str] = None
    skills: Optional[List] = None
    education: Optional[List] = None
    experience: Optional[List] = None
    projects: Optional[List] = None
    question_responses: Optional[List] = None
    status: str
    ai_match_score: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
