import uuid
from ..core.db import Base
from sqlalchemy import Column, String, Integer, Boolean, DateTime, ForeignKey, func, CheckConstraint
from sqlalchemy.dialects.postgresql import UUID, JSONB


class JobInterviewSettingsModel(Base):
    __tablename__ = "job_interview_settings"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    job_id = Column(UUID(as_uuid=True), ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False, unique=True)

    ai_interview_enabled = Column(Boolean, nullable=False, default=False)
    uploaded_questions = Column(JSONB, nullable=True)
    topics = Column(JSONB, nullable=False, default=list)
    fixed_question_count = Column(Boolean, nullable=False, default=False)
    number_of_questions = Column(Integer, nullable=True)
    max_questions = Column(Integer, nullable=True)
    difficulty_level = Column(String, nullable=True)
    interview_stages = Column(Integer, nullable=False, default=1)

    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())

    __table_args__ = (
        CheckConstraint(
            "difficulty_level IS NULL OR difficulty_level IN ('low','medium','high','very_high','varying')",
            name="job_interview_settings_difficulty_chk",
        ),
    )
