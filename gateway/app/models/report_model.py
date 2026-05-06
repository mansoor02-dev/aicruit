import uuid
import datetime
from sqlalchemy import Column, Numeric, Text, DateTime
from sqlalchemy.dialects.postgresql import UUID, JSONB

from ..core.db import Base

class ReportModel(Base):
    __tablename__ = "reports"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    interview_id = Column(UUID(as_uuid=True), nullable=False)
    overall_score = Column(Numeric(5, 2))
    category_scores = Column(JSONB)
    overall_remark = Column(Text)
    strengths = Column(JSONB)
    improvements = Column(JSONB)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
