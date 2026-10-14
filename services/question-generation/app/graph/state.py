from typing import Any, Optional, TypedDict


class QuestionGraphState(TypedDict, total=False):
    resume_json: dict[str, Any]
    previous_qa_list: Optional[list[dict[str, Any]]]
    difficulty: str
    category: Optional[str]
    scenario: str
    evaluation: dict[str, Any]
    flow: dict[str, Any]
    question: str
    metadata: dict[str, Any]
