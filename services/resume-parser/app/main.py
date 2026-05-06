import sys
import os
import logging
sys.path.insert(0, "/app")

from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import List, Optional
import pdfplumber
import io

from shared.llm_client import LLMClient

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Resume Parser Service", version="1.0.0")

# CORS middleware
FRONTEND_ORIGINS = os.getenv("FRONTEND_ORIGINS", "http://localhost:3000").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=FRONTEND_ORIGINS if FRONTEND_ORIGINS != [''] else ["*"],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)


# ── Pydantic models ────────────────────────────────────────────────────────

class WorkExperience(BaseModel):
    company: str
    title: str
    duration_months: Optional[int] = None
    description: str = ""


class Education(BaseModel):
    institution: str
    degree: str
    field: str = ""
    year: Optional[int] = None


class ParsedResume(BaseModel):
    full_name: str = ""
    email: str = ""
    phone: str = ""
    location: str = ""
    skills: List[str] = Field(default_factory=list)
    years_experience: float = 0.0
    experience: List[WorkExperience] = Field(default_factory=list)
    education: List[Education] = Field(default_factory=list)
    summary: str = ""
    languages: List[str] = Field(default_factory=list)


# ── Helpers ────────────────────────────────────────────────────────────────

def extract_text_from_pdf(pdf_bytes: bytes) -> str:
    """Extract raw text from PDF bytes using pdfplumber."""
    text_parts = []
    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        for page in pdf.pages:
            text = page.extract_text()
            if text:
                text_parts.append(text)
    return "\n".join(text_parts)


async def parse_with_llm(resume_text: str) -> ParsedResume:
    """Use LLM to extract structured data from raw resume text."""
    client = LLMClient()
    prompt = f"""Extract information from this resume text and return structured JSON.

RESUME TEXT:
{resume_text[:6000]}

Rules:
- skills: technical skills only (Python, React, PostgreSQL etc), not soft skills
- years_experience: total years of professional work experience as a number
- duration_months: approximate months at each job, 0 if unknown
- Return empty strings/arrays for missing fields, never null"""

    return await client.complete_json(prompt, ParsedResume)


def fallback_extract(resume_text: str) -> ParsedResume:
    """Regex fallback for when LLM fails. Gets critical fields only."""
    import re
    parsed = ParsedResume()

    email_match = re.search(r'[\w.+-]+@[\w-]+\.[a-zA-Z]{2,}', resume_text)
    if email_match:
        parsed.email = email_match.group(0)

    phone_match = re.search(r'(\+?\d[\d\s\-().]{7,15}\d)', resume_text)
    if phone_match:
        parsed.phone = phone_match.group(0).strip()

    return parsed


# ── Routes ─────────────────────────────────────────────────────────────────

@app.post("/parse", response_model=ParsedResume)
async def parse_resume(file: UploadFile = File(...)):
    """Parse a resume PDF and return structured data."""
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files accepted")

    pdf_bytes = await file.read()
    if len(pdf_bytes) > 10 * 1024 * 1024:  # 10MB limit
        raise HTTPException(status_code=400, detail="File too large (max 10MB)")

    resume_text = extract_text_from_pdf(pdf_bytes)
    if not resume_text.strip():
        raise HTTPException(status_code=422, detail="Could not extract text from PDF")

    try:
        parsed = await parse_with_llm(resume_text)
        logger.info(f"LLM parsed resume: {parsed.full_name}, skills: {len(parsed.skills)}")
        return parsed
    except Exception as e:
        logger.warning(f"LLM parsing failed ({e}), using fallback")
        return fallback_extract(resume_text)


@app.get("/health")
async def health():
    return {"status": "ok", "service": "resume-parser"}