"""Pure text helpers: cleaning, validation and resume snippets."""

from __future__ import annotations

import random
import re
from typing import Any

_FOLLOWUP_ANGLE_MAP = {
    "deep_dive": "implementation_details",
    "same_topic": "elaboration",
}

_FALLBACK_TEMPLATES = [
    "Can you walk me through a specific example from your experience where you applied {topic}?",
    "What trade-offs did you weigh the last time you used {topic} in a real project?",
    "What's the most common mistake you've seen others make with {topic}, and how would you avoid it?",
]

_CONVERSATIONAL_PREFIXES = ["", "I'd like to know: "]

_DIFFICULTY_WORD_LIMIT = {
    "easy": 10,
    "medium": 15,
    "hard": 20,
}

_CONVERSATIONAL_PREFIX = "I'd like to know: "


def followup_angle(decision: str) -> str:
    """Map an evaluation decision to a follow-up angle."""
    return _FOLLOWUP_ANGLE_MAP.get((decision or "").lower(), "elaboration")


def fallback_template_question(topic: str | None, rng: random.Random) -> str:
    """Render a random topic-aware fallback template."""
    template = rng.choice(_FALLBACK_TEMPLATES)
    return template.format(topic=topic or "this area")


def maybe_rephrase(question: str, rng: random.Random) -> str:
    """Add a conversational prefix ~40% of the time."""
    if rng.random() < 0.4:
        prefix = rng.choice(_CONVERSATIONAL_PREFIXES)
        return f"{prefix}{question}" if prefix else question
    return question


def word_limit(difficulty: str) -> int:
    """Max seed-question words per difficulty (easy 10, medium 15, hard 20)."""
    return _DIFFICULTY_WORD_LIMIT.get((difficulty or "medium").lower(), 20)


def clean_question(text: str) -> str:
    """Clean LLM-generated question text.

    Keeps text through the first ``?`` (so ``Node.js`` / ``e.g.`` / ``vs.`` /
    ``C++`` survive); when there is no ``?``, trailing punctuation is
    stripped and ``?`` is appended.
    """
    text = (text or "").strip()
    # Strip common preambles.
    text = re.sub(
        r"^(Question|Follow-up|Q)\s*[:\-]\s*", "", text, flags=re.IGNORECASE
    ).strip()
    # Strip surrounding quotes / backticks.
    text = text.strip("`")
    if (text.startswith('"') and text.endswith('"') and len(text) >= 2) or (
        text.startswith("'") and text.endswith("'") and len(text) >= 2
    ):
        text = text[1:-1].strip()
    # Strip stray leading markdown bullets / numbering.
    text = re.sub(r"^(?:[-*]|\d+[\.)])\s+", "", text).strip()

    cut = text.find("?")
    if cut != -1:
        return text[: cut + 1].strip()
    text = text.rstrip("?.! ").strip()
    return text + "?" if text else ""


def is_valid_followup(question: str, previous_answer: str) -> bool:
    """Local follow-up checks (length, shape and topical overlap)."""
    if not question or len(question) < 10 or not question.endswith("?"):
        return False
    if len(question.split()) > 30:
        return False
    q_words = set(re.findall(r"\b\w{4,}\b", question.lower()))
    a_words = set(re.findall(r"\b\w{4,}\b", previous_answer.lower()))
    common = q_words & a_words
    return 1 <= len(common) <= 10


def strip_conversational_prefix(question: str) -> str:
    """Remove the ``"I'd like to know: "`` prefix for dataset matching."""
    if question.startswith(_CONVERSATIONAL_PREFIX):
        return question[len(_CONVERSATIONAL_PREFIX):]
    return question


def build_resume_snippet(resume_json: dict[str, Any] | None) -> str:
    """Extract skills, projects and experience into a concise prompt string."""
    if not resume_json or not isinstance(resume_json, dict):
        return ""
    parts: list[str] = []

    name = (
        resume_json.get("name")
        or resume_json.get("Name", "")
        or resume_json.get("personal_info", {}).get("name", "")
    )
    if name:
        parts.append(f"Name: {name}")

    skills = resume_json.get("Skills") or resume_json.get("skills") or []
    if skills:
        parts.append(f"Skills: {', '.join(skills)}")

    projects = resume_json.get("projects") or resume_json.get("Projects") or []
    for proj in projects[:3]:
        title = proj.get("title", "")
        desc = proj.get("description", "")
        if isinstance(desc, list):
            desc = "; ".join(desc)
        if title:
            parts.append(f"Project - {title}: {desc[:200]}")

    experience = resume_json.get("experience") or resume_json.get("Experience") or []
    for exp in experience[:3]:
        role = exp.get("role") or exp.get("title", "")
        company = exp.get("company", "")
        desc = exp.get("description", "")
        if isinstance(desc, list):
            desc = "; ".join(desc)
        if role:
            parts.append(f"Experience - {role} at {company}: {desc[:200]}")

    return "\n".join(parts)
