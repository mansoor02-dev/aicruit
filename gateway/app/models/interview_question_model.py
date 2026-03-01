import uuid
from ..core.db import Base
from sqlalchemy import Column, String, Integer, Text, DateTime, ForeignKey, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship


class InterviewQuestionModel(Base):
    __tablename__ = "interview_questions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # --- Relations ---
    interview_id = Column(UUID(as_uuid=True), ForeignKey("interviews.id", ondelete="CASCADE"), nullable=False)

    # --- Question Details ---
    question_text = Column(Text, nullable=False)
    question_order = Column(Integer)  # Sequence: 1, 2, 3...

    created_at = Column(DateTime, default=func.now())

    # --- Relationships ---
    interview = relationship("InterviewModel", backref="questions")
