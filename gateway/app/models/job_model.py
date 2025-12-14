import uuid
from ..core.db import Base
from sqlalchemy import Column, String, Integer, Text, DateTime, ForeignKey, func
from sqlalchemy.dialects.postgresql import UUID, JSONB # <--- Important for skills list
from sqlalchemy.orm import relationship


class JobModel(Base):
    __tablename__ = "jobs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    # --- Relations ---
    # Link to the Company (SaaS Parent)
    company_id = Column(UUID(as_uuid=True), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False)
    # Link to the specific Recruiter who posted it
    recruiter_id = Column(UUID(as_uuid=True), ForeignKey("recruiters.id", ondelete="SET NULL"), nullable=True)

    # --- Job Details ---
    title = Column(String(200), nullable=False)
    description = Column(Text, nullable=False)
    location = Column(String(100), nullable=True) # e.g. "Remote", "Islamabad"
    type = Column(String(50), nullable=True)      # e.g. "Full Time", "Contract"
    
    # --- AI Data (Crucial for Matching) ---
    # JSONB allows efficient querying of arrays in Postgres
    required_skills = Column(JSONB, default=list) # Stores ["Python", "FastAPI"]
    experience_level = Column(String(50), nullable=True) # e.g. "Senior", "Junior"

    # --- Metadata ---
    salary_min = Column(Integer, nullable=True)
    salary_max = Column(Integer, nullable=True)
    status = Column(String(20), default="OPEN")   # OPEN, CLOSED
    
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())

    # --- Relationships ---
    # We use string names "CompanyModel" to avoid circular import errors
    company = relationship("CompanyModel", back_populates="jobs")
    recruiter = relationship("RecruiterModel", back_populates="jobs")
    
    # Future proofing: You will add this later for candidates
    # applications = relationship("ApplicationModel", back_populates="job")