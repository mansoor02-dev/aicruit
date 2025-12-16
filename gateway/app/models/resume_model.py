import uuid
from ..core.db import Base
from sqlalchemy import Column, String, DateTime, ForeignKey, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship


class ResumeModel(Base):
    __tablename__ = "resumes"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    candidate_id = Column(UUID(as_uuid=True), ForeignKey("candidates.id", ondelete="CASCADE"), nullable=False)
    file_url = Column(String, nullable=False)
    parsed_text = Column(String, nullable=True)
    parsed_skills = Column(String, nullable=True)  # store JSON as text or adjust to JSONB if needed
    created_at = Column(DateTime, default=func.now())

    candidate = relationship("CandidateModel", back_populates="resumes")
    applications = relationship("ApplicationModel", back_populates="resume")
