from pydantic import BaseModel, Field
from typing import Optional


class ParseResumeRequest(BaseModel):
    """Request model for parse-resume endpoint"""
    id: Optional[str] = Field(None, description="Candidate ID (optional)")
    pdf_url: str = Field(..., description="URL of the resume PDF/DOCX file")


class ParseResumeResponse(BaseModel):
    """Response model for parse-resume endpoint"""
    id: str = Field(..., description="ID of the created resume record")
    message: str = Field(..., description="Status message")

