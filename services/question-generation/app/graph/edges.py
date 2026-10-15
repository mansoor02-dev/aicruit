"""Graph routers (pure functions of turn state).

Also home to the pure recruiter-pool selector shared by the routers and the
pool node, so the preferred/unused[0] rule lives in exactly one place.
"""

from __future__ import annotations

from typing import Any, Optional

from app.services.text import is_valid_followup

from .state import QuestionGraphState


def select_pool_question(
    pool: list[dict[str, Any]] | None,
    used_pool_questions: list[str] | None,
    category: Optional[str],
) -> dict[str, Any] | None:
    """Pick the recruiter-pool question for this turn (no LLM).

    Prefers the first unused question whose topic matches the requested
    category (case-insensitive); with no category every unused question is
    eligible. Falls back to the first unused question when nothing matches
    the topic (topic mismatch is accepted on purpose). Returns ``None`` when
    the pool is exhausted so the caller falls through to the normal graph.
    """
    if not pool:
        return None
    used = set(used_pool_questions or [])
    target_topic = (category or "").strip().lower()

    def _topic_match(item: dict[str, Any]) -> bool:
        if not target_topic:
            return True
        topic = (item.get("topic") or "").strip().lower()
        return topic == target_topic

    unused = [item for item in pool if item.get("question") not in used]
    preferred = [item for item in unused if _topic_match(item)]
    if preferred:
        return preferred[0]
    if unused:
        return unused[0]
    return None


def has_unused_pool_question(state: QuestionGraphState) -> bool:
    """Whether the recruiter pool still has a question for this turn."""
    return (
        select_pool_question(
            state.get("pool"),
            state.get("used_pool_questions"),
            state.get("category"),
        )
        is not None
    )


def route_entry(state: QuestionGraphState) -> str:
    """Initial routing: history -> evaluate; pool -> pool; else intro/opener."""
    if state.get("previous_qa_list"):
        return "evaluate"
    if has_unused_pool_question(state):
        return "pool"
    if not state.get("category"):
        return "introduction"
    return "opener"


def trailing_followup_count(
    previous_qa_list: list[dict[str, Any]] | None,
) -> int:
    """Consecutive trailing history items flagged as follow-ups."""
    count = 0
    for qa in reversed(previous_qa_list or []):
        if qa.get("is_followup"):
            count += 1
        else:
            break
    return count


def route_after_eval(
    state: QuestionGraphState, max_followups_per_topic: int = 2
) -> str:
    """Post-evaluation routing: pool -> pool; deep/same -> follow-up.

    When history items carry ``is_followup`` flags, more than
    ``max_followups_per_topic`` consecutive follow-ups force a new topic.
    Without those flags the count is 0 and behaviour is unchanged.
    """
    if has_unused_pool_question(state):
        return "pool"
    decision = state.get("flow", {}).get("decision", "new_topic")
    if decision in ("deep_dive", "same_topic"):
        if (
            trailing_followup_count(state.get("previous_qa_list"))
            >= max_followups_per_topic
        ):
            return "new_topic"
        return "followup"
    return "new_topic"


def rejection_reason(candidate: str, previous_answer: str) -> str:
    """Human-readable reason a follow-up candidate was rejected."""
    if not candidate or len(candidate) < 10 or not candidate.endswith("?"):
        return "it is not a well-formed question ending with '?'"
    if len(candidate.split()) > 30:
        return "it is too long (over 30 words)"
    return "it does not engage with the candidate's last answer"


def route_after_validation(state: QuestionGraphState) -> str:
    """Follow-up validation: valid -> done; retry once; else template."""
    history = state.get("previous_qa_list") or []
    previous_answer = history[-1].get("A", "") if history else ""
    if is_valid_followup(state.get("candidate", ""), previous_answer):
        return "done"
    if state.get("followup_error"):
        return "template"
    if state.get("attempts", 0) < 2:
        return "retry"
    return "template"
