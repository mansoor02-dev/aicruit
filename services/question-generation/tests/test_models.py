"""Provider selection matrix for ``app.llm.models`` (no network calls)."""

import pytest

import app.llm.models as models_module
from app.config import Settings
from app.llm.models import make_chat_models, resolve_openrouter_model


class FakeChatModel:
    def __init__(self, **kwargs):
        self.kwargs = kwargs


def _settings(**overrides):
    base = {
        "gemini_api_key": "test-gemini-key",
        "openrouter_api_key": "test-openrouter-key",
        "gemini_model": "gemini-2.5-flash",
        "llm_primary_model": "openai/gpt-oss-120b:free",
        "llm_fallback_model": "meta-llama/llama-3.1-8b-instruct:free",
    }
    base.update(overrides)
    return Settings(**base)


@pytest.fixture
def fake_models(monkeypatch):
    gemini_seen: list[dict] = []
    openrouter_seen: list[dict] = []

    def fake_gemini(**kwargs):
        gemini_seen.append(kwargs)
        return FakeChatModel(**kwargs)

    def fake_openrouter(**kwargs):
        openrouter_seen.append(kwargs)
        return FakeChatModel(**kwargs)

    monkeypatch.setattr(models_module, "ChatGoogleGenerativeAI", fake_gemini)
    monkeypatch.setattr(models_module, "ChatOpenAI", fake_openrouter)
    return gemini_seen, openrouter_seen


def test_both_providers_gemini_primary_openrouter_fallback(fake_models):
    gemini_seen, openrouter_seen = fake_models

    models = make_chat_models(_settings())

    assert models.has_gemini is True
    assert models.has_openrouter is True
    for profile in (models.question, models.evaluation, models.email):
        assert isinstance(profile.primary, FakeChatModel)
        assert isinstance(profile.fallback, FakeChatModel)
    # Fallback uses LLM_FALLBACK_MODEL when Gemini is configured.
    assert resolve_openrouter_model(_settings()) == (
        "meta-llama/llama-3.1-8b-instruct:free"
    )
    assert all(
        kwargs["model_name"] == "meta-llama/llama-3.1-8b-instruct:free"
        for kwargs in openrouter_seen
    )
    assert len(gemini_seen) == 3
    assert len(openrouter_seen) == 3


def test_per_profile_generation_settings(fake_models):
    gemini_seen, _ = fake_models
    make_chat_models(_settings())

    by_tokens = {
        (kwargs["max_output_tokens"], kwargs["temperature"])
        for kwargs in gemini_seen
    }
    assert by_tokens == {(150, 0.4), (200, 0.1), (900, 0.4)}


def test_gemini_single_attempt_policy(fake_models):
    gemini_seen, _ = fake_models
    make_chat_models(_settings())

    for kwargs in gemini_seen:
        assert kwargs["max_retries"] == 0
        assert kwargs["timeout"] == 60.0
        assert kwargs["top_p"] == 0.95
        assert kwargs["thinking_budget"] == 0  # gemini-2.5-flash disables thinking


def test_thinking_budget_skipped_for_non_25_models(fake_models):
    gemini_seen, _ = fake_models
    make_chat_models(_settings(gemini_model="gemini-2.0-flash"))

    assert all("thinking_budget" not in kwargs for kwargs in gemini_seen)


def test_openrouter_single_attempt_policy(fake_models):
    _, openrouter_seen = fake_models
    make_chat_models(_settings())

    for kwargs in openrouter_seen:
        assert kwargs["max_retries"] == 0
        assert kwargs["request_timeout"] == 60.0
        assert kwargs["openai_api_base"] == "https://openrouter.ai/api/v1"
        assert kwargs["default_headers"] == {
            "HTTP-Referer": "http://localhost:3000"
        }


def test_gemini_only_has_no_fallback(fake_models):
    gemini_seen, openrouter_seen = fake_models

    models = make_chat_models(_settings(openrouter_api_key=None))

    assert models.has_gemini is True
    assert models.has_openrouter is False
    assert all(
        profile.fallback is None
        for profile in (models.question, models.evaluation, models.email)
    )
    assert openrouter_seen == []
    assert len(gemini_seen) == 3


def test_openrouter_only_uses_primary_model_rule(fake_models):
    _, openrouter_seen = fake_models

    models = make_chat_models(_settings(gemini_api_key=None))

    assert models.has_gemini is False
    assert models.has_openrouter is True
    assert resolve_openrouter_model(
        _settings(gemini_api_key=None)
    ) == "openai/gpt-oss-120b:free"
    assert all(
        kwargs["model_name"] == "openai/gpt-oss-120b:free"
        for kwargs in openrouter_seen
    )
    assert all(
        profile.fallback is None
        for profile in (models.question, models.evaluation, models.email)
    )


def test_openrouter_only_falls_back_to_fallback_model_name(fake_models):
    _, openrouter_seen = fake_models
    make_chat_models(
        _settings(gemini_api_key=None, llm_primary_model=None)
    )

    assert all(
        kwargs["model_name"] == "meta-llama/llama-3.1-8b-instruct:free"
        for kwargs in openrouter_seen
    )


def test_neither_provider_raises_value_error(fake_models):
    with pytest.raises(ValueError, match="Neither GEMINI_API_KEY"):
        make_chat_models(
            _settings(gemini_api_key=None, openrouter_api_key=None)
        )


def test_settings_from_env_requires_a_provider(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)

    with pytest.raises(ValueError, match="Neither GEMINI_API_KEY"):
        Settings.from_env()


def test_settings_from_env_defaults(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "key")
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    monkeypatch.delenv("GEMINI_CHAT_MODEL", raising=False)
    monkeypatch.delenv("MAX_FOLLOWUPS_PER_TOPIC", raising=False)

    settings = Settings.from_env()

    assert settings.gemini_model == "gemini-2.5-flash"
    assert settings.embedding_model == "gemini-embedding-001"
    assert settings.embedding_dims == 768
    assert settings.max_followups_per_topic == 2
