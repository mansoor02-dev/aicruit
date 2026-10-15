"""Centralised environment-driven configuration.

All ``os.getenv`` access for the service lives in this module. Every other
module receives a :class:`Settings` instance instead of reading the
environment itself.
"""

from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()

DEFAULT_GEMINI_MODEL = "gemini-2.5-flash"
DEFAULT_FALLBACK_MODEL = "meta-llama/llama-3.1-8b-instruct:free"
DEFAULT_EMBEDDING_MODEL = "gemini-embedding-001"
DEFAULT_EMBEDDING_DIMS = 768
DEFAULT_APP_URL = "http://localhost:3000"
DEFAULT_TIMEOUT_SECONDS = 60.0
DEFAULT_MAX_FOLLOWUPS_PER_TOPIC = 2


def _get(name: str, default: str | None = None) -> str | None:
    value = os.getenv(name)
    if value is None or not value.strip():
        return default
    return value.strip()


def _get_int(name: str, default: int) -> int:
    raw = _get(name)
    if raw is None:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def _get_float(name: str, default: float) -> float:
    raw = _get(name)
    if raw is None:
        return default
    try:
        return float(raw)
    except ValueError:
        return default


@dataclass(frozen=True)
class Settings:
    """Immutable service configuration loaded once at startup."""

    gemini_api_key: str | None = None
    openrouter_api_key: str | None = None
    gemini_model: str = DEFAULT_GEMINI_MODEL
    llm_primary_model: str | None = None
    llm_fallback_model: str = DEFAULT_FALLBACK_MODEL
    embedding_model: str = DEFAULT_EMBEDDING_MODEL
    embedding_dims: int = DEFAULT_EMBEDDING_DIMS
    app_url: str = DEFAULT_APP_URL
    llm_timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS
    max_followups_per_topic: int = DEFAULT_MAX_FOLLOWUPS_PER_TOPIC

    @classmethod
    def from_env(cls) -> "Settings":
        """Build settings from the environment, failing fast with no provider."""
        settings = cls(
            gemini_api_key=_get("GEMINI_API_KEY"),
            openrouter_api_key=_get("OPENROUTER_API_KEY"),
            gemini_model=_get("GEMINI_CHAT_MODEL", DEFAULT_GEMINI_MODEL)
            or DEFAULT_GEMINI_MODEL,
            llm_primary_model=_get("LLM_PRIMARY_MODEL"),
            llm_fallback_model=_get("LLM_FALLBACK_MODEL", DEFAULT_FALLBACK_MODEL)
            or DEFAULT_FALLBACK_MODEL,
            embedding_model=_get("EMBEDDING_MODEL", DEFAULT_EMBEDDING_MODEL)
            or DEFAULT_EMBEDDING_MODEL,
            embedding_dims=_get_int("EMBEDDING_DIMS", DEFAULT_EMBEDDING_DIMS),
            app_url=_get("APP_URL", DEFAULT_APP_URL) or DEFAULT_APP_URL,
            llm_timeout_seconds=_get_float(
                "LLM_TIMEOUT_SECONDS", DEFAULT_TIMEOUT_SECONDS
            ),
            max_followups_per_topic=_get_int(
                "MAX_FOLLOWUPS_PER_TOPIC", DEFAULT_MAX_FOLLOWUPS_PER_TOPIC
            ),
        )
        if not settings.gemini_api_key and not settings.openrouter_api_key:
            raise ValueError(
                "Neither GEMINI_API_KEY nor OPENROUTER_API_KEY is configured"
            )
        return settings
