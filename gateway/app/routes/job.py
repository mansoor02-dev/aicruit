from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List

from ..core.db import get_db_session
from ..models.job_model import JobModel
from ..models.application_model import ApplicationModel
from ..models.user import UserModel
from ..models.job import JobCreate, JobResponse, JobUpdate
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
# 2. LIST JOBS (Smart View)
# =========================================================
@router.get("/", response_model=List[JobResponse])
def get_jobs(
    db: Session = Depends(get_db_session),
    current_user: UserModel = Depends(allow_anyone) # <--- Any logged in user
):
    if current_user.role == "RECRUITER":
        # VIEW A: Recruiter sees THEIR Company's jobs (Open & Closed)
        if not current_user.recruiter:
             return []
        
        jobs = db.query(JobModel).filter(
            JobModel.company_id == current_user.recruiter.company_id
        ).all()
        
    else:
        # VIEW B: Candidates see ALL Companies' jobs (Only Open)
        jobs = db.query(JobModel).filter(
            JobModel.status == 'OPEN'
        ).all()

    return jobs

# =========================================================
# 3. GET JOB DETAILS
# =========================================================
@router.get("/{job_id}", response_model=JobResponse)
def get_job_detail(
    job_id: str,
    db: Session = Depends(get_db_session),
    current_user: UserModel = Depends(allow_anyone)
):
    job = db.query(JobModel).filter(JobModel.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
        
    return job

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
def apply_to_job(
    application_data: ApplicationCreate,
    db: Session = Depends(get_db_session),
    current_user: UserModel = Depends(allow_candidates)
):
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
    
    # Create application
    new_application = ApplicationModel(
        job_id=application_data.job_id,
        candidate_id=current_user.candidate.id,
        resume_url=application_data.resume_url,
        status="APPLIED"
    )
    
    db.add(new_application)
    db.commit()
    db.refresh(new_application)
    
    return new_application