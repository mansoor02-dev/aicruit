import io
import json
import os
from datetime import datetime, timedelta, timezone
from uuid import UUID

import httpx
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from ..core.db import get_db_session
from ..models.interview_model import InterviewModel
from ..models.interview_question_model import InterviewQuestionModel
from ..models.interview_response_model import InterviewResponseModel
from ..models.application_model import ApplicationModel
from ..models.user import UserModel
from ..models.interview import (
    InterviewScheduleRequest,
    InterviewScheduleResponse,
    StartInterviewRequest,
)
from ..core.security import RoleChecker, get_current_user

router = APIRouter()

# Only RECRUITER and ADMIN can schedule interviews
allow_recruiters = RoleChecker(["RECRUITER", "ADMIN"])

# Service URLs (use container names inside Docker, fallback for local dev)
QUESTION_GEN_URL = os.getenv("QUESTION_GEN_URL", "http://aicruit_question_generation:8010")
TTS_URL = os.getenv("TTS_URL", "http://aicruit_text_to_speech:8011")
TRANSCRIBE_URL = os.getenv("TRANSCRIBE_URL", "http://aicruit_audio_transcribe:8007")

# Hardcoded resume path (inside the gateway container, mounted or copied)
HARDCODED_RESUME_PATH = os.getenv(
    "HARDCODED_RESUME_PATH",
    os.path.join(os.path.dirname(__file__), "..", "..", "hardcoded_resume.json"),
)


# ─── Helpers ─────────────────────────────────────────────────────────────────


def _load_hardcoded_resume() -> dict:
    """Load the hardcoded resume JSON. Falls back to an inline dict if file is missing."""
    try:
        with open(HARDCODED_RESUME_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        pass

    # Inline fallback – the exact resume from resume_2a6cca54-…
    return {
        "name": "Ahmad Tariq",
        "email": "dev.ahmadtariq@gmail.com",
        "phone": "+92 320 484 6384",
        "location": "Islamabad, Pakistan",
        "linkedin": "https://linkedin.com/in/ahmad-tariq-",
        "github": "https://github.com/iAhmadTariq",
        "website": None,
        "summary": "Flutter Developer with proven expertise in building scalable, feature-rich applications. Proficient in state management, backend integrations, and delivering clean, industry-standard solutions across diverse domains.",
        "skills": [
            "Flutter", "Dart", "JavaScript", "React", "Python", "Node.js", "PHP",
            "Firebase", "MySQL", "PostgreSQL", "MongoDB", "WebRTC",
            "Clean Architecture", "MVC", "MVVM", "Dependency Injection",
            "GoRouter", "Bloc", "GetIt", "Dio", "HTTP", "Supabase",
            "Cubit", "Provider", "Riverpod", "AdMob", "Android TVs",
        ],
        "education": [
            {
                "degree": "Bachelor\u2019s degree",
                "field": "Computer Science",
                "university": "National University of Science and Technology (NUST)",
                "country": "Pakistan",
                "start_year": 2022,
                "end_year": 2026,
                "gpa": None,
            },
            {
                "degree": "Intermediate",
                "field": "Pre-Engineering",
                "university": "Government College University (GCU), Lahore",
                "country": "Pakistan",
                "start_year": 2020,
                "end_year": 2022,
                "gpa": None,
            },
        ],
        "experience": [
            {
                "title": "Flutter Developer",
                "company": "Code Next Solutions",
                "location": "Islamabad, Pakistan",
                "start_date": "2024-07",
                "end_date": "Present",
                "duration_months": 2,
                "description": "Revamped MoltoVino, a wine restaurant app, using Clean Architecture, GoRouter, Bloc, and GetIt.",
                "technologies": ["Flutter", "Clean Architecture", "GoRouter", "Bloc", "GetIt", "Provider", "Riverpod", "Android TVs"],
            },
            {
                "title": "Freelance Flutter Developer",
                "company": "Freelance",
                "location": "Remote",
                "start_date": "2023-08",
                "end_date": "Present",
                "duration_months": 13,
                "description": "Completed 10+ projects with 100% client satisfaction.",
                "technologies": ["Flutter", "Bloc", "PHP", "Python", "Firebase", "Supabase", "MySQL", "MongoDB"],
            },
        ],
        "projects": [
            {
                "title": "Molto Vino",
                "description": "Refactored app with Clean Architecture.",
                "technologies": ["Flutter", "Dart", "GoRouter", "Bloc", "GetIt", "Dio", "HTTP", "Clean Architecture"],
                "role": None, "link": None, "year": 2024,
            },
            {
                "title": "Safe Pak",
                "description": "Built a public safety app for crime reporting.",
                "technologies": ["Flutter", "Supabase", "Bloc/Cubit", "GoRouter", "Clean Architecture"],
                "role": None, "link": None, "year": 2025,
            },
            {
                "title": "Chat Caller App",
                "description": "Developed audio/video calling app with WebRTC and Firebase.",
                "technologies": ["Flutter", "Firebase", "Bloc", "WebRTC", "Dart", "Clean Architecture", "Cubit", "AdMob"],
                "role": None, "link": None, "year": 2024,
            },
        ],
        "publications": [],
        "certifications": [],
        "languages": [],
        "awards": [],
    }


def _generate_question(resume_json: dict, previous_qa: list, difficulty: str = "medium") -> dict:
    """Call the question-generation service and return the full JSON response."""
    payload = {
        "resume_json": resume_json,
        "previous_qa": previous_qa,
        "difficulty": difficulty,
    }
    try:
        with httpx.Client(timeout=60.0) as client:
            resp = client.post(f"{QUESTION_GEN_URL}/next-question", json=payload)
            resp.raise_for_status()
    except httpx.HTTPStatusError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Question generation service error: {exc.response.status_code} – {exc.response.text}",
        )
    except httpx.RequestError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Could not reach question generation service: {str(exc)}",
        )

    data = resp.json()
    if not data.get("question"):
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Question generation service returned an empty question.",
        )
    return data


def _synthesize_audio(text: str) -> tuple[bytes, str]:
    """Call the TTS service and return (audio_bytes, content_type)."""
    try:
        with httpx.Client(timeout=60.0) as client:
            resp = client.post(f"{TTS_URL}/synthesize", json={"text": text})
            resp.raise_for_status()
            content_type = resp.headers.get("content-type", "audio/wav")
            return resp.content, content_type
    except (httpx.HTTPStatusError, httpx.RequestError) as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"TTS service error: {str(exc)}",
        )


def _transcribe_audio(audio_bytes: bytes, filename: str) -> str:
    """Call the audio-transcribe service and return the transcript text."""
    try:
        with httpx.Client(timeout=120.0) as client:
            files = {"file": (filename, audio_bytes)}
            resp = client.post(f"{TRANSCRIBE_URL}/transcribe", files=files)
            resp.raise_for_status()
    except httpx.HTTPStatusError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Transcription service error: {exc.response.status_code} – {exc.response.text}",
        )
    except httpx.RequestError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Could not reach transcription service: {str(exc)}",
        )

    data = resp.json()
    return data.get("transcription", "")


def _build_audio_response(
    audio_bytes: bytes,
    content_type: str,
    interview_id,
    question_text: str,
    question_sequence: int,
) -> StreamingResponse:
    """
    Build a StreamingResponse that sends the audio file as binary,
    with interview metadata in custom headers.
    """
    headers = {
        "X-Interview-Id": str(interview_id),
        "X-Question-Text": question_text.replace("\n", " "),
        "X-Question-Sequence": str(question_sequence),
        "Content-Disposition": f'attachment; filename="question_{question_sequence}.wav"',
        "Access-Control-Expose-Headers": "X-Interview-Id, X-Question-Text, X-Question-Sequence",
    }
    return StreamingResponse(
        io.BytesIO(audio_bytes),
        media_type=content_type,
        headers=headers,
    )


def _get_previous_qa(db: Session, interview_id) -> list[dict]:
    """
    Build the previous_qa list from the database.
    Returns [{"Q": "...", "A": "..."}, ...] for all answered questions.
    """
    questions = (
        db.query(InterviewQuestionModel)
        .filter(InterviewQuestionModel.interview_id == interview_id)
        .order_by(InterviewQuestionModel.question_order.asc())
        .all()
    )

    previous_qa = []
    for q in questions:
        # Find the response for this question
        response = (
            db.query(InterviewResponseModel)
            .filter(InterviewResponseModel.question_id == q.id)
            .first()
        )
        if response and response.transcript:
            previous_qa.append({
                "Q": q.question_text,
                "A": response.transcript,
            })

    return previous_qa


# =========================================================
# SCHEDULE INTERVIEW (Recruiters / Admins Only)
# =========================================================
@router.post("/schedule", response_model=InterviewScheduleResponse, status_code=status.HTTP_200_OK)
def schedule_interview(
    payload: InterviewScheduleRequest,
    db: Session = Depends(get_db_session),
    current_user: UserModel = Depends(allow_recruiters),
):
    # 1. Verify the application exists
    application = db.query(ApplicationModel).filter(
        ApplicationModel.id == payload.application_id
    ).first()

    if not application:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Application not found",
        )

    # 2. Create the interview record
    new_interview = InterviewModel(
        application_id=payload.application_id,
        scheduled_at=payload.scheduled_at,
        status="scheduled",
    )
    db.add(new_interview)

    # 3. Update application status to INTERVIEW_SCHEDULED
    application.status = "INTERVIEW_SCHEDULED"

    db.commit()
    db.refresh(new_interview)

    return new_interview


# =========================================================
# START INTERVIEW (Candidates)
# =========================================================
@router.post("/start", status_code=status.HTTP_200_OK)
def start_interview(
    payload: StartInterviewRequest,
    db: Session = Depends(get_db_session),
    current_user: UserModel = Depends(get_current_user),
):
    """
    Start an interview for the given application.

    Returns a binary audio file of the first question, with metadata in headers:
      - X-Interview-Id
      - X-Question-Text
      - X-Question-Sequence
    """

    # ── 1. Find the interview for the given application ──────────────────
    interview = (
        db.query(InterviewModel)
        .filter(InterviewModel.application_id == payload.application_id)
        .filter(InterviewModel.status == "scheduled")
        .order_by(InterviewModel.scheduled_at.desc())
        .first()
    )

    if not interview:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No scheduled interview found for this application.",
        )

    # ── 2. Validate time window (within 1 hour of scheduled_at) ──────────
    # now = datetime.now(timezone.utc)
    # scheduled_at = interview.scheduled_at

    # # Make scheduled_at timezone-aware if it isn't already
    # if scheduled_at.tzinfo is None:
    #     scheduled_at = scheduled_at.replace(tzinfo=timezone.utc)

    # window_start = scheduled_at - timedelta(hours=1)
    # window_end = scheduled_at + timedelta(hours=1)

    # if not (window_start <= now <= window_end):
    #     raise HTTPException(
    #         status_code=status.HTTP_400_BAD_REQUEST,
    #         detail=(
    #             f"Interview can only be started within 1 hour of the scheduled time. "
    #             f"Scheduled at: {scheduled_at.isoformat()}. "
    #             f"Current time: {now.isoformat()}."
    #         ),
    #     )

    # ── 3. Load resume JSON (hardcoded for now) ──────────────────────────
    resume_json = _load_hardcoded_resume()

    # ── 4. Generate the first question ───────────────────────────────────
    qg_data = _generate_question(resume_json, previous_qa=[], difficulty="medium")
    question_text = qg_data["question"]

    # ── 5. Save the question to the database ─────────────────────────────
    existing_count = (
        db.query(InterviewQuestionModel)
        .filter(InterviewQuestionModel.interview_id == interview.id)
        .count()
    )
    sequence_number = existing_count + 1

    new_question = InterviewQuestionModel(
        interview_id=interview.id,
        question_text=question_text,
        question_order=sequence_number,
    )
    db.add(new_question)

    # Update interview status
    interview.status = "in_progress"

    db.commit()
    db.refresh(new_question)

    # ── 6. Generate audio via TTS service ────────────────────────────────
    audio_bytes, content_type = _synthesize_audio(question_text)

    # ── 7. Return binary audio with metadata in headers ──────────────────
    return _build_audio_response(
        audio_bytes=audio_bytes,
        content_type=content_type,
        interview_id=interview.id,
        question_text=question_text,
        question_sequence=sequence_number,
    )


# =========================================================
# EVALUATE AND GENERATE NEXT QUESTION
# =========================================================
@router.post("/evaluateAndGenerate", status_code=status.HTTP_200_OK)
def evaluate_and_generate(
    interview_id: UUID = Form(...),
    question: str = Form(...),
    response_audio: UploadFile = File(...),
    db: Session = Depends(get_db_session),
    current_user: UserModel = Depends(get_current_user),
):
    """
    Evaluate the candidate's audio response and generate the next question.

    Accepts:
      - interview_id (form field)
      - question (form field) – the question that was asked
      - response_audio (file) – the candidate's audio response

    Flow:
      1. Transcribe the audio via the transcription service.
      2. Find the question record in the DB and store the response + transcript.
      3. Build previous_qa list from all answered questions.
      4. Call question-generation service to get the next question.
      5. Store evaluation scores from the metadata.
      6. Save the new question to the DB.
      7. Synthesize audio for the new question.
      8. Return binary audio with metadata in headers.
    """

    # ── 1. Verify the interview exists and is in progress ────────────────
    interview = (
        db.query(InterviewModel)
        .filter(InterviewModel.id == interview_id)
        .first()
    )

    if not interview:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Interview not found.",
        )

    if interview.status not in ("in_progress", "scheduled"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Interview is not active. Current status: {interview.status}",
        )

    # ── 2. Transcribe the audio response ─────────────────────────────────
    audio_bytes = response_audio.file.read()
    filename = response_audio.filename or "response.wav"
    transcript = _transcribe_audio(audio_bytes, filename)

    if not transcript:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Transcription service returned an empty transcript.",
        )

    # ── 3. Find the question record for the asked question ───────────────
    question_record = (
        db.query(InterviewQuestionModel)
        .filter(
            InterviewQuestionModel.interview_id == interview_id,
            InterviewQuestionModel.question_text == question,
        )
        .order_by(InterviewQuestionModel.question_order.desc())
        .first()
    )

    if not question_record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Question not found in the interview record.",
        )

    # ── 4. Build previous_qa from DB (all questions answered so far) ─────
    # First, save the current response so it's included in previous_qa
    new_response = InterviewResponseModel(
        interview_id=interview_id,
        question_id=question_record.id,
        transcript=transcript,
    )
    db.add(new_response)
    db.flush()  # Ensure it's saved before querying

    previous_qa = _get_previous_qa(db, interview_id)

    # ── 5. Generate next question ────────────────────────────────────────
    resume_json = _load_hardcoded_resume()
    qg_data = _generate_question(resume_json, previous_qa=previous_qa, difficulty="medium")
    next_question_text = qg_data["question"]
    metadata = qg_data.get("metadata", {})

    # ── 6. Extract evaluation scores and update the response record ──────
    evaluation = metadata.get("evaluation", {})
    ai_score = evaluation.get("score")
    remarks = evaluation.get("remarks", "")
    feedback = evaluation.get("feedback", "")

    # Store AI score and feedback in the response
    if ai_score is not None:
        new_response.ai_score = int(ai_score) if ai_score is not None else None
    # Store combined remarks/feedback in sentiment field (or you can use a separate field)
    if remarks or feedback:
        combined_feedback = f"{remarks} | {feedback}" if remarks and feedback else (remarks or feedback)
        new_response.sentiment = combined_feedback[:20] if combined_feedback else None
        # Also store full feedback in transcript-adjacent fields
        # We'll use communication_score and confidence_score for additional metadata
    
    db.flush()

    # ── 7. Save next question to the database ────────────────────────────
    existing_count = (
        db.query(InterviewQuestionModel)
        .filter(InterviewQuestionModel.interview_id == interview_id)
        .count()
    )
    sequence_number = existing_count + 1

    new_question = InterviewQuestionModel(
        interview_id=interview_id,
        question_text=next_question_text,
        question_order=sequence_number,
    )
    db.add(new_question)

    db.commit()
    db.refresh(new_question)
    db.refresh(new_response)

    # ── 8. Generate audio for the next question ──────────────────────────
    audio_bytes, content_type = _synthesize_audio(next_question_text)

    # ── 9. Return binary audio with metadata in headers ──────────────────
    return _build_audio_response(
        audio_bytes=audio_bytes,
        content_type=content_type,
        interview_id=interview_id,
        question_text=next_question_text,
        question_sequence=sequence_number,
    )
