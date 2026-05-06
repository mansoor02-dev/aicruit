import uuid
from ..core.db import Base
from sqlalchemy import Column, String, Integer, DateTime, ForeignKey, func, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship


class JobStageModel(Base):
    __tablename__ = "job_stages"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # --- Relations ---
    job_id = Column(UUID(as_uuid=True), ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False)

    # --- Stage Details ---
    position = Column(Integer, nullable=False)  # 0-based; unique per job_id
    name = Column(String(100), nullable=False)

    created_at = Column(DateTime(timezone=True), default=func.now())
    updated_at = Column(DateTime(timezone=True), default=func.now(), onupdate=func.now())

    # --- Relationships ---
    job = relationship("JobModel", back_populates="stages")
    applications = relationship("ApplicationModel", back_populates="stage")

    __table_args__ = (
        UniqueConstraint('job_id', 'position', name='unique_job_stage_position'),
    )
