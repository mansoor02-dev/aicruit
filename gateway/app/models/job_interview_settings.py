from pydantic import BaseModel, Field, validator
from typing import List, Optional, Literal
from datetime import datetime
from uuid import UUID


DifficultyLevel = Literal["low", "medium", "high", "very_high", "varying"]


class UploadedQuestion(BaseModel):
    question: str
    topic: Optional[str] = None


class JobInterviewSettingsBase(BaseModel):
    ai_interview_enabled: bool = False
    uploaded_questions: Optional[List[UploadedQuestion]] = None
    topics: List[str] = []
    fixed_question_count: bool = False
    number_of_questions: Optional[int] = None
    max_questions: Optional[int] = None
    difficulty_level: Optional[DifficultyLevel] = None
    interview_stages: int = 1


class JobInterviewSettingsUpdate(JobInterviewSettingsBase):
    pass


class JobInterviewSettingsResponse(JobInterviewSettingsBase):
    id: Optional[UUID] = None
    job_id: UUID
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True
