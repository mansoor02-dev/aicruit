"""Canonical asynchronous client for structured LLM requests."""

import asyncio
import json
import logging
import os
from typing import TypeVar

import httpx
from dotenv import load_dotenv
from pydantic import BaseModel, ValidationError

load_dotenv()

logger = logging.getLogger(__name__)
T = TypeVar("T", bound=BaseModel)

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
FALLBACK_MODEL = os.getenv(
    "LLM_FALLBACK_MODEL", "meta-llama/llama-3.1-8b-instruct:free"
)
OPENROUTER_PRIMARY_MODEL = os.getenv("LLM_PRIMARY_MODEL")
GEMINI_MODEL = os.getenv("GEMINI_CHAT_MODEL", "gemini-2.5-flash")
DEFAULT_TIMEOUT_SECONDS = 60.0


class LLMProviderError(RuntimeError):
    """Raised when all configured LLM providers fail."""


class LLMClient:
    """Gemini-primary, OpenRouter-fallback async LLM client."""

    def __init__(self, timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS):
        self.timeout_seconds = timeout_seconds
        self._openrouter_key = os.getenv("OPENROUTER_API_KEY")
        self._gemini_client = None

        if os.getenv("GEMINI_API_KEY"):
            try:
                from google import genai

                self._gemini_client = genai.Client(
                    api_key=os.environ["GEMINI_API_KEY"]
                )
            except ImportError:
                logger.warning("google-genai is unavailable; Gemini is disabled")

        if not self._gemini_client and not self._openrouter_key:
            raise ValueError(
                "Neither GEMINI_API_KEY nor OPENROUTER_API_KEY is configured"
            )

    async def _gemini_complete(
        self,
        prompt: str,
        system: str,
        max_tokens: int,
        model: str | None,
        temperature: float,
    ) -> str:
        response = await self._gemini_client.aio.models.generate_content(
            model=model or GEMINI_MODEL,
            contents=f"SYSTEM: {system}\n\nUSER: {prompt}",
            config={
                "temperature": temperature,
                "max_output_tokens": max_tokens,
                "top_p": 0.95,
            },
        )
        text = getattr(response, "text", "") or ""
        if not text.strip():
            raise RuntimeError("Gemini returned an empty response")
        return text.strip()

    async def _openrouter_complete(
        self,
        prompt: str,
        system: str,
        max_tokens: int,
        model: str | None,
        temperature: float,
    ) -> str:
        payload = {
            "model": model or FALLBACK_MODEL,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": prompt},
            ],
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        headers = {
            "Authorization": f"Bearer {self._openrouter_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": os.getenv("APP_URL", "http://localhost:3000"),
        }
        timeout = httpx.Timeout(self.timeout_seconds)
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.post(
                OPENROUTER_URL,
                headers=headers,
                json=payload,
            )
            response.raise_for_status()
            data = response.json()

        choices = data.get("choices", [])
        if not choices:
            raise RuntimeError("OpenRouter returned no completion choices")
        text = choices[0].get("message", {}).get("content", "")
        if not isinstance(text, str) or not text.strip():
            raise RuntimeError("OpenRouter returned an empty completion")
        return text.strip()

    async def complete(
        self,
        prompt: str,
        system: str = "You are a helpful AI assistant for a recruitment platform.",
        model: str | None = None,
        max_tokens: int = 1500,
        temperature: float = 0.1,
    ) -> str:
        """Request a completion without blocking the event loop.

        Each configured provider is attempted at most once. Gemini is primary
        when configured; OpenRouter is the fallback. OpenRouter-only deployments
        may select their model through LLM_PRIMARY_MODEL.
        """
        gemini_error: Exception | None = None
        if self._gemini_client:
            try:
                return await asyncio.wait_for(
                    self._gemini_complete(
                        prompt, system, max_tokens, model, temperature
                    ),
                    timeout=self.timeout_seconds,
                )
            except Exception as exc:
                gemini_error = exc
                logger.warning(
                    "Gemini completion failed (%s); trying OpenRouter when configured",
                    type(exc).__name__,
                )

        if self._openrouter_key:
            try:
                openrouter_model = model or (
                    FALLBACK_MODEL
                    if self._gemini_client
                    else OPENROUTER_PRIMARY_MODEL or FALLBACK_MODEL
                )
                return await asyncio.wait_for(
                    self._openrouter_complete(
                        prompt, system, max_tokens, openrouter_model, temperature
                    ),
                    timeout=self.timeout_seconds,
                )
            except Exception as exc:
                logger.error(
                    "OpenRouter completion failed (%s)", type(exc).__name__,
                    exc_info=True,
                )
                raise LLMProviderError(
                    "All configured LLM providers failed"
                ) from exc

        if gemini_error is not None:
            raise LLMProviderError(
                "Gemini failed and no OpenRouter fallback is configured"
            ) from gemini_error
        raise LLMProviderError("No LLM provider is configured")

    async def complete_json(
        self,
        prompt: str,
        response_model: type[T],
        system: str | None = None,
        model: str | None = None,
        max_tokens: int = 1500,
        temperature: float = 0.1,
    ) -> T:
        """Return a Pydantic-validated structured completion."""
        schema = json.dumps(response_model.model_json_schema())
        system_prompt = system or (
            "Return only valid JSON matching this response schema: "
            f"{schema}"
        )
        if system:
            system_prompt = (
                f"{system}\n\nReturn only valid JSON matching this response "
                f"schema: {schema}"
            )
        raw = await self.complete(
            prompt=prompt,
            system=system_prompt,
            model=model,
            max_tokens=max_tokens,
            temperature=temperature,
        )
        cleaned = raw.strip()
        if cleaned.startswith("```"):
            cleaned = cleaned.split("```", maxsplit=2)[1].strip()
            if cleaned.lower().startswith("json"):
                cleaned = cleaned[4:].strip()
        try:
            return response_model.model_validate_json(cleaned)
        except (ValidationError, ValueError):
            logger.warning(
                "LLM response did not match %s",
                response_model.__name__,
                exc_info=True,
            )
            raise
