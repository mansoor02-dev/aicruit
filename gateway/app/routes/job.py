from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List

from ..core.db import get_db_session
from ..models.job_model import JobModel
from ..models.user import UserModel
from ..models.job import JobCreate, JobResponse
from ..core.security import get_current_user, RoleChecker

router = APIRouter()

# Define Role Guards
allow_recruiters = RoleChecker(["RECRUITER", "ADMIN"])
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