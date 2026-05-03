from pydantic import BaseModel, Field
from typing import List, Optional, Literal
from datetime import datetime
from uuid import UUID


# ---------------------------------------------------------------------------
# Custom application question (recruiter defines, candidate answers)
# ---------------------------------------------------------------------------
QuestionType = Literal[
    "text", "textarea", "number", "date", "select", "yes_no", "email", "url"
]


class ApplicationQuestion(BaseModel):
    """Recruiter-defined question attached to a job's application form."""
    id: str
    label: str
    help_text: Optional[str] = None
    type: QuestionType = "text"
    required: bool = False
    # Text constraints
    min_length: Optional[int] = None
    max_length: Optional[int] = None
    # Number constraints
    min_value: Optional[float] = None
    max_value: Optional[float] = None
    # Select options (only for type == "select")
    options: Optional[List[str]] = None


# ---------------------------------------------------------------------------
# Job schemas
# ---------------------------------------------------------------------------
class JobBase(BaseModel):
    title: str
    description: str
    location: Optional[str] = "Remote"
    type: Optional[str] = "Full Time"
    salary_min: Optional[int] = None
    salary_max: Optional[int] = None
    required_skills: List[str] = []  # e.g. ["Flutter", "FastAPI"]
    experience_level: str
    last_date_to_apply: Optional[datetime] = None
    application_questions: List[ApplicationQuestion] = []


class JobCreate(JobBase):
    pass


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
    application_questions: Optional[List[ApplicationQuestion]] = None


class JobResponse(JobBase):
    id: UUID
    company_id: UUID
    recruiter_id: UUID
    status: str
    created_at: datetime
    company_name: Optional[str] = None

    class Config:
        from_attributes = True


# Schema for Candidate's Applications (Job + Application details combined)
class MyApplicationResponse(BaseModel):
    application_id: UUID
    application_status: str
    applied_at: datetime
    job_id: UUID
    job_title: str
    job_description: str
    location: Optional[str]
    job_type: Optional[str]
    salary_min: Optional[int]
    salary_max: Optional[int]
    required_skills: List[str]
    experience_level: Optional[str]
    last_date_to_apply: Optional[datetime]
    job_status: str
    job_created_at: datetime
    scheduled_at: Optional[datetime] = None


# Schema for Applicant info (Recruiter view)
class ApplicantInfo(BaseModel):
    application_id: UUID
    application_status: str
    stage_id: Optional[UUID] = None
    applied_at: datetime
    candidate_id: UUID
    candidate_name: str
    candidate_email: str
    candidate_phone: Optional[str]
    candidate_linkedin: Optional[str]
    resume_id: Optional[UUID]
    resume_url: str

    class Config:
        from_attributes = True


# Schema for Recruiter's Job Listing (with list of applicants)
class JobWithApplicantsResponse(JobBase):
    id: UUID
    company_id: UUID
    recruiter_id: UUID
    status: str
    created_at: datetime
    applicants: List[ApplicantInfo] = []

    class Config:
        from_attributes = True


# Schema for Candidate's Job Listing (basic job details)
class JobForCandidateResponse(JobBase):
    id: UUID
    company_id: UUID
    status: str
    created_at: datetime

    class Config:
        from_attributes = True
