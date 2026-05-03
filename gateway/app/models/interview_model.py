import uuid
from ..core.db import Base
from sqlalchemy import Column, String, Integer, DateTime, ForeignKey, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship


class InterviewModel(Base):
    __tablename__ = "interviews"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # --- Relations ---
    application_id = Column(UUID(as_uuid=True), ForeignKey("applications.id", ondelete="CASCADE"), nullable=False)

    # --- Interview Details ---
    scheduled_at = Column(DateTime, nullable=False)
    status = Column(String(20), default="scheduled")  # scheduled, in_progress, completed, cancelled, expired
    cheating_risk_score = Column(Integer, default=0)
    next_snapshot_at = Column(DateTime, nullable=True)
    expires_at = Column(DateTime(timezone=True), nullable=True)

    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())

    # --- Relationships ---
    application = relationship("ApplicationModel", backref="interviews")
