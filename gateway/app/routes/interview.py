import io
import json
import os
from datetime import datetime, timedelta, timezone
from typing import Optional
from uuid import UUID

import httpx
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from fastapi.responses import JSONResponse, StreamingResponse
from sqlalchemy.orm import Session

from ..core.db import get_db_session
from ..models.interview_model import InterviewModel
from ..models.interview_question_model import InterviewQuestionModel
from ..models.interview_response_model import InterviewResponseModel
from ..models.application_model import ApplicationModel
from ..models.job_model import JobModel
from ..models.user import UserModel
from ..models.report_model import ReportModel
from ..models.interview import (
    InterviewScheduleRequest,
    InterviewScheduleResponse,
    StartInterviewRequest,
)
from ..core.security import RoleChecker, get_current_user

router = APIRouter()

# Only RECRUITER and ADMIN can schedule interviews
allow_recruiters = RoleChecker(["RECRUITER", "ADMIN"])

# How many questions to ask per category/skill before switching
QUESTIONS_PER_CATEGORY = 3

# Maximum number of interview questions
MAX_QUESTIONS = 10

# Answer timeout in seconds (5 minutes) — anti-cheat measure
ANSWER_TIMEOUT_SECONDS = 300

# Service URLs (use container names inside Docker, fallback for local dev)
QUESTION_GEN_URL = os.getenv("QUESTION_GEN_URL", "http://aicruit_question_generation:8010")
TTS_URL = os.getenv("TTS_URL", "http://aicruit_text_to_speech:8011")
TRANSCRIBE_URL = os.getenv("TRANSCRIBE_URL", "http://aicruit_audio_transcribe:8007")
REPORT_GEN_URL = os.getenv("REPORT_GEN_URL", "http://aicruit_report_generation:8012")

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

    # Inline fallback
    return {
        "name": "Ahmad Tariq",
        "email": "dev.ahmadtariq@gmail.com",
        "phone": "+92 320 484 6384",
        "location": "Islamabad, Pakistan",
        "linkedin": "https://linkedin.com/in/ahmad-tariq-",
        "github": "https://github.com/iAhmadTariq",
        "website": None,
        "summary": "Flutter Developer with proven expertise in building scalable, feature-rich applications.",
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
        ],
        "experience": [
            {
                "title": "Flutter Developer",
                "company": "Code Next Solutions",
                "location": "Islamabad, Pakistan",
                "start_date": "2024-07",
                "end_date": "Present",
                "duration_months": 2,
                "description": "Revamped MoltoVino, a wine restaurant app.",
                "technologies": ["Flutter", "Clean Architecture", "GoRouter", "Bloc", "GetIt"],
            },
        ],
        "projects": [],
        "publications": [],
        "certifications": [],
        "languages": [],
        "awards": [],
    }


def _generate_question(
    resume_json: dict,
    previous_qa: list,
    difficulty: str = "medium",
    category: Optional[str] = None,
) -> dict:
    """
    Call the question-generation service and return the full JSON response.
    'category' is passed to the service when provided (skill-based questions).
    """
    payload = {
        "resume_json": resume_json,
        "previous_qa": previous_qa,
        "difficulty": difficulty,
    }
    # Only include category in the payload when it's explicitly provided
    if category is not None:
        payload["category"] = category

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
    is_interview_ended: bool = False,
) -> StreamingResponse:
    """
    Build a StreamingResponse that sends the audio file as binary,
    with interview metadata in custom headers.
    """
    headers = {
        "X-Interview-Id": str(interview_id),
        "X-Question-Text": question_text.replace("\n", " "),
        "X-Question-Sequence": str(question_sequence),
        "X-Interview-Ended": "true" if is_interview_ended else "false",
        "Content-Disposition": f'attachment; filename="question_{question_sequence}.wav"',
        "Access-Control-Expose-Headers": "X-Interview-Id, X-Question-Text, X-Question-Sequence, X-Interview-Ended",
    }
    return StreamingResponse(
        io.BytesIO(audio_bytes),
        media_type=content_type,
        headers=headers,
    )


def _get_previous_qa_for_category(db: Session, interview_id, category: str) -> list[dict]:
    """
    Build the previous_qa list from questions of the SAME category only.
    Returns [{"Q": "...", "A": "..."}, ...].
    """
    questions = (
        db.query(InterviewQuestionModel)
        .filter(
            InterviewQuestionModel.interview_id == interview_id,
            InterviewQuestionModel.category == category,
        )
        .order_by(InterviewQuestionModel.question_order.asc())
        .all()
    )

    previous_qa = []
    for q in questions:
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


def _get_required_skills(db: Session, interview_id) -> list[str]:
    """
    Fetch the required_skills for the job associated with this interview.
    Path: interview → application → job → required_skills
    """
    interview = (
        db.query(InterviewModel)
        .filter(InterviewModel.id == interview_id)
        .first()
    )
    if not interview:
        return []

    application = (
        db.query(ApplicationModel)
        .filter(ApplicationModel.id == interview.application_id)
        .first()
    )
    if not application:
        return []

    job = (
        db.query(JobModel)
        .filter(JobModel.id == application.job_id)
        .first()
    )
    if not job or not job.required_skills:
        return []

    return job.required_skills  # JSONB column, returns a Python list


def _determine_next_category(db: Session, interview_id, required_skills: list[str]) -> tuple[str, bool]:
    """
    Determine which category (skill) to use for the next question.

    Returns (category, is_first_question_in_category).

    Logic:
    - Look at all questions asked so far, grouped by category.
    - If the current category has < QUESTIONS_PER_CATEGORY questions → continue same category.
    - Otherwise, move to the next skill in required_skills.
    """
    # Get all questions for this interview, ordered by sequence
    all_questions = (
        db.query(InterviewQuestionModel)
        .filter(InterviewQuestionModel.interview_id == interview_id)
        .order_by(InterviewQuestionModel.question_order.asc())
        .all()
    )

    # Count questions per category (excluding intro questions where category is None)
    category_counts: dict[str, int] = {}
    last_category = None
    for q in all_questions:
        if q.category is not None:
            category_counts[q.category] = category_counts.get(q.category, 0) + 1
            last_category = q.category

    # If no skill-based questions yet, start with the first skill
    if last_category is None:
        if required_skills:
            return required_skills[0], True
        return "general", True

    # Check how many questions the last category has
    count_in_last = category_counts.get(last_category, 0)

    if count_in_last < QUESTIONS_PER_CATEGORY:
        # Continue with the same category
        return last_category, False

    # Need to switch to a new category
    # Find current category's index in required_skills
    try:
        current_index = required_skills.index(last_category)
        next_index = current_index + 1
    except ValueError:
        next_index = 0

    if next_index < len(required_skills):
        return required_skills[next_index], True
    else:
        # All skills exhausted — cycle back or use "general"
        return "general", True


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
    Generates the FIRST question (intro) with NO prev_qa and NO category.

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

    # ── 2. Validate time window (commented out for development) ──────────
    # now = datetime.now(timezone.utc)
    # scheduled_at = interview.scheduled_at
    # if scheduled_at.tzinfo is None:
    #     scheduled_at = scheduled_at.replace(tzinfo=timezone.utc)
    # window_start = scheduled_at - timedelta(hours=1)
    # window_end = scheduled_at + timedelta(hours=1)
    # if not (window_start <= now <= window_end):
    #     raise HTTPException(status_code=400, detail="...")

    # ── 3. Load resume JSON (hardcoded for now) ──────────────────────────
    resume_json = _load_hardcoded_resume()

    # ── 4. Generate the first question (INTRO: no prev_qa, no category) ──
    qg_data = _generate_question(
        resume_json,
        previous_qa=[],  # No prev_qa for intro
        difficulty="medium",
        category=None,   # No category for intro
    )
    question_text = qg_data["question"]

    # ── 5. Save the question to the database (category = None = intro) ───
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
        category=None,  # Intro question has no category
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

    Category / skill-based logic:
      - Q1 (from /start): intro, no category, no prev_qa
      - Q2: first skill from required_skills, no prev_qa, prepend intro thank-you
      - Q3-Q4: same skill, WITH prev_qa from same category
      - Q5: switch to next skill, no prev_qa
      - Q6-Q7: same skill, WITH prev_qa from same category
      - ...repeats for each skill (3 questions per category)
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

    # ── 2. Check answer timeout (anti-cheat: 5 min max) ──────────────────
    last_question = (
        db.query(InterviewQuestionModel)
        .filter(InterviewQuestionModel.interview_id == interview_id)
        .order_by(InterviewQuestionModel.question_order.desc())
        .first()
    )
    if last_question and last_question.created_at:
        now_utc = datetime.now(timezone.utc)
        question_time = last_question.created_at
        if question_time.tzinfo is None:
            question_time = question_time.replace(tzinfo=timezone.utc)
        elapsed = (now_utc - question_time).total_seconds()
        if elapsed > ANSWER_TIMEOUT_SECONDS:
            # Candidate took too long — suspected cheating
            interview.status = "completed"
            application = db.query(ApplicationModel).filter(ApplicationModel.id == interview.application_id).first()
            if application:
                application.status = "INTERVIEW_COMPLETED"
            db.commit()
            return JSONResponse(
                content={
                    "is_interview_ended": True,
                    "question_text": "",
                    "question_sequence": 0,
                    "interview_id": str(interview_id),
                    "reason": "Answer timeout exceeded. Interview ended.",
                },
            )

    # ── 3. Transcribe the audio response ─────────────────────────────────
    audio_bytes = response_audio.file.read()
    filename = response_audio.filename or "response.wav"
    transcript = _transcribe_audio(audio_bytes, filename)

    if not transcript:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Transcription service returned an empty transcript.",
        )

    # ── 4. Find the question record for the asked question ───────────────
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

    # ── 5. Save the candidate's response ─────────────────────────────────
    new_response = InterviewResponseModel(
        interview_id=interview_id,
        question_id=question_record.id,
        transcript=transcript,
    )
    db.add(new_response)
    db.flush()

    # ── 6. Check if this was the last question (question limit reached) ──
    total_questions = (
        db.query(InterviewQuestionModel)
        .filter(InterviewQuestionModel.interview_id == interview_id)
        .count()
    )

    if total_questions >= MAX_QUESTIONS:
        # All questions have been answered — interview is complete
        interview.status = "completed"
        application = db.query(ApplicationModel).filter(ApplicationModel.id == interview.application_id).first()
        if application:
            application.status = "INTERVIEW_COMPLETED"
        db.commit()
        return JSONResponse(
            content={
                "is_interview_ended": True,
                "question_text": "",
                "question_sequence": total_questions,
                "interview_id": str(interview_id),
                "reason": "All questions answered. Interview completed.",
            },
        )

    # ── 7. Determine the next category and whether to pass prev_qa ───────
    required_skills = _get_required_skills(db, interview_id)
    next_category, is_first_in_category = _determine_next_category(
        db, interview_id, required_skills
    )

    # Build prev_qa: only pass it if we're continuing the SAME category
    # (not the first question in a new category)
    if is_first_in_category:
        previous_qa = []  # New category → fresh start, no prev_qa
    else:
        previous_qa = _get_previous_qa_for_category(db, interview_id, next_category)

    # ── 8. Generate next question ────────────────────────────────────────
    resume_json = _load_hardcoded_resume()
    qg_data = _generate_question(
        resume_json,
        previous_qa=previous_qa,
        difficulty="medium",
        category=next_category,
    )
    next_question_text = qg_data["question"]
    metadata = qg_data.get("metadata", {})

    # ── 9. Prepend intro thank-you if this is question 2 ─────────────────
    # total_questions is the count BEFORE adding the new question.
    # Question 1 = intro (already saved). So if total_questions == 1,
    # the next question being generated is Q2 → prepend thank-you.
    if total_questions == 1:
        next_question_text = (
            "Thank you for your introduction, now please tell me "
            + next_question_text
        )

    # ── 10. Extract evaluation scores and update the response record ─────
    evaluation = metadata.get("evaluation", {})
    ai_score = evaluation.get("score")
    remarks = evaluation.get("remarks", "")
    feedback = evaluation.get("feedback", "")
    print("remarks ", remarks)
    print("feedback ", feedback)
    print("ai_score ", ai_score)

    if ai_score is not None:
        new_response.ai_score = int(float(ai_score) * 100)
    
    # Store confidence if available
    confidence = evaluation.get("confidence")
    if confidence is not None:
        new_response.confidence_score = int(float(confidence) * 100)

    if remarks or feedback:
        combined = f"{remarks} | {feedback}" if remarks and feedback else (remarks or feedback)
        new_response.sentiment = str(combined)

    db.flush()

    # ── 11. Save next question to the database ───────────────────────────
    sequence_number = total_questions + 1

    new_question = InterviewQuestionModel(
        interview_id=interview_id,
        question_text=next_question_text,
        question_order=sequence_number,
        category=next_category,
    )
    db.add(new_question)

    db.commit()
    db.refresh(new_question)
    db.refresh(new_response)

    # ── 12. Generate audio for the next question ─────────────────────────
    audio_bytes, content_type = _synthesize_audio(next_question_text)

    # ── 13. Return binary audio with metadata in headers ─────────────────
    return _build_audio_response(
        audio_bytes=audio_bytes,
        content_type=content_type,
        interview_id=interview_id,
        question_text=next_question_text,
        question_sequence=sequence_number,
        is_interview_ended=False,
    )


# =========================================================
# END INTERVIEW
# =========================================================
@router.post("/end", status_code=status.HTTP_200_OK)
def end_interview(
    interview_id: UUID = Form(...),
    db: Session = Depends(get_db_session),
    current_user: UserModel = Depends(get_current_user),
):
    """
    End an interview. Sets the interview status to 'completed'.
    Called by the frontend when the interview is finished.
    """
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

    interview.status = "completed"
    application = db.query(ApplicationModel).filter(ApplicationModel.id == interview.application_id).first()
    if application:
        application.status = "INTERVIEW_COMPLETED"
        
    # Generate Report
    questions = (
        db.query(InterviewQuestionModel)
        .filter(InterviewQuestionModel.interview_id == interview.id)
        .order_by(InterviewQuestionModel.question_order.asc())
        .all()
    )
    
    payload_data = []
    for q in questions:
        resp = db.query(InterviewResponseModel).filter(InterviewResponseModel.question_id == q.id).first()
        ai_score = resp.ai_score if resp and resp.ai_score is not None else None
        
        # Normalize score
        score_out_of_5 = 1
        if ai_score is not None:
            # Current ai_score is percentage 0-100. Convert to 1-5.
            score_out_of_5 = max(1, min(5, round(ai_score * 5 / 100)))

        remarks = resp.sentiment if resp and resp.sentiment else ""
        
        payload_data.append({
            "q": q.question_text,
            "a": resp.transcript if resp and resp.transcript else "",
            "category": q.category or "Intro",
            "ai_score": score_out_of_5,
            "remarks": remarks
        })
        
    if payload_data:
        try:
            with httpx.Client(timeout=120.0) as client:
                report_resp = client.post(f"{REPORT_GEN_URL}/generate-report", json={"data": payload_data})
                report_resp.raise_for_status()
                report_data = report_resp.json()
                
                recruiter = report_data.get("recruiter_report", {})
                candidate = report_data.get("candidate_report", {})
                
                new_report = ReportModel(
                    interview_id=interview.id,
                    overall_score=recruiter.get("overall_score"),
                    category_scores=recruiter.get("category_scores"),
                    overall_remark=recruiter.get("overall_remark"),
                    strengths=candidate.get("strengths"),
                    improvements=candidate.get("improvements"),
                )
                db.add(new_report)
        except Exception as e:
            print(f"FAILED TO GENERATE REPORT: {e}")

    db.commit()

    return {"message": "Interview ended successfully.", "interview_id": str(interview_id)}

# =========================================================
# GET INTERVIEW DETAILS (RECRUITER/ADMIN ONLY)
# =========================================================
@router.get("/{application_id}/details", status_code=status.HTTP_200_OK)
def get_interview_details(
    application_id: UUID,
    db: Session = Depends(get_db_session),
    current_user: UserModel = Depends(RoleChecker(["RECRUITER", "ADMIN"])),
):
    """
    Get full details of an interview (questions, responses, ai scores, feedback)
    for a specific application. Restricted to Recruiters/Admins.
    """
    interview = db.query(InterviewModel).filter(InterviewModel.application_id == application_id).first()
    
    if not interview:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Interview not found for this application.",
        )
        
    questions = (
        db.query(InterviewQuestionModel)
        .filter(InterviewQuestionModel.interview_id == interview.id)
        .order_by(InterviewQuestionModel.question_order.asc())
        .all()
    )
    
    details = []
    for q in questions:
        # get response
        resp = db.query(InterviewResponseModel).filter(InterviewResponseModel.question_id == q.id).first()
        details.append({
            "question_order": q.question_order,
            "category": q.category,
            "question_text": q.question_text,
            "transcript": resp.transcript if resp else None,
            "ai_score": resp.ai_score if resp else None,
            "confidence_score": resp.confidence_score if resp else None,
            "sentiment": resp.sentiment if resp else None,
            "audio_url": resp.audio_url if resp else None,
            "video_url": resp.video_url if resp else None
        })
        
    report = db.query(ReportModel).filter(ReportModel.interview_id == interview.id).first()
    report_data = None
    if report:
        report_data = {
            "overall_score": report.overall_score,
            "category_scores": report.category_scores,
            "overall_remark": report.overall_remark,
            "strengths": report.strengths,
            "improvements": report.improvements
        }
        
    return {
        "interview_id": str(interview.id),
        "status": interview.status,
        "scheduled_at": interview.scheduled_at,
        "details": details,
        "report": report_data
    }
