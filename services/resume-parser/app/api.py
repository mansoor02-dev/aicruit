from fastapi import FastAPI, File, UploadFile, Form, HTTPException
from fastapi.responses import JSONResponse
from typing import Optional
import time

from app.ingestion import ingest_bytes
from app.cleaner import clean_text
from app.inference import run_inference
from app.validator import validate

app = FastAPI(title="Resume Parser API", version="1.0.0")


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