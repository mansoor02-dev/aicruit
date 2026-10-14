import asyncio
from unittest.mock import AsyncMock

import pytest
from pydantic import ValidationError

import app.services.llm_client as llm_client_module
from app.schemas.llm import GeneratedQuestion
from app.services.llm_client import LLMClient, LLMProviderError


def _client(monkeypatch, timeout=1.0):
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-openrouter-key")
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    client = LLMClient(timeout_seconds=timeout)
    client._gemini_client = object()
    return client


def test_complete_json_returns_validated_output(monkeypatch):
    client = _client(monkeypatch)
    client._gemini_complete = AsyncMock(
        return_value='{"question": "How do you invalidate a cache?"}'
    )
    client._openrouter_complete = AsyncMock()

    result = asyncio.run(
        client.complete_json("Prompt", GeneratedQuestion, system="Interviewer")
    )

    assert result == GeneratedQuestion(
        question="How do you invalidate a cache?"
    )
    client._gemini_complete.assert_awaited_once()
    client._openrouter_complete.assert_not_awaited()


def test_complete_json_rejects_invalid_provider_output(monkeypatch):
    client = _client(monkeypatch)
    client._gemini_complete = AsyncMock(return_value='{"answer": "not a question"}')
    client._openrouter_complete = AsyncMock()

    with pytest.raises(ValidationError):
        asyncio.run(
            client.complete_json("Prompt", GeneratedQuestion, system="Interviewer")
        )

    client._openrouter_complete.assert_not_awaited()


def test_gemini_timeout_falls_back_to_openrouter(monkeypatch):
    client = _client(monkeypatch, timeout=0.01)

    async def slow_gemini(*_args):
        await asyncio.sleep(1)

    client._gemini_complete = AsyncMock(side_effect=slow_gemini)
    client._openrouter_complete = AsyncMock(
        return_value='{"question": "How do you invalidate a cache?"}'
    )

    result = asyncio.run(
        client.complete_json("Prompt", GeneratedQuestion, system="Interviewer")
    )

    assert result.question == "How do you invalidate a cache?"
    client._gemini_complete.assert_awaited_once()
    client._openrouter_complete.assert_awaited_once()


def test_provider_failures_raise_after_one_attempt_each(monkeypatch):
    client = _client(monkeypatch)
    client._gemini_complete = AsyncMock(side_effect=RuntimeError("Gemini unavailable"))
    client._openrouter_complete = AsyncMock(
        side_effect=RuntimeError("OpenRouter unavailable")
    )

    with pytest.raises(LLMProviderError, match="All configured LLM providers failed"):
        asyncio.run(client.complete("Prompt"))

    client._gemini_complete.assert_awaited_once()
    client._openrouter_complete.assert_awaited_once()


def test_openrouter_only_uses_configured_primary_model(monkeypatch):
    client = _client(monkeypatch)
    client._gemini_client = None
    monkeypatch.setattr(
        llm_client_module, "OPENROUTER_PRIMARY_MODEL", "openai/example-model"
    )
    client._openrouter_complete = AsyncMock(return_value='{"question": "Q?"}')

    asyncio.run(client.complete("Prompt"))

    assert client._openrouter_complete.await_args.args[3] == "openai/example-model"
