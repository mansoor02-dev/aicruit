from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File
from sqlalchemy.orm import Session
from typing import List, Union
import httpx
from uuid import UUID
import os
import json

from ..core.db import get_db_session
from ..models.job_model import JobModel
from ..models.application_model import ApplicationModel
from ..models.resume_model import ResumeModel
from ..models.user import UserModel
from ..models.job import JobCreate, JobResponse, JobUpdate, JobWithApplicantsResponse, JobForCandidateResponse, ApplicantInfo
from ..models.application import ApplicationCreate, ApplicationResponse
from ..core.security import get_current_user, RoleChecker

router = APIRouter()

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
@router.post("/upload-resume", status_code=status.HTTP_200_OK)
async def upload_and_parse_resume(
    file: UploadFile = File(...),
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
            status="APPLIED"
        )
        
        db.add(new_application)
        db.commit()
        db.refresh(new_application)
        
        return new_application
    except HTTPException as he:
        raise he
    except Exception as e:
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