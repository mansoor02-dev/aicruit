"""
Pydantic schemas for structured resume extraction.

These schemas match the existing API contract established by the original
`validator.ResumeSchema` and the output format consumed by the gateway's
`job.py` route (which reads personal_info, skills, experience, education,
projects, certifications, publications, interests, languages).

The LLM is instructed to produce JSON conforming to `ResumeExtraction`.
After extraction, `ResumeExtraction.to_api_dict()` produces the dict that
matches the legacy response shape.
"""

from __future__ import annotations

import re
from typing import Any, Optional

from pydantic import BaseModel, Field, field_validator


# ── Nested schemas ────────────────────────────────────────────────────────

class PersonalInfo(BaseModel):
    """Contact and identity information."""
    name: str = ""
    email: str = ""
    phone: str = ""
    linkedin: str = ""
    github: str = ""
    location: str = ""

    @field_validator("email")
    @classmethod
    def _clean_email(cls, v: str) -> str:
        if not v:
            return v
        v = re.sub(r"[#\s]+", "", v).strip()
        return v


class ExperienceEntry(BaseModel):
    """A single work-experience entry."""
    title: str = ""
    company: str = ""
    duration: str = ""
    description: str | list[str] = ""


class EducationEntry(BaseModel):
    """A single education entry."""
    degree: str = ""
    institution: str = ""
    duration: str = ""
    location: str = ""


class ProjectEntry(BaseModel):
    """A single project entry."""
    name: str = ""
    tech: str = ""
    description: str | list[str] = ""


class CertificationEntry(BaseModel):
    """A certification or award."""
    name: str = ""
    issuer: str = ""
    date: str = ""


class PublicationEntry(BaseModel):
    """A publication entry."""
    title: str = ""
    venue: str = ""
    date: str = ""


# ── Top-level extraction schema ──────────────────────────────────────────

class ResumeExtraction(BaseModel):
    """
    Schema for LLM-extracted resume data.

    Matches the existing API response contract. All fields have safe defaults
    so the model never needs to fabricate missing information.
    """
    personal_info: PersonalInfo = Field(default_factory=PersonalInfo)
    skills: list[str] = Field(default_factory=list)
    experience: list[ExperienceEntry] = Field(default_factory=list)
    education: list[EducationEntry] = Field(default_factory=list)
    projects: list[ProjectEntry] = Field(default_factory=list)
    certifications: list[CertificationEntry | dict[str, Any]] = Field(default_factory=list)
    publications: list[PublicationEntry | dict[str, Any]] = Field(default_factory=list)
    interests: list[str] = Field(default_factory=list)
    languages: list[str] = Field(default_factory=list)

    def to_api_dict(self) -> dict[str, Any]:
        """
        Convert to the dict format expected by the existing API response
        and the gateway's `job.py` normalization.

        Matches the legacy `validator.ResumeSchema.model_dump()` output.
        """
        return {
            "personal_info": self.personal_info.model_dump(),
            "skills": self.skills,
            "experience": [e.model_dump() for e in self.experience],
            "education": [e.model_dump() for e in self.education],
            "projects": [p.model_dump() for p in self.projects],
            "certifications": [
                c.model_dump() if isinstance(c, BaseModel) else c
                for c in self.certifications
            ],
            "publications": [
                p.model_dump() if isinstance(p, BaseModel) else p
                for p in self.publications
            ],
            "interests": self.interests,
            "languages": self.languages,
        }


# ── API response models (kept in schemas for co-location) ────────────────

class ParseResumeByIdRequest(BaseModel):
    resume_id: str


class ParseResumeByIdResponse(BaseModel):
    id: str
    message: str
    skills: list


class ScoreFitRequest(BaseModel):
    resume: dict
    job: dict


class ScoreFitResponse(BaseModel):
    overall: int
    skills_match: int
    experience_match: int
    education_match: int
    project_match: int
    rationale: str
