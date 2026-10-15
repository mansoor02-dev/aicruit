"""Chat model wiring: Gemini primary, OpenRouter fallback.

Provider policy (unchanged from the hand-rolled client):
- Gemini is primary when ``GEMINI_API_KEY`` is set. Each model is built with
  ``max_retries=0`` so exactly one attempt is made per provider call, with a
  60 s timeout (no hidden retries).
- OpenRouter (via its OpenAI-compatible endpoint) is the fallback. It uses
  ``LLM_FALLBACK_MODEL`` when Gemini is configured, or
  ``LLM_PRIMARY_MODEL or LLM_FALLBACK_MODEL`` when OpenRouter is the only
  provider.
- If neither key exists, startup fails fast with ``ValueError``.

Separate model instances are built per generation profile (question,
evaluation, email) because temperature / max-token overrides differ and
``.bind()`` semantics vary per parameter.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_openai import ChatOpenAI

from app.config import Settings

logger = logging.getLogger(__name__)

OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"

# Per-call generation settings (kept identical to the previous client).
QUESTION_MAX_TOKENS = 150
QUESTION_TEMPERATURE = 0.4
EVALUATION_MAX_TOKENS = 200
EVALUATION_TEMPERATURE = 0.1
EMAIL_MAX_TOKENS = 900
EMAIL_TEMPERATURE = 0.4
GEMINI_TOP_P = 0.95


class LLMProviderError(RuntimeError):
    """Raised when every configured LLM provider fails."""


@dataclass(frozen=True)
class ProfileModels:
    """Primary / fallback chat models for one generation profile."""

    primary: BaseChatModel | None
    fallback: BaseChatModel | None


@dataclass(frozen=True)
class ChatModels:
    """All chat models for the service, grouped by generation profile."""

    question: ProfileModels
    evaluation: ProfileModels
    email: ProfileModels
    has_gemini: bool
    has_openrouter: bool


def resolve_openrouter_model(settings: Settings) -> str:
    """Apply the OpenRouter model-name rule.

    With Gemini configured, OpenRouter is purely a fallback and uses
    ``LLM_FALLBACK_MODEL``. In an OpenRouter-only deployment the model comes
    from ``LLM_PRIMARY_MODEL`` with ``LLM_FALLBACK_MODEL`` as the default.
    """
    if settings.gemini_api_key:
        return settings.llm_fallback_model
    return settings.llm_primary_model or settings.llm_fallback_model


def _thinking_budget(model_name: str) -> int | None:
    """Cap thinking tokens for Gemini 2.5 models.

    Uncapped thinking can consume the small ``max_output_tokens`` budgets
    used for questions (150) and return an empty question. ``0`` disables
    thinking on 2.5 Flash; other 2.5 models require a minimum budget, so they
    are capped at 128 instead.
    """
    if "2.5" not in model_name:
        return None
    if "flash" in model_name.lower():
        return 0
    return 128


def make_gemini_model(
    settings: Settings, *, max_tokens: int, temperature: float
) -> ChatGoogleGenerativeAI:
    """Build one Gemini chat model with a single-attempt policy."""
    kwargs: dict = {
        "model": settings.gemini_model,
        "google_api_key": settings.gemini_api_key,
        "temperature": temperature,
        "max_output_tokens": max_tokens,
        "top_p": GEMINI_TOP_P,
        "timeout": settings.llm_timeout_seconds,
        "max_retries": 0,
    }
    budget = _thinking_budget(settings.gemini_model)
    if budget is not None:
        kwargs["thinking_budget"] = budget
    return ChatGoogleGenerativeAI(**kwargs)


def make_openrouter_model(
    settings: Settings,
    *,
    model_name: str,
    max_tokens: int,
    temperature: float,
) -> ChatOpenAI:
    """Build one OpenRouter chat model (OpenAI-compatible endpoint)."""
    return ChatOpenAI(
        model_name=model_name,
        openai_api_base=OPENROUTER_BASE_URL,
        openai_api_key=settings.openrouter_api_key,
        temperature=temperature,
        max_tokens=max_tokens,
        request_timeout=settings.llm_timeout_seconds,
        max_retries=0,
        default_headers={"HTTP-Referer": settings.app_url},
    )


def make_chat_models(settings: Settings) -> ChatModels:
    """Build every chat model for the service from ``settings``."""
    if not settings.gemini_api_key and not settings.openrouter_api_key:
        raise ValueError(
            "Neither GEMINI_API_KEY nor OPENROUTER_API_KEY is configured"
        )

    profiles = (
        ("question", QUESTION_MAX_TOKENS, QUESTION_TEMPERATURE),
        ("evaluation", EVALUATION_MAX_TOKENS, EVALUATION_TEMPERATURE),
        ("email", EMAIL_MAX_TOKENS, EMAIL_TEMPERATURE),
    )
    built: dict[str, ProfileModels] = {}
    openrouter_model = (
        resolve_openrouter_model(settings) if settings.openrouter_api_key else None
    )
    for name, max_tokens, temperature in profiles:
        primary: BaseChatModel | None = None
        fallback: BaseChatModel | None = None
        if settings.gemini_api_key:
            primary = make_gemini_model(
                settings, max_tokens=max_tokens, temperature=temperature
            )
            if openrouter_model:
                fallback = make_openrouter_model(
                    settings,
                    model_name=openrouter_model,
                    max_tokens=max_tokens,
                    temperature=temperature,
                )
        elif openrouter_model:
            # OpenRouter-only deployment: the "primary" slot holds OpenRouter.
            primary = make_openrouter_model(
                settings,
                model_name=openrouter_model,
                max_tokens=max_tokens,
                temperature=temperature,
            )
        built[name] = ProfileModels(primary=primary, fallback=fallback)

    models = ChatModels(
        question=built["question"],
        evaluation=built["evaluation"],
        email=built["email"],
        has_gemini=bool(settings.gemini_api_key),
        has_openrouter=bool(settings.openrouter_api_key),
    )
    logger.info(
        "Chat models ready (gemini=%s, openrouter=%s, gemini_model=%s, "
        "openrouter_model=%s)",
        models.has_gemini,
        models.has_openrouter,
        settings.gemini_model,
        openrouter_model,
    )
    return models
