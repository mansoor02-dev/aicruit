"""Structured response models shared by question-generation LLM calls."""

from typing import Literal

from pydantic import BaseModel, Field


class GeneratedQuestion(BaseModel):
    question: str = Field(min_length=1)


class AnswerEvaluation(BaseModel):
    score: float = Field(default=0.5, ge=0.0, le=1.0)
    confidence: float = Field(default=0.6, ge=0.0, le=1.0)
    feedback: str = ""
    decision: Literal["new_topic", "same_topic", "deep_dive"] = "new_topic"
    remarks: str = ""
    score_reason: str = ""


class DraftEmail(BaseModel):
    subject: str = Field(min_length=1)
    body: str = Field(min_length=1)
