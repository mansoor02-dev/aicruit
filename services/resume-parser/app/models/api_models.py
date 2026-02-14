from pydantic import BaseModel, Field
from typing import Optional


class ParseResumeRequest(BaseModel):
    """Request model for parse-resume endpoint"""
    resume_id: str = Field(..., description="Resume ID from database to parse")


class ParseResumeResponse(BaseModel):
    """Response model for parse-resume endpoint"""
    id: str = Field(..., description="ID of the created resume record")
    message: str = Field(..., description="Status message")
    skills: list = Field(default_factory=list, description="List of skills extracted from resume")

