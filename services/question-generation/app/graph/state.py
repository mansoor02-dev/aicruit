"""Graph state schemas for one question-generation turn.

The compiled graph only accepts request fields (``QuestionGraphInput``) and
only returns the response pair (``QuestionGraphOutput``). Everything else is
internal turn state owned by this invocation; the caller (gateway) owns
durable interview state. No checkpointer or memory is attached.
"""

from __future__ import annotations

from typing import Any, Optional, TypedDict


class QuestionGraphState(TypedDict, total=False):
    """Full turn state (internal channels included)."""

    resume_json: dict[str, Any]
    previous_qa_list: Optional[list[dict[str, Any]]]
    difficulty: str
    category: Optional[str]
    pool: list[dict[str, Any]]
    used_pool_questions: list[str]
    evaluation: dict[str, Any]
    flow: dict[str, Any]
    candidate: str
    attempts: int
    followup_error: bool
    question: str
    metadata: dict[str, Any]


class QuestionGraphInput(TypedDict, total=False):
    """The only keys the compiled graph accepts."""

    resume_json: dict[str, Any]
    previous_qa_list: Optional[list[dict[str, Any]]]
    difficulty: str
    category: Optional[str]
    pool: list[dict[str, Any]]
    used_pool_questions: list[str]


class QuestionGraphOutput(TypedDict, total=False):
    """The only keys the compiled graph returns."""

    question: str
    metadata: dict[str, Any]
