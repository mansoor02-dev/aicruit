from fastapi import FastAPI, File, UploadFile, Form, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import Optional
import json
import time
import requests

from app.ingestion import ingest_bytes
from app.cleaner import clean_text
from app.inference import run_inference
from app.validator import validate
from app.db import get_db_session, Resume, init_db

app = FastAPI(title="Resume Parser API", version="1.0.0")

# Initialise DB tables on startup
init_db()


@app.get("/health")
async def health():
    return {"status": "ok"}

@app.get("/")
async def root():
    return {"message": "Go to the /docs"}

@app.post("/parse")
async def parse_resume(
    file: UploadFile = File(...),
    backend: Optional[str] = Form(default="gemini")
):
    filename = file.filename or ""
    ext = "." + filename.rsplit(".", 1)[-1].lower() if "." in filename else ""

    if ext not in {".pdf", ".docx"}:
        raise HTTPException(status_code=400, detail=f"Unsupported file type '{ext}'. Use PDF or DOCX.")

    if backend not in ("local", "gemini"):
        raise HTTPException(status_code=400, detail="backend must be 'local' or 'gemini'.")

    contents = await file.read()
    if len(contents) > 10 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="File exceeds 10 MB limit.")

    start = time.perf_counter()
    try:
        raw_text = ingest_bytes(contents, ext)
        cleaned = clean_text(raw_text)
        raw_json = run_inference(cleaned, backend=backend)
        result = validate(raw_json)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))

    return JSONResponse(content={
        "filename": filename,
        "backend": backend,
        "elapsed_seconds": round(time.perf_counter() - start, 2),
        "resume": result,
    })


# ---------------------------------------------------------------------------
# Request / Response models
# ---------------------------------------------------------------------------

class ParseResumeByIdRequest(BaseModel):
    resume_id: str
    backend: Optional[str] = "gemini"


class ParseResumeByIdResponse(BaseModel):
    id: str
    message: str
    skills: list


# ---------------------------------------------------------------------------
# /parse-resume  — fetch from DB, parse, save back
# ---------------------------------------------------------------------------

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

        # Resolve internal Docker service URL if needed
        file_url = resume_row.file_url
        for local in ("localhost:8005", "127.0.0.1:8005"):
            if local in file_url:
                file_url = file_url.replace(local, "aicruit_file_service:8005")
                break
        if file_url.startswith("/"):
            file_url = f"http://aicruit_file_service:8005{file_url}"

        # Download the resume file
        try:
            resp = requests.get(file_url, timeout=30)
            resp.raise_for_status()
        except requests.RequestException as e:
            raise HTTPException(status_code=502, detail=f"Failed to download resume file: {e}")

        # Determine extension from URL or Content-Type
        url_path = file_url.split("?")[0]
        if url_path.lower().endswith(".docx"):
            ext = ".docx"
        else:
            ext = ".pdf"  # default

        # Parse
        start = time.perf_counter()
        try:
            raw_text = ingest_bytes(resp.content, ext)
            cleaned = clean_text(raw_text)
            raw_json = run_inference(cleaned, backend=request.backend)
            result = validate(raw_json)
        except Exception as exc:
            raise HTTPException(status_code=500, detail=f"Parsing failed: {exc}")

        elapsed = round(time.perf_counter() - start, 2)
        skills: list = result.get("skills", []) if isinstance(result, dict) else []

        # Persist result back to DB
        try:
            resume_row.parsed_skills = {"skills": skills}
            resume_row.parsed_text = json.dumps(result)
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
            message=f"Resume parsed successfully in {elapsed}s",
            skills=skills,
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        session.close()