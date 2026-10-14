"""
Resume Parser API — FastAPI routes.

Entry point: gunicorn app.api:app -k uvicorn.workers.UvicornWorker

Routes:
  POST /parse          — Upload a PDF/DOCX and get structured resume data.
  POST /parse-resume   — Fetch a resume from DB by ID, parse, and save back.
  POST /score-fit      — Score a resume against a job description.
  GET  /health         — Health check.
  GET  /readiness      — Readiness check (verifies LLM provider is configured).
  GET  /               — Root / docs redirect.
"""

import os
import logging
import time

from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel
import json
import requests
from dotenv import load_dotenv

from app.core.config import get_settings
from app.schemas.resume import (
    ParseResumeByIdRequest,
    ParseResumeByIdResponse,
    ScoreFitRequest,
    ScoreFitResponse,
)
from app.services.resume_pipeline import (
    PipelineError,
    FileValidationError,
    ExtractionFailedError,
    LLMFailedError,
    parse_resume,
)
# Keep existing inference for /score-fit backward compatibility
from app.inference import run_score_inference
from app.db import get_db_session, Resume, init_db

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(name)s %(levelname)s %(message)s",
)
logger = logging.getLogger(__name__)

app = FastAPI(title="Resume Parser API", version="2.0.0")

# ── Settings ──────────────────────────────────────────────────────────────

settings = get_settings()
FILE_SERVICE_URL = settings.file_service_url

# Initialise DB tables on startup
init_db()


# ── Score-fit prompt (preserved from original) ────────────────────────────

SCORE_SYSTEM_PROMPT = """You are a hiring assistant evaluating how well a candidate's resume matches a job posting.

You will be given:
1. A job description (title, description, required_skills, experience_level, location, type).
2. A parsed resume (skills, experience entries with title/company/duration, education, projects).

Score the candidate on a 0-100 scale across four dimensions:

- skills_match (0-100): How well the candidate's listed skills cover the job's required_skills.
  Required skills are MUST-HAVE. Missing all of them caps this dimension at 20.
  Adjacent/transferable skills (e.g., "TypeScript" for a "JavaScript" requirement) count as partial credit.
- experience_match (0-100): Does the candidate's work history align with the role's seniority and domain?
  Treat experience_level as a soft signal — note mismatches in rationale but do not hard-cap.
  Weight relevance over years (3 yrs of directly-relevant beats 8 yrs of unrelated).
- education_match (0-100): Does education align? For most roles, default this to 70+ unless the JD
  explicitly demands a specific degree the candidate lacks.
- project_match (0-100): Do listed projects demonstrate the kinds of work this role involves?
  If no projects listed and the JD doesn't emphasize them, default to 60.

Then compute overall (0-100) as a weighted average:
  overall = round(0.45 * skills_match + 0.30 * experience_match + 0.10 * education_match + 0.15 * project_match)

Return ONLY valid JSON in this exact shape:
{
  "skills_match": int,
  "experience_match": int,
  "education_match": int,
  "project_match": int,
  "overall": int,
  "rationale": "1-3 sentences explaining the overall score, focused on the strongest match factors and the most significant gaps."
}

Rules:
- Be calibrated, not generous. A truly average match is 50, not 75.
- Never exceed 100 or go below 0 on any dimension.
- Do not invent skills/experience the resume doesn't list.
- If the resume is essentially empty, return all zeros and rationale "Resume contains insufficient information to evaluate."
"""


# ── Health & readiness ────────────────────────────────────────────────────

@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/readiness")
async def readiness():
    """Readiness check — verifies LLM provider is configured."""
    s = get_settings()
    issues = []
    if not s.gemini_api_key:
        issues.append("GEMINI_API_KEY not configured")
    if issues:
        return JSONResponse(
            status_code=503,
            content={"status": "not_ready", "issues": issues},
        )
    return {"status": "ready"}


@app.get("/")
async def root():
    return {"message": "Go to the /docs"}


# ── POST /parse — Upload & parse ──────────────────────────────────────────

@app.post("/parse")
async def parse_resume_upload(
    file: UploadFile = File(...),
):
    """
    Parse an uploaded PDF/DOCX resume and return structured data.

    Returns:
        JSON with filename, elapsed_seconds, and resume dict matching
        the established schema (personal_info, skills, experience, etc.)
    """
    filename = file.filename or ""
    ext = "." + filename.rsplit(".", 1)[-1].lower() if "." in filename else ""

    if ext not in {".pdf", ".docx"}:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type '{ext}'. Use PDF or DOCX.",
        )

    contents = await file.read()

    if len(contents) > settings.max_file_size_bytes:
        raise HTTPException(
            status_code=413,
            detail=f"File exceeds {settings.max_file_size_mb} MB limit.",
        )

    try:
        result = await parse_resume(contents, ext, settings)
    except FileValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except ExtractionFailedError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except LLMFailedError as e:
        raise HTTPException(status_code=502, detail=str(e))
    except PipelineError as e:
        raise HTTPException(status_code=e.status_code, detail=str(e))
    except Exception as exc:
        logger.error("parse.unexpected_error", extra={"error": str(exc)})
        raise HTTPException(
            status_code=500,
            detail="An unexpected error occurred during parsing.",
        )

    return JSONResponse(content={
        "filename": filename,
        "elapsed_seconds": result.elapsed_seconds,
        "resume": result.data,
    })


# ── POST /parse-resume — Fetch from DB, parse, save ──────────────────────

@app.post("/parse-resume", response_model=ParseResumeByIdResponse)
async def parse_resume_by_id(request: ParseResumeByIdRequest):
    """
    Fetch a resume record from the database by ID, download the file from
    its stored URL, parse it, persist the result back to the DB, and return
    the extracted skills.
    """
    session = next(get_db_session())
    try:
        resume_row = session.query(Resume).filter(Resume.id == request.resume_id).first()
        if not resume_row:
            raise HTTPException(
                status_code=404,
                detail=f"Resume with ID {request.resume_id} not found",
            )

        # Return cached result if already parsed
        if resume_row.parsed_skills:
            skills_data = resume_row.parsed_skills
            if isinstance(skills_data, dict):
                skills = skills_data.get("skills", [])
            elif isinstance(skills_data, list):
                skills = skills_data
            else:
                skills = []
            return ParseResumeByIdResponse(
                id=request.resume_id,
                message="Resume already parsed (cached)",
                skills=skills,
            )

        # Resolve file URL using the FILE_SERVICE_URL env var
        file_url = resume_row.file_url
        for local in ("localhost:8005", "127.0.0.1:8005"):
            if local in file_url:
                file_url = file_url.replace(f"http://{local}", FILE_SERVICE_URL)
                break
        if file_url.startswith("/"):
            file_url = f"{FILE_SERVICE_URL}{file_url}"

        # Fix file service mount path: /uploads is served at /static
        if "/uploads/" in file_url:
            file_url = file_url.replace("/uploads/", "/static/", 1)

        # Download the resume file
        try:
            resp = requests.get(file_url, timeout=30)
            resp.raise_for_status()
        except requests.RequestException as e:
            raise HTTPException(
                status_code=502,
                detail=f"Failed to download resume file: {e}",
            )

        # Determine extension from URL or Content-Type
        url_path = file_url.split("?")[0]
        if url_path.lower().endswith(".docx"):
            ext = ".docx"
        else:
            ext = ".pdf"  # default

        # Parse using new pipeline
        try:
            result = await parse_resume(resp.content, ext, settings)
        except FileValidationError as e:
            raise HTTPException(status_code=400, detail=str(e))
        except ExtractionFailedError as e:
            raise HTTPException(status_code=422, detail=str(e))
        except LLMFailedError as e:
            raise HTTPException(status_code=502, detail=str(e))
        except PipelineError as e:
            raise HTTPException(status_code=e.status_code, detail=str(e))
        except Exception as exc:
            logger.error("parse_by_id.unexpected_error", extra={"error": str(exc)})
            raise HTTPException(
                status_code=500,
                detail="Parsing failed due to an unexpected error.",
            )

        parsed_data = result.data
        skills: list = parsed_data.get("skills", []) if isinstance(parsed_data, dict) else []

        # Persist result back to DB
        try:
            resume_row.parsed_skills = {"skills": skills}
            resume_row.parsed_text = json.dumps(parsed_data)
            session.commit()
            session.refresh(resume_row)
        except Exception as update_err:
            session.rollback()
            raise HTTPException(
                status_code=500,
                detail=f"Failed to save parsed result: {update_err}",
            )

        return ParseResumeByIdResponse(
            id=request.resume_id,
            message=f"Resume parsed successfully in {result.elapsed_seconds}s",
            skills=skills,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error("parse_by_id.error", extra={"error": str(e)})
        raise HTTPException(status_code=500, detail="An unexpected error occurred.")
    finally:
        session.close()


# ── POST /score-fit — Score resume vs job ─────────────────────────────────

@app.post("/score-fit", response_model=ScoreFitResponse)
def score_fit(req: ScoreFitRequest):
    """Score how well a resume matches a job description."""
    user_payload = f"Job:\n{json.dumps(req.job, indent=2)}\n\nResume:\n{json.dumps(req.resume, indent=2)}"
    try:
        raw = run_score_inference(SCORE_SYSTEM_PROMPT, user_payload)
    except Exception as e:
        raise HTTPException(status_code=502, detail="scoring_unavailable") from e

    if not isinstance(raw, dict) or "overall" not in raw:
        raise HTTPException(status_code=502, detail="scoring_unavailable")

    def clamp(v):
        try:
            return max(0, min(100, int(v)))
        except (TypeError, ValueError):
            raise HTTPException(status_code=502, detail="scoring_unavailable")

    return ScoreFitResponse(
        overall=clamp(raw.get("overall")),
        skills_match=clamp(raw.get("skills_match", 0)),
        experience_match=clamp(raw.get("experience_match", 0)),
        education_match=clamp(raw.get("education_match", 0)),
        project_match=clamp(raw.get("project_match", 0)),
        rationale=str(raw.get("rationale") or ""),
    )