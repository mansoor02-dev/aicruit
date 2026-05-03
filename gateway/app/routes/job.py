from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Query, Form
from sqlalchemy.orm import Session
from typing import List, Optional, Union
from datetime import date
import httpx
from uuid import UUID
import os
import json
from pydantic import BaseModel

from ..core.db import get_db_session
from ..models.job_model import JobModel
from ..models.application_model import ApplicationModel
from ..models.resume_model import ResumeModel
from ..models.resume_job_score_model import ResumeJobScoreModel
from ..models.user import UserModel
from ..models.job import JobCreate, JobResponse, JobUpdate, JobWithApplicantsResponse, JobForCandidateResponse, ApplicantInfo
from ..models.application import (
    ApplicationCreate,
    ApplicationResponse,
    ApplicationStageUpdate,
    ApplicationStageResponse,
    BoardInterview,
    BoardCandidate,
    BoardStage,
    BoardResponse,
    BulkMoveRequest,
    BulkMoveResponse,
)
from ..models.job_stage_model import JobStageModel
from ..models.interview_model import InterviewModel
from sqlalchemy.orm import joinedload
import logging
from ..models.job_stage import JobStageCreate, JobStageUpdate, JobStageResponse, StageReorderItem
from ..models.job_interview_settings_model import JobInterviewSettingsModel
from ..services import job_stages as stage_svc
from ..services import bulk_move as bulk_move_svc
from ..services.auto_schedule import auto_schedule as _run_auto_schedule
from ..core.security import get_current_user, RoleChecker

router = APIRouter()


def _resolve_ai_match_score(db: Session, resume_id: UUID, job_id: UUID) -> Optional[int]:
    """Look up the precomputed AI match score for this resume+job pair, if any."""
    row = (
        db.query(ResumeJobScoreModel)
        .filter_by(resume_id=resume_id, job_id=job_id)
        .first()
    )
    return row.overall if row else None


def _build_resume_url(file_url: str) -> str:
    """Build full resume download URL from the relative path stored in DB.
    
    Uses FILE_SERVICE_PUBLIC_URL (browser-accessible) for resume download links.
    Falls back to FILE_SERVICE_URL, then localhost:8005.
    """
    if not file_url:
        return ""
    # If it's already an absolute URL, return as-is
    if file_url.startswith("http://") or file_url.startswith("https://"):
        return file_url
    # Use public URL for browser access; falls back to internal URL then localhost
    file_service_url = os.getenv(
        "FILE_SERVICE_PUBLIC_URL",
        os.getenv("FILE_SERVICE_URL", "http://localhost:8005")
    )
    # The file-service stores paths like /uploads/Resume/file.pdf
    # and serves them under /static, so /uploads/X -> /static/X
    if file_url.startswith("/uploads/"):
        static_path = "/static/" + file_url[len("/uploads/"):]
    else:
        static_path = file_url
    return f"{file_service_url}{static_path}"

# Define Role Guards
allow_recruiters = RoleChecker(["RECRUITER", "ADMIN"])
allow_candidates = RoleChecker(["CANDIDATE"])
allow_anyone = get_current_user # Just needs to be logged in

# =========================================================
# 1. CREATE JOB (Recruiters Only)
# =========================================================
@router.post("/", response_model=JobResponse, status_code=status.HTTP_201_CREATED)
def create_job(
    job_data: JobCreate,
    db: Session = Depends(get_db_session),
    current_user: UserModel = Depends(allow_recruiters) # <--- Security Gate
):
    # Double check Recruiter Profile exists
    if not current_user.recruiter:
        raise HTTPException(status_code=400, detail="Recruiter profile incomplete")

    # Serialize application_questions (Pydantic models -> plain dicts) for JSONB storage
    payload = job_data.dict()
    payload["application_questions"] = [
        q if isinstance(q, dict) else q.dict()
        for q in (job_data.application_questions or [])
    ]

    # SaaS Logic: Link to the Recruiter's Company automatically
    new_job = JobModel(
        **payload,
        recruiter_id=current_user.recruiter.id,
        company_id=current_user.recruiter.company_id,
        status="OPEN"
    )
    
    db.add(new_job)
    db.commit()
    db.refresh(new_job)
    
    return new_job

# =========================================================
# 2. LIST JOBS (Smart View - Role Based)
# =========================================================
@router.get("/", response_model=List)
def get_jobs(
    db: Session = Depends(get_db_session),
    current_user: UserModel = Depends(allow_anyone) # <--- Any logged in user
):
    if current_user.role == "RECRUITER":
        # VIEW A: Recruiter sees THEIR Company's jobs with applicants
        if not current_user.recruiter:
             return []
        
        jobs = db.query(JobModel).filter(
            JobModel.company_id == current_user.recruiter.company_id
        ).all()
        
        result = []
        for job in jobs:
            # Get all applications for this job
            applications = db.query(ApplicationModel).filter(
                ApplicationModel.job_id == job.id
            ).all()
            
            applicants = []
            for app in applications:
                candidate = app.candidate
                user = candidate.user
                resume = app.resume
                
                applicants.append(
                    ApplicantInfo(
                        application_id=app.id,
                        application_status=app.status,
                        ai_match_score=app.ai_match_score,
                        applied_at=app.created_at,
                        candidate_id=candidate.id,
                        candidate_name=app.applicant_name or user.full_name,
                        candidate_email=app.applicant_email or user.email,
                        candidate_phone=app.applicant_phone or candidate.phone,
                        candidate_linkedin=candidate.linkedin_url if hasattr(candidate, 'linkedin_url') else None,
                        resume_id=resume.id if resume else None,
                        resume_url=_build_resume_url(resume.file_url) if resume else "",
                    )
                )
            
            result.append(
                JobWithApplicantsResponse(
                    id=job.id,
                    company_id=job.company_id,
                    recruiter_id=job.recruiter_id,
                    status=job.status,
                    created_at=job.created_at,
                    title=job.title,
                    description=job.description,
                    location=job.location,
                    type=job.type,
                    salary_min=job.salary_min,
                    salary_max=job.salary_max,
                    required_skills=job.required_skills or [],
                    experience_level=job.experience_level,
                    last_date_to_apply=job.last_date_to_apply,
                    application_questions=job.application_questions or [],
                    applicants=applicants,
                )
            )
        
        return result
        
    else:
        # VIEW B: Candidates see ALL Companies' jobs (Only Open)
        jobs = db.query(JobModel).filter(
            JobModel.status == 'OPEN'
        ).all()
        
        return [
            JobForCandidateResponse(
                id=job.id,
                company_id=job.company_id,
                status=job.status,
                created_at=job.created_at,
                title=job.title,
                description=job.description,
                location=job.location,
                type=job.type,
                salary_min=job.salary_min,
                salary_max=job.salary_max,
                required_skills=job.required_skills or [],
                experience_level=job.experience_level,
                last_date_to_apply=job.last_date_to_apply,
                application_questions=job.application_questions or [],
            )
            for job in jobs
        ]



# =========================================================
# 4. UPDATE JOB (Recruiters Only)
# =========================================================
@router.put("/{job_id}", response_model=JobResponse)
def update_job(
    job_id: str,
    job_data: JobUpdate,
    db: Session = Depends(get_db_session),
    current_user: UserModel = Depends(allow_recruiters)
):
    # Get the job
    job = db.query(JobModel).filter(JobModel.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    # Ensure recruiter owns this job (via company)
    if not current_user.recruiter or job.company_id != current_user.recruiter.company_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, 
            detail="You can only update jobs from your company"
        )
    
    # Update only provided fields
    update_data = job_data.dict(exclude_unset=True)
    if "application_questions" in update_data and update_data["application_questions"] is not None:
        update_data["application_questions"] = [
            q if isinstance(q, dict) else q.dict()
            for q in update_data["application_questions"]
        ]
    for field, value in update_data.items():
        setattr(job, field, value)
    
    db.commit()
    db.refresh(job)
    
    return job

# =========================================================
# 5a. UPLOAD & PARSE RESUME (Candidates Only)
# =========================================================
logger = logging.getLogger(__name__)


@router.post("/upload-resume", status_code=status.HTTP_200_OK)
async def upload_and_parse_resume(
    file: UploadFile = File(...),
    job_id: Optional[UUID] = Form(None),
    db: Session = Depends(get_db_session),
    current_user: UserModel = Depends(allow_candidates)
):
    """
    1. Upload the resume file to the file-service
    2. Create a resume record in the database
    3. Call the resume-parser microservice to parse the resume
    4. Return the parsed data for form autofill
    """
    try:
        if not current_user.candidate:
            raise HTTPException(status_code=400, detail="Candidate profile incomplete")

        # Validate file type
        filename = file.filename or ""
        if not filename.lower().endswith((".pdf", ".docx")):
            raise HTTPException(status_code=400, detail="Only PDF and DOCX files are supported")

        contents = await file.read()
        if len(contents) > 10 * 1024 * 1024:
            raise HTTPException(status_code=413, detail="File exceeds 10 MB limit")

        # Step 1: Upload to file-service
        file_service_url = os.getenv("FILE_SERVICE_URL", "http://localhost:8005")
        async with httpx.AsyncClient() as client:
            upload_response = await client.post(
                f"{file_service_url}/upload-file",
                files={"file": (filename, contents, file.content_type or "application/octet-stream")},
                data={"file_type": "Resume"},
                timeout=30.0
            )
            if upload_response.status_code != 200:
                raise HTTPException(status_code=502, detail="Failed to upload file to storage service")
            upload_data = upload_response.json()
            file_url = upload_data.get("file_url", "")

        if not file_url:
            raise HTTPException(status_code=502, detail="File service did not return a valid URL")

        # Step 2: Create resume record in DB
        new_resume = ResumeModel(
            candidate_id=current_user.candidate.id,
            file_url=file_url,
        )
        db.add(new_resume)
        db.commit()
        db.refresh(new_resume)

        # Step 3: Call resume-parser microservice
        parsed_data = None
        try:
            resume_parser_url = os.getenv("RESUME_PARSER_URL", "http://localhost:8006")
            async with httpx.AsyncClient() as client:
                parse_response = await client.post(
                    f"{resume_parser_url}/parse-resume",
                    json={"resume_id": str(new_resume.id)},
                    timeout=60.0
                )
                if parse_response.status_code == 200:
                    parse_result = parse_response.json()
                    print(f"✅ Resume {new_resume.id} parsed successfully")

                    # Reload resume to get parsed_text (full parsed JSON)
                    db.refresh(new_resume)
                    if new_resume.parsed_text:
                        try:
                            parsed_data = json.loads(new_resume.parsed_text)
                        except (json.JSONDecodeError, TypeError):
                            parsed_data = None
                else:
                    print(f"⚠️ Resume parsing returned status {parse_response.status_code}")
        except Exception as parse_err:
            print(f"⚠️ Failed to call parse-resume service: {parse_err}")

        # Step 3.5: If job_id provided, score the resume against the job (best-effort)
        if job_id is not None:
            job = db.query(JobModel).filter(JobModel.id == job_id).first()
            if job is None or job.status != "OPEN":
                logger.warning(
                    "upload_resume.score_skipped_job",
                    extra={"job_id": str(job_id), "reason": "missing_or_closed"},
                )
            else:
                job_payload = {
                    "title": job.title,
                    "description": job.description,
                    "required_skills": job.required_skills or [],
                    "experience_level": job.experience_level,
                    "location": job.location,
                    "type": job.type,
                }
                from ..services.resume_scoring import score_resume_for_job
                from ..models.resume_job_score_model import ResumeJobScoreModel
                from sqlalchemy.dialects.postgresql import insert as pg_insert
                from sqlalchemy import func

                score = await score_resume_for_job(parsed_data or {}, job_payload)
                if score is not None:
                    stmt = pg_insert(ResumeJobScoreModel).values(
                        resume_id=new_resume.id, job_id=job_id, overall=score
                    ).on_conflict_do_update(
                        index_elements=["resume_id", "job_id"],
                        set_={"overall": score, "updated_at": func.now()},
                    )
                    db.execute(stmt)
                    db.commit()

        # Step 4: Return resume info + parsed data
        # The parser returns: { personal_info: {name, email, ...}, skills: [...], ... }
        d = parsed_data or {}
        pi = d.get("personal_info", {}) or {}

        # Normalize education entries: parser uses "institution", frontend expects "university"
        raw_edu = d.get("education", []) or []
        education = []
        for e in raw_edu:
            if not isinstance(e, dict):
                continue
            education.append({
                "university": e.get("institution") or e.get("university") or "",
                "degree": e.get("degree", ""),
                "field": e.get("field", ""),
                "start_year": e.get("start_year") or e.get("duration", "").split("-")[0].strip() if e.get("start_year") or e.get("duration") else "",
                "end_year": e.get("end_year") or (e.get("duration", "").split("-")[-1].strip() if e.get("duration") else ""),
            })

        # Normalize experience entries
        raw_exp = d.get("experience", []) or []
        experience = []
        for e in raw_exp:
            if not isinstance(e, dict):
                continue
            desc = e.get("description", "")
            if isinstance(desc, list):
                desc = " ".join(desc)
            experience.append({
                "title": e.get("title", ""),
                "company": e.get("company", ""),
                "start_date": e.get("start_date") or e.get("duration", "").split("-")[0].strip() if e.get("start_date") or e.get("duration") else "",
                "end_date": e.get("end_date") or (e.get("duration", "").split("-")[-1].strip() if e.get("duration") else ""),
                "description": desc,
            })

        # Normalize project entries
        raw_proj = d.get("projects", []) or []
        projects = []
        for p in raw_proj:
            if not isinstance(p, dict):
                continue
            desc = p.get("description", "")
            if isinstance(desc, list):
                desc = " ".join(desc)
            projects.append({
                "title": p.get("name") or p.get("title", ""),
                "description": desc,
            })

        return {
            "resume_id": str(new_resume.id),
            "file_url": file_url,
            "parsed": parsed_data is not None,
            "data": {
                "name": pi.get("name", "") or d.get("name", ""),
                "email": pi.get("email", "") or d.get("email", ""),
                "phone": pi.get("phone", "") or d.get("phone", ""),
                "location": pi.get("location", "") or d.get("location", ""),
                "summary": d.get("summary", ""),
                "skills": d.get("skills", []) or [],
                "education": education,
                "experience": experience,
                "projects": projects,
            }
        }

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to upload and parse resume: {str(e)}")


# =========================================================
# 5b. APPLY TO JOB (Candidates Only)
# =========================================================
@router.post("/apply", response_model=ApplicationResponse, status_code=status.HTTP_201_CREATED)
async def apply_to_job(
    application_data: ApplicationCreate,
    db: Session = Depends(get_db_session),
    current_user: UserModel = Depends(allow_candidates)
):
    try:
        # Ensure candidate profile exists
        if not current_user.candidate:
            raise HTTPException(status_code=400, detail="Candidate profile incomplete")
        
        # Check if job exists and is still open
        job = db.query(JobModel).filter(JobModel.id == application_data.job_id).first()
        if not job:
            raise HTTPException(status_code=404, detail="Job not found")
        
        if job.status != "OPEN":
            raise HTTPException(status_code=400, detail="This job is no longer accepting applications")
        
        # Check if application deadline passed (if set)
        if job.last_date_to_apply:
            from datetime import datetime
            if datetime.now() > job.last_date_to_apply:
                raise HTTPException(status_code=400, detail="Application deadline has passed")
        
        # Check if candidate already applied
        existing_application = db.query(ApplicationModel).filter(
            ApplicationModel.job_id == application_data.job_id,
            ApplicationModel.candidate_id == current_user.candidate.id
        ).first()
        
        if existing_application:
            raise HTTPException(status_code=400, detail="You have already applied to this job")
        
        # Verify the resume exists and belongs to this candidate
        resume = db.query(ResumeModel).filter(
            ResumeModel.id == application_data.resume_id,
            ResumeModel.candidate_id == current_user.candidate.id
        ).first()
        
        if not resume:
            raise HTTPException(status_code=400, detail="Resume not found or does not belong to you")

        # Serialize nested pydantic models to dicts for JSONB storage
        education_data = [e.dict() for e in application_data.education] if application_data.education else []
        experience_data = [e.dict() for e in application_data.experience] if application_data.experience else []
        projects_data = [p.dict() for p in application_data.projects] if application_data.projects else []

        # ---- Validate custom application questions defined on the job ----
        job_questions = job.application_questions or []
        responses_by_qid = {}
        for r in (application_data.question_responses or []):
            qid = r.question_id if hasattr(r, "question_id") else r.get("question_id")
            responses_by_qid[qid] = r

        validated_responses = []
        for q in job_questions:
            qid = q.get("id") if isinstance(q, dict) else getattr(q, "id", None)
            label = (q.get("label") if isinstance(q, dict) else getattr(q, "label", "")) or ""
            qtype = (q.get("type") if isinstance(q, dict) else getattr(q, "type", "text")) or "text"
            required = bool(q.get("required") if isinstance(q, dict) else getattr(q, "required", False))
            min_length = q.get("min_length") if isinstance(q, dict) else getattr(q, "min_length", None)
            max_length = q.get("max_length") if isinstance(q, dict) else getattr(q, "max_length", None)

            r = responses_by_qid.get(qid)
            if r is None:
                value = None
            elif hasattr(r, "value"):
                value = r.value
            else:
                value = r.get("value")

            if required and (value is None or (isinstance(value, str) and value.strip() == "")):
                raise HTTPException(status_code=400, detail=f"Question {label!r} is required.")

            if isinstance(value, str) and qtype in ("text", "textarea"):
                length = len(value)
                if min_length is not None and length < int(min_length):
                    raise HTTPException(
                        status_code=400,
                        detail=f"{label!r} must be at least {min_length} characters.",
                    )
                if max_length is not None and length > int(max_length):
                    raise HTTPException(
                        status_code=400,
                        detail=f"{label!r} must be at most {max_length} characters.",
                    )

            validated_responses.append({
                "question_id": qid,
                "label": label,
                "type": qtype,
                "value": value,
            })

        # Look up the first stage of the job so the new application lands on the board
        first_stage = (
            db.query(JobStageModel)
            .filter(JobStageModel.job_id == job.id)
            .order_by(JobStageModel.position.asc())
            .first()
        )

        # Resolve precomputed AI match score (Wave 2 Slice D)
        ai_match_score = _resolve_ai_match_score(db, resume.id, application_data.job_id)

        # Create application with all candidate-submitted form data
        new_application = ApplicationModel(
            job_id=application_data.job_id,
            candidate_id=current_user.candidate.id,
            resume_id=resume.id,
            applicant_name=application_data.applicant_name,
            applicant_email=application_data.applicant_email,
            applicant_phone=application_data.applicant_phone,
            applicant_location=application_data.applicant_location,
            summary=application_data.summary or "",
            skills=application_data.skills or [],
            education=education_data,
            experience=experience_data,
            projects=projects_data,
            question_responses=validated_responses,
            stage_id=first_stage.id if first_stage else None,
            # NOTE: applications.status has a CHECK constraint that restricts it
            # to a fixed enum (APPLIED, SCREENING, INTERVIEW_SCHEDULED,
            # INTERVIEW_COMPLETED, OFFERED, REJECTED). Stage names are
            # recruiter-defined free text (e.g. "Phone Screen") and would violate
            # the constraint. The kanban board uses stage_id as the source of
            # truth for column placement, so we leave status as APPLIED on
            # creation and let the stage-update endpoint manage transitions.
            status="APPLIED",
            ai_match_score=ai_match_score,
        )

        db.add(new_application)
        db.commit()
        db.refresh(new_application)

        return new_application
    except HTTPException as he:
        raise he
    except Exception as e:
        logger.exception("apply_to_job failed")
        db.rollback()
        raise HTTPException(status_code=500, detail="Failed to apply to job: " + str(e))

# =========================================================
# 6. GET MY APPLICATIONS (Candidates Only)
# =========================================================
@router.get("/my-applications", response_model=List)
def get_my_applications(
    db: Session = Depends(get_db_session),
    current_user: UserModel = Depends(allow_candidates)
):
    from ..models.job import MyApplicationResponse
    
    # Ensure candidate profile exists
    if not current_user.candidate:
        raise HTTPException(status_code=400, detail="Candidate profile incomplete")
    
    # Query all applications for this candidate with job details
    applications = db.query(ApplicationModel).filter(
        ApplicationModel.candidate_id == current_user.candidate.id
    ).all()
    
    result = []
    for app in applications:
        job = app.job
        
        # Check for scheduled interview
        scheduled_at = None
        if hasattr(app, 'interviews') and app.interviews:
            # Sort by created_at desc to get latest
            sorted_interviews = sorted(app.interviews, key=lambda x: x.created_at, reverse=True)
            if sorted_interviews:
                 scheduled_at = sorted_interviews[0].scheduled_at

        result.append(
            MyApplicationResponse(
                application_id=app.id,
                application_status=app.status,
                applied_at=app.created_at,
                job_id=job.id,
                job_title=job.title,
                job_description=job.description,
                location=job.location,
                job_type=job.type,
                salary_min=job.salary_min,
                salary_max=job.salary_max,
                required_skills=job.required_skills,
                experience_level=job.experience_level,
                last_date_to_apply=job.last_date_to_apply,
                job_status=job.status,
                job_created_at=job.created_at,
                scheduled_at=scheduled_at
            )
        )
    
    return result


# =========================================================
# 3. GET JOB DETAILS (Role-Based Response)
# =========================================================
@router.get("/{job_id}", response_model=Union[JobWithApplicantsResponse, JobForCandidateResponse])
def get_job_detail(
    job_id: str,
    db: Session = Depends(get_db_session),
    current_user: UserModel = Depends(allow_anyone)
):
    # Validate job_id
    try:
        UUID(job_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Job not found")

    job = db.query(JobModel).filter(JobModel.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    if current_user.role == "RECRUITER":
        # For Recruiter: Return job with all applicants
        if not current_user.recruiter:
            raise HTTPException(status_code=403, detail="Recruiter profile incomplete")
        
        # Ensure recruiter owns this job (via company)
        if job.company_id != current_user.recruiter.company_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You can only view jobs from your company"
            )
        
        # Get all applications for this job
        applications = db.query(ApplicationModel).filter(
            ApplicationModel.job_id == job.id
        ).all()
        
        applicants = []
        for app in applications:
            candidate = app.candidate
            user = candidate.user
            resume = app.resume
            
            applicants.append(
                ApplicantInfo(
                    application_id=app.id,
                    application_status=app.status,
                    ai_match_score=app.ai_match_score,
                    applied_at=app.created_at,
                    candidate_id=candidate.id,
                    candidate_name=app.applicant_name or user.full_name,
                    candidate_email=app.applicant_email or user.email,
                    candidate_phone=app.applicant_phone or candidate.phone,
                    candidate_linkedin=candidate.linkedin_url if hasattr(candidate, 'linkedin_url') else None,
                    resume_id=resume.id if resume else None,
                    resume_url=_build_resume_url(resume.file_url) if resume else "",
                )
            )
        
        return JobWithApplicantsResponse(
            id=job.id,
            company_id=job.company_id,
            recruiter_id=job.recruiter_id,
            status=job.status,
            created_at=job.created_at,
            title=job.title,
            description=job.description,
            location=job.location,
            type=job.type,
            salary_min=job.salary_min,
            salary_max=job.salary_max,
            required_skills=job.required_skills or [],
            experience_level=job.experience_level,
            last_date_to_apply=job.last_date_to_apply,
            application_questions=job.application_questions or [],
            applicants=applicants,
        )
    
    else:
        # For Candidate: Return basic job details
        if job.status != "OPEN":
            raise HTTPException(status_code=404, detail="Job not found")
        
        return JobForCandidateResponse(
            id=job.id,
            company_id=job.company_id,
            status=job.status,
            created_at=job.created_at,
            title=job.title,
            description=job.description,
            location=job.location,
            type=job.type,
            salary_min=job.salary_min,
            salary_max=job.salary_max,
            required_skills=job.required_skills or [],
            experience_level=job.experience_level,
            last_date_to_apply=job.last_date_to_apply,
            application_questions=job.application_questions or [],
        )

# =========================================================
# 7. DELETE / CLOSE JOB (Recruiters Only)
# =========================================================
@router.delete("/{job_id}", status_code=status.HTTP_200_OK)
def delete_job(
    job_id: str,
    db: Session = Depends(get_db_session),
    current_user: UserModel = Depends(allow_recruiters)
):
    job = db.query(JobModel).filter(JobModel.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
        
    if not current_user.recruiter or job.company_id != current_user.recruiter.company_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, 
            detail="You can only delete jobs from your company"
        )
        
    db.delete(job)
    db.commit()
    return {"message": "Job deleted successfully"}

# =========================================================
# 8. GET APPLICATION DETAILS (Recruiters Only)
# =========================================================
@router.get("/application/{application_id}")
def get_application_detail(
    application_id: str,
    db: Session = Depends(get_db_session),
    current_user: UserModel = Depends(allow_recruiters)
):
    """Return full candidate application details for recruiter view."""
    try:
        UUID(application_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Application not found")

    application = db.query(ApplicationModel).filter(
        ApplicationModel.id == application_id
    ).first()
    
    if not application:
        raise HTTPException(status_code=404, detail="Application not found")
    
    # Verify recruiter has access (owns the job's company)
    job = application.job
    if not current_user.recruiter or job.company_id != current_user.recruiter.company_id:
        raise HTTPException(status_code=403, detail="You don't have access to this application")
    
    candidate = application.candidate
    user = candidate.user
    resume = application.resume
    
    return {
        "application_id": str(application.id),
        "job_id": str(job.id),
        "job_title": job.title,
        "application_status": application.status,
        "ai_match_score": application.ai_match_score,
        "applied_at": application.created_at.isoformat() if application.created_at else None,
        # Candidate details from application form
        "applicant_name": application.applicant_name or user.full_name,
        "applicant_email": application.applicant_email or user.email,
        "applicant_phone": application.applicant_phone or candidate.phone or "",
        "applicant_location": application.applicant_location or "",
        "summary": application.summary or "",
        "skills": application.skills or [],
        "education": application.education or [],
        "experience": application.experience or [],
        "projects": application.projects or [],
        # Custom recruiter-defined questions (definitions on the job + candidate answers)
        "application_questions": job.application_questions or [],
        "question_responses": application.question_responses or [],
        # Resume
        "resume_id": str(resume.id) if resume else None,
        "resume_url": _build_resume_url(resume.file_url) if resume else "",
    }


# =========================================================
# 9. STAGE CRUD (Recruiters Only)
# =========================================================
def _get_owned_job(job_id: str, db: Session, current_user: UserModel) -> JobModel:
    try:
        UUID(job_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Job not found")

    job = db.query(JobModel).filter(JobModel.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    if not current_user.recruiter or job.company_id != current_user.recruiter.company_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only manage jobs from your company"
        )
    return job


@router.get("/{job_id}/stages", response_model=List[JobStageResponse])
def list_job_stages(
    job_id: str,
    db: Session = Depends(get_db_session),
    current_user: UserModel = Depends(allow_recruiters)
):
    job = _get_owned_job(job_id, db, current_user)
    return stage_svc.list_stages(db, job.id)


@router.post("/{job_id}/stages", response_model=JobStageResponse, status_code=status.HTTP_201_CREATED)
def create_job_stage(
    job_id: str,
    payload: JobStageCreate,
    db: Session = Depends(get_db_session),
    current_user: UserModel = Depends(allow_recruiters)
):
    job = _get_owned_job(job_id, db, current_user)
    return stage_svc.create_stage(db, job.id, name=payload.name, position=payload.position)


@router.patch("/{job_id}/stages/{stage_id}", response_model=JobStageResponse)
def rename_job_stage(
    job_id: str,
    stage_id: UUID,
    payload: JobStageUpdate,
    db: Session = Depends(get_db_session),
    current_user: UserModel = Depends(allow_recruiters)
):
    job = _get_owned_job(job_id, db, current_user)
    if payload.name is None:
        raise HTTPException(status_code=400, detail="name is required")
    try:
        return stage_svc.rename_stage(db, job.id, stage_id, payload.name)
    except stage_svc.StageNotFoundError:
        raise HTTPException(status_code=404, detail="Stage not found")


@router.put("/{job_id}/stages/reorder", response_model=List[JobStageResponse])
def reorder_job_stages(
    job_id: str,
    items: List[StageReorderItem],
    db: Session = Depends(get_db_session),
    current_user: UserModel = Depends(allow_recruiters)
):
    job = _get_owned_job(job_id, db, current_user)
    try:
        return stage_svc.reorder_stages(db, job.id, items)
    except stage_svc.StageReorderMismatchError:
        raise HTTPException(status_code=400, detail="Reorder body must include all stages of this job")


@router.delete("/{job_id}/stages/{stage_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_job_stage(
    job_id: str,
    stage_id: UUID,
    move_to: Optional[UUID] = None,
    db: Session = Depends(get_db_session),
    current_user: UserModel = Depends(allow_recruiters)
):
    job = _get_owned_job(job_id, db, current_user)
    try:
        stage_svc.delete_stage(db, job.id, stage_id, move_to=move_to)
    except stage_svc.StageNotFoundError:
        raise HTTPException(status_code=404, detail="Stage not found")
    except stage_svc.InvalidMoveTargetError:
        raise HTTPException(status_code=422, detail="move_to does not exist on this job")
    except stage_svc.StageConflictError as e:
        raise HTTPException(
            status_code=409,
            detail={"candidate_count": e.candidate_count, "message": "Stage has candidates; provide move_to"}
        )
    return None


# =========================================================
# 10. AI INTERVIEW AUTO-SCHEDULE (Recruiters Only)
# =========================================================
class AutoScheduleRequest(BaseModel):
    stage_id: UUID
    start_date: date
    end_date: date


def _ensure_ai_enabled(db: Session, job_id) -> None:
    settings = (
        db.query(JobInterviewSettingsModel)
        .filter(JobInterviewSettingsModel.job_id == job_id)
        .first()
    )
    if settings is None or not settings.ai_interview_enabled:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="AI interview not enabled for this job",
        )


@router.post("/{job_id}/auto-schedule")
def auto_schedule_endpoint(
    job_id: str,
    payload: AutoScheduleRequest,
    db: Session = Depends(get_db_session),
    current_user: UserModel = Depends(allow_recruiters),
):
    job = _get_owned_job(job_id, db, current_user)
    _ensure_ai_enabled(db, job.id)
    if payload.end_date < payload.start_date:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="end_date must be on or after start_date",
        )
    return _run_auto_schedule(
        db,
        job,
        payload.stage_id,
        payload.start_date,
        payload.end_date,
        dry_run=False,
    )


@router.get("/{job_id}/auto-schedule/preview")
def auto_schedule_preview(
    job_id: str,
    stage_id: UUID = Query(...),
    start_date: date = Query(...),
    end_date: date = Query(...),
    db: Session = Depends(get_db_session),
    current_user: UserModel = Depends(allow_recruiters),
):
    job = _get_owned_job(job_id, db, current_user)
    _ensure_ai_enabled(db, job.id)
    if end_date < start_date:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="end_date must be on or after start_date",
        )
    return _run_auto_schedule(
        db,
        job,
        stage_id,
        start_date,
        end_date,
        dry_run=True,
    )


# =========================================================
# 11. CANDIDATE STAGE ASSIGNMENT (Recruiters Only)
# =========================================================
_logger = logging.getLogger(__name__)


@router.patch(
    "/{job_id}/applications/{application_id}/stage",
    response_model=ApplicationStageResponse,
)
def update_application_stage(
    job_id: str,
    application_id: UUID,
    payload: ApplicationStageUpdate,
    db: Session = Depends(get_db_session),
    current_user: UserModel = Depends(allow_recruiters),
):
    job = _get_owned_job(job_id, db, current_user)

    if not payload.rejected and payload.stage_id is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Either stage_id or rejected must be provided",
        )

    application = (
        db.query(ApplicationModel)
        .filter(
            ApplicationModel.id == application_id,
            ApplicationModel.job_id == job.id,
        )
        .first()
    )
    if not application:
        raise HTTPException(status_code=404, detail="Application not found")

    if payload.rejected:
        application.status = "REJECTED"
    else:
        stage = (
            db.query(JobStageModel)
            .filter(
                JobStageModel.id == payload.stage_id,
                JobStageModel.job_id == job.id,
            )
            .first()
        )
        if not stage:
            raise HTTPException(
                status_code=400,
                detail="Stage does not belong to this job",
            )
        application.stage_id = stage.id
        application.status = stage.name

    db.commit()
    db.refresh(application)
    return ApplicationStageResponse(
        application_id=application.id,
        stage_id=application.stage_id,
        status=application.status,
    )


# =========================================================
# 12. KANBAN BOARD FETCH (Recruiters Only)
# =========================================================
def _pick_interview(interviews):
    """Pick the most-recent active interview, else the most-recent of any."""
    if not interviews:
        return None
    active_states = {"scheduled", "in_progress", "expired"}
    active = [i for i in interviews if i.status in active_states]
    pool = active if active else list(interviews)
    return max(pool, key=lambda i: i.created_at)


def _build_board_candidate(app: ApplicationModel) -> BoardCandidate:
    candidate = app.candidate
    user = candidate.user if candidate else None
    resume = app.resume
    interview_obj = _pick_interview(app.interviews) if hasattr(app, "interviews") else None
    interview_payload = None
    if interview_obj is not None:
        interview_payload = BoardInterview(
            id=interview_obj.id,
            status=interview_obj.status,
            scheduled_at=interview_obj.scheduled_at,
            expires_at=interview_obj.expires_at,
        )
    return BoardCandidate(
        application_id=app.id,
        candidate_id=candidate.id,
        candidate_name=app.applicant_name or (user.full_name if user else ""),
        candidate_email=app.applicant_email or (user.email if user else ""),
        applied_at=app.created_at,
        resume_url=_build_resume_url(resume.file_url) if resume else "",
        stage_id=app.stage_id,
        status=app.status,
        ai_match_score=app.ai_match_score,
        interview=interview_payload,
    )


@router.get("/{job_id}/board", response_model=BoardResponse)
def get_job_board(
    job_id: str,
    db: Session = Depends(get_db_session),
    current_user: UserModel = Depends(allow_recruiters),
):
    job = _get_owned_job(job_id, db, current_user)

    stages = (
        db.query(JobStageModel)
        .filter(JobStageModel.job_id == job.id)
        .order_by(JobStageModel.position.asc())
        .all()
    )

    applications = (
        db.query(ApplicationModel)
        .options(joinedload(ApplicationModel.interviews))
        .filter(ApplicationModel.job_id == job.id)
        .all()
    )

    stage_buckets: dict = {s.id: [] for s in stages}
    rejected: list = []

    # First stage (lowest position) is used as a fallback bucket for orphaned
    # applications (no stage_id, or stage_id pointing at a stage that no longer
    # belongs to the job). We only use it for display; we do not mutate the DB.
    fallback_stage_id = stages[0].id if stages else None

    for app in applications:
        candidate_payload = _build_board_candidate(app)
        if app.status == "REJECTED":
            rejected.append(candidate_payload)
            continue
        if app.stage_id is not None and app.stage_id in stage_buckets:
            stage_buckets[app.stage_id].append(candidate_payload)
            continue
        # Orphan: missing or stale stage_id -> bucket into first stage if any
        if fallback_stage_id is not None:
            _logger.warning(
                "Application %s on job %s has missing/stale stage_id %s; "
                "bucketing into first stage %s for display",
                app.id,
                job.id,
                app.stage_id,
                fallback_stage_id,
            )
            stage_buckets[fallback_stage_id].append(candidate_payload)
            continue
        _logger.warning(
            "Application %s on job %s has no stage and job has zero stages; skipping",
            app.id,
            job.id,
        )

    board_stages: List[BoardStage] = []
    for s in stages:
        bucket = stage_buckets[s.id]
        bucket.sort(key=lambda c: c.applied_at, reverse=True)
        board_stages.append(
            BoardStage(id=s.id, position=s.position, name=s.name, candidates=bucket)
        )

    rejected.sort(key=lambda c: c.applied_at, reverse=True)
    return BoardResponse(stages=board_stages, rejected=rejected)


# =========================================================
# 13. BULK MOVE BY AI SCORE (Recruiters Only)
# =========================================================
@router.post(
    "/{job_id}/stages/{stage_id}/bulk-move",
    response_model=BulkMoveResponse,
)
def stage_bulk_move(
    job_id: str,
    stage_id: UUID,
    body: BulkMoveRequest,
    db: Session = Depends(get_db_session),
    current_user: UserModel = Depends(allow_recruiters),
):
    _get_owned_job(job_id, db, current_user)
    try:
        return bulk_move_svc.execute_bulk_move(
            db,
            UUID(job_id),
            stage_id,
            body.min_score,
            body.target_stage_id,
            dry_run=False,
        )
    except bulk_move_svc.NoNextStageError as e:
        raise HTTPException(status_code=422, detail="no_next_stage") from e
    except bulk_move_svc.StageNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e


@router.get(
    "/{job_id}/stages/{stage_id}/bulk-move/preview",
    response_model=BulkMoveResponse,
)
def stage_bulk_move_preview(
    job_id: str,
    stage_id: UUID,
    min_score: int = Query(...),
    target_stage_id: Optional[UUID] = Query(None),
    db: Session = Depends(get_db_session),
    current_user: UserModel = Depends(allow_recruiters),
):
    _get_owned_job(job_id, db, current_user)
    try:
        return bulk_move_svc.execute_bulk_move(
            db,
            UUID(job_id),
            stage_id,
            min_score,
            target_stage_id,
            dry_run=True,
        )
    except bulk_move_svc.NoNextStageError as e:
        raise HTTPException(status_code=422, detail="no_next_stage") from e
    except bulk_move_svc.StageNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
