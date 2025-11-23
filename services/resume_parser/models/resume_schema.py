from pydantic import BaseModel, Field, field_validator

# ============================================================================
# PYDANTIC SCHEMA - Structured Resume Data Model
# ============================================================================

class Education(BaseModel):
    """Educational qualification"""
    degree: str = Field(..., description="Degree type (e.g., BSc, MSc, PhD)")
    field: str = Field(..., description="Field of study (e.g., Computer Science)")
    university: str = Field(..., description="University/Institution name")
    country: Optional[str] = Field(None, description="Country")
    start_year: Optional[int] = Field(None, description="Start year")
    end_year: Optional[int] = Field(None, description="End year or expected")
    gpa: Optional[float] = Field(None, ge=0, le=4.0, description="GPA out of 4.0")
    
    @field_validator('end_year')
    def validate_end_year(cls, v, info):
        if v and info.data.get('start_year') and v < info.data['start_year']:
            raise ValueError('End year must be after start year')
        return v


class WorkExperience(BaseModel):
    """Work experience entry"""
    title: str = Field(..., description="Job title")
    company: str = Field(..., description="Company name")
    location: Optional[str] = Field(None, description="Location")
    start_date: str = Field(..., description="Start date (YYYY-MM format)")
    end_date: Optional[str] = Field(None, description="End date (YYYY-MM) or 'Present'")
    duration_months: Optional[int] = Field(None, description="Duration in months")
    description: Optional[str] = Field(None, description="Job description")
    technologies: List[str] = Field(default_factory=list, description="Technologies used")


class Project(BaseModel):
    """Technical project"""
    title: str = Field(..., description="Project name")
    description: str = Field(..., description="Project description")
    technologies: List[str] = Field(default_factory=list, description="Tech stack")
    role: Optional[str] = Field(None, description="Your role")
    link: Optional[str] = Field(None, description="GitHub/demo link")
    year: Optional[int] = Field(None, description="Year completed")


class Publication(BaseModel):
    """Research publication"""
    title: str = Field(..., description="Paper title")
    authors: List[str] = Field(..., description="Author list")
    venue: str = Field(..., description="Conference/Journal name")
    year: int = Field(..., description="Publication year")
    paper_type: Literal["conference", "journal", "workshop", "preprint"] = "conference"
    link: Optional[str] = Field(None, description="DOI or paper link")


class Certification(BaseModel):
    """Professional certification"""
    name: str = Field(..., description="Certification name")
    issuer: str = Field(..., description="Issuing organization")
    issue_date: Optional[str] = Field(None, description="Issue date (YYYY-MM)")
    expiry_date: Optional[str] = Field(None, description="Expiry date (YYYY-MM)")
    credential_id: Optional[str] = Field(None, description="Credential ID")


class StructuredResume(BaseModel):
    """Complete structured resume schema"""
    # Personal Info
    name: str = Field(..., description="Full name")
    email: Optional[str] = Field(None, description="Email address")
    phone: Optional[str] = Field(None, description="Phone number")
    location: Optional[str] = Field(None, description="Current location")
    linkedin: Optional[str] = Field(None, description="LinkedIn URL")
    github: Optional[str] = Field(None, description="GitHub URL")
    website: Optional[str] = Field(None, description="Personal website")
    
    # Professional Summary
    summary: Optional[str] = Field(None, description="Professional summary/objective")
    
    # Core Sections
    skills: List[str] = Field(default_factory=list, description="Technical skills")
    education: List[Education] = Field(default_factory=list, description="Education history")
    experience: List[WorkExperience] = Field(default_factory=list, description="Work experience")
    projects: List[Project] = Field(default_factory=list, description="Technical projects")
    publications: List[Publication] = Field(default_factory=list, description="Publications")
    certifications: List[Certification] = Field(default_factory=list, description="Certifications")
    
    # Additional
    languages: List[str] = Field(default_factory=list, description="Spoken languages")
    awards: List[str] = Field(default_factory=list, description="Awards and honors")
    
    # Metadata
    extraction_date: str = Field(default_factory=lambda: datetime.now().isoformat())
    source_file: Optional[str] = None