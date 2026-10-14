"""HTTP request models for the Question Generation API."""

from typing import Any

from pydantic import BaseModel, Field


class QA(BaseModel):
    Q: str
    A: str


class PoolQuestion(BaseModel):
    question: str
    topic: str | None = None


class QuestionRequest(BaseModel):
    resume_json: dict[str | None, Any] | None = None
    previous_qa: list[QA] = Field(default_factory=list)
    difficulty: str = "medium"
    category: str | None = None
    question_pool: list[PoolQuestion] | None = None
    used_pool_questions: list[str] | None = None


class CategoryScore(BaseModel):
    category: str
    score: float


class DraftEmailRequest(BaseModel):
    scenario: str
    candidate_name: str
    job_title: str
    company_name: str | None = None
    scheduled_at: str | None = None
    stage_name: str | None = None
    category_scores: list[CategoryScore] | None = None
    overall_score: float | None = None
    custom_instructions: str | None = None
