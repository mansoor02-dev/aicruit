from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
import httpx

from ..core.db import get_db_session
from ..models.job_model import JobModel
from ..models.application_model import ApplicationModel
from ..models.resume_model import ResumeModel
from ..models.user import UserModel
from ..models.job import JobCreate, JobResponse, JobUpdate, JobWithApplicantsResponse, JobForCandidateResponse, ApplicantInfo
from ..models.application import ApplicationCreate, ApplicationResponse
from ..core.security import get_current_user, RoleChecker

router = APIRouter()

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

    # SaaS Logic: Link to the Recruiter's Company automatically
    new_job = JobModel(
        **job_data.dict(),
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
                        candidate_name=user.full_name,
                        candidate_email=user.email,
                        candidate_phone=candidate.phone,
                        candidate_linkedin=candidate.linkedin_url if hasattr(candidate, 'linkedin_url') else None,
                        resume_id=resume.id if resume else None,
                        resume_url=resume.file_url if resume else "",
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
    for field, value in update_data.items():
        setattr(job, field, value)
    
    db.commit()
    db.refresh(job)
    
    return job

# =========================================================
# 5. APPLY TO JOB (Candidates Only)
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
        
        # Create resume record first
        new_resume = ResumeModel(
            candidate_id=current_user.candidate.id,
            file_url=application_data.resume_url,
        )
        db.add(new_resume)
        db.flush()  # get resume id

        # Create application referencing resume
        new_application = ApplicationModel(
            job_id=application_data.job_id,
            candidate_id=current_user.candidate.id,
            resume_id=new_resume.id,
            status="APPLIED"
        )
        
        db.add(new_application)
        db.commit()
        db.refresh(new_application)
        
        # Call parse-resume microservice to parse and extract skills
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    "http://localhost:8006/parse-resume",
                    json={"resume_id": str(new_resume.id)},
                    timeout=30.0
                )
                if response.status_code == 200:
                    print(f"✅ Resume {new_resume.id} parsed successfully")
                else:
                    print(f"⚠️ Resume parsing service returned status {response.status_code}")
        except Exception as service_error:
            print(f"⚠️ Failed to call parse-resume service: {service_error}")
            # Continue even if service call fails - application is already created
        
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
            )
        )
    
    return result


# =========================================================
# 3. GET JOB DETAILS (Role-Based Response)
# =========================================================
@router.get("/{job_id}", response_model=List)
def get_job_detail(
    job_id: str,
    db: Session = Depends(get_db_session),
    current_user: UserModel = Depends(allow_anyone)
):
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
                    candidate_name=user.full_name,
                    candidate_email=user.email,
                    candidate_phone=candidate.phone,
                    candidate_linkedin=candidate.linkedin_url if hasattr(candidate, 'linkedin_url') else None,
                    resume_id=resume.id if resume else None,
                    resume_url=resume.file_url if resume else "",
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
        )