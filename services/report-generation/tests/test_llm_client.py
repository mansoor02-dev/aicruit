import asyncio

import httpx
import pytest

from app.llm.client import LLMClient, LLMProviderError
from app.prompts.report_prompts import SCORE_PROMPT
from app.schemas.reports import ScoreResult


def _make_gemini_only_client():
    client = LLMClient(max_retries=0)
    client._gemini_client = object()
    client._openrouter_key = None
    return client


def test_malformed_provider_output_is_rejected(monkeypatch):
    client = _make_gemini_only_client()

    async def malformed(*_args, **_kwargs):
        return "not JSON"

    monkeypatch.setattr(client, "_complete_gemini", malformed)

    with pytest.raises(LLMProviderError, match="valid output"):
        asyncio.run(
            client.complete_structured(
                SCORE_PROMPT,
                ScoreResult,
                {
                    "question": "Question?",
                    "answer": "Answer.",
                    "existing_score": "none",
                    "existing_remark": "none",
                },
                max_tokens=100,
            )
        )


def test_transient_timeout_retries_with_a_bound(monkeypatch):
    client = _make_gemini_only_client()
    client.max_retries = 1
    calls = 0

    async def flaky(*_args, **_kwargs):
        nonlocal calls
        calls += 1
        if calls == 1:
            raise httpx.ReadTimeout("temporary timeout")
        return '{"score": 4, "remark": "Clear answer."}'

    monkeypatch.setattr(client, "_complete_gemini", flaky)

    result = asyncio.run(
        client.complete_structured(
            SCORE_PROMPT,
            ScoreResult,
            {
                "question": "Question?",
                "answer": "Answer.",
                "existing_score": "none",
                "existing_remark": "none",
            },
            max_tokens=100,
        )
    )

    assert result.score == 4
    assert calls == 2


def test_request_timeout_is_retried_only_within_the_configured_bound(monkeypatch):
    client = LLMClient(timeout_seconds=0.001, max_retries=1)
    client._gemini_client = object()
    calls = 0

    async def slow(*_args, **_kwargs):
        nonlocal calls
        calls += 1
        await asyncio.sleep(0.02)
        return '{"score": 4, "remark": "Clear answer."}'

    monkeypatch.setattr(client, "_complete_gemini", slow)

    with pytest.raises(LLMProviderError, match="valid output"):
        asyncio.run(
            client.complete_structured(
                SCORE_PROMPT,
                ScoreResult,
                {
                    "question": "Question?",
                    "answer": "Answer.",
                    "existing_score": "none",
                    "existing_remark": "none",
                },
                max_tokens=100,
            )
        )

    assert calls == 2


def test_openrouter_is_used_after_gemini_provider_failure(monkeypatch):
    client = _make_gemini_only_client()
    client._openrouter_key = "test-key"
    client._openrouter_model = "test-model"
    calls = []

    async def failing_gemini(*_args, **_kwargs):
        calls.append("gemini")
        raise RuntimeError("provider unavailable")

    async def successful_openrouter(*_args, **_kwargs):
        calls.append("openrouter")
        return '{"score": 5, "remark": "Excellent answer."}'

    monkeypatch.setattr(client, "_complete_gemini", failing_gemini)
    monkeypatch.setattr(client, "_complete_openrouter", successful_openrouter)

    result = asyncio.run(
        client.complete_structured(
            SCORE_PROMPT,
            ScoreResult,
            {
                "question": "Question?",
                "answer": "Answer.",
                "existing_score": "none",
                "existing_remark": "none",
            },
            max_tokens=100,
        )
    )

    assert result.score == 5
    assert calls == ["gemini", "openrouter"]


def test_existing_model_environment_variables_are_preserved(monkeypatch):
    monkeypatch.setenv("LLM_PRIMARY_MODEL", "gemini-test-model")
    monkeypatch.setenv("LLM_FALLBACK_MODEL", "openrouter/test-model")
    monkeypatch.delenv("GEMINI_CHAT_MODEL", raising=False)
    client = LLMClient()

    assert client._gemini_model == "gemini-test-model"
    assert client._openrouter_model == "openrouter/test-model"


def test_no_configured_provider_raises_clear_error(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    client = LLMClient(max_retries=0)

    with pytest.raises(LLMProviderError, match="No LLM provider"):
        asyncio.run(
            client.complete_structured(
                SCORE_PROMPT,
                ScoreResult,
                {
                    "question": "Question?",
                    "answer": "Answer.",
                    "existing_score": "none",
                    "existing_remark": "none",
                },
                max_tokens=100,
            )
        )
