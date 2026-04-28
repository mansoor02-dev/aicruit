import uuid
from ..core.db import Base
from sqlalchemy import Column, String, Integer, Text, DateTime, ForeignKey, func, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship


class ApplicationModel(Base):
    __tablename__ = "applications"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    # --- Relations ---
    job_id = Column(UUID(as_uuid=True), ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False)
    candidate_id = Column(UUID(as_uuid=True), ForeignKey("candidates.id", ondelete="CASCADE"), nullable=False)
    resume_id = Column(UUID(as_uuid=True), ForeignKey("resumes.id"), nullable=True)
    
    # --- Candidate-submitted form data ---
    applicant_name = Column(String(255), nullable=True)
    applicant_email = Column(String(255), nullable=True)
    applicant_phone = Column(String(100), nullable=True)
    applicant_location = Column(String(255), nullable=True)
    summary = Column(Text, nullable=True)
    skills = Column(JSONB, default=list)
    education = Column(JSONB, default=list)
    experience = Column(JSONB, default=list)
    projects = Column(JSONB, default=list)
    
    # --- Answers to recruiter-defined application questions ---
    # JSONB array: [{ question_id, label, type, value }, ...]
    question_responses = Column(JSONB, default=list)
    
    # --- Application Details ---
    status = Column(String(50), default="APPLIED")  # APPLIED, SCREENING, INTERVIEW_SCHEDULED, INTERVIEW_COMPLETED, OFFERED, REJECTED
    ai_match_score = Column(Integer, default=0)
    
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())

    # --- Relationships ---
    job = relationship("JobModel", back_populates="applications")
    candidate = relationship("CandidateModel", back_populates="applications")
    resume = relationship("ResumeModel", back_populates="applications")
    
    # Ensure candidate can apply to same job only once
    __table_args__ = (
        UniqueConstraint('job_id', 'candidate_id', name='unique_job_candidate_application'),
    )
