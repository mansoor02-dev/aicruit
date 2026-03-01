import uuid
from ..core.db import Base
from sqlalchemy import Column, String, Integer, Text, DateTime, ForeignKey, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship


class InterviewResponseModel(Base):
    __tablename__ = "interview_responses"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # --- Relations ---
    interview_id = Column(UUID(as_uuid=True), ForeignKey("interviews.id", ondelete="CASCADE"), nullable=False)
    question_id = Column(UUID(as_uuid=True), ForeignKey("interview_questions.id", ondelete="CASCADE"), nullable=False)

    # --- Response Data ---
    video_url = Column(Text, nullable=True)
    audio_url = Column(Text, nullable=True)
    transcript = Column(Text, nullable=True)

    # --- AI Grading ---
    ai_score = Column(Integer, nullable=True)
    confidence_score = Column(Integer, nullable=True)
    communication_score = Column(Integer, nullable=True)
    sentiment = Column(String(20), nullable=True)

    created_at = Column(DateTime, default=func.now())

    # --- Relationships ---
    interview = relationship("InterviewModel", backref="responses")
    question = relationship("InterviewQuestionModel", backref="responses")
