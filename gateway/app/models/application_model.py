import uuid
from ..core.db import Base
from sqlalchemy import Column, String, Integer, DateTime, ForeignKey, func, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship


class ApplicationModel(Base):
    __tablename__ = "applications"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    # --- Relations ---
    job_id = Column(UUID(as_uuid=True), ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False)
    candidate_id = Column(UUID(as_uuid=True), ForeignKey("candidates.id", ondelete="CASCADE"), nullable=False)
    resume_id = Column(UUID(as_uuid=True), ForeignKey("resumes.id"), nullable=True)
    
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
