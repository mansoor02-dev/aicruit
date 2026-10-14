"""Async LLM client with provider fallback and LangChain-validated output."""

import asyncio
import logging
import os
from pathlib import Path
from typing import Any, Awaitable, Callable, TypeVar

import httpx
from dotenv import load_dotenv
from langchain_core.messages import BaseMessage
from langchain_core.output_parsers import PydanticOutputParser
from langchain_core.prompts import ChatPromptTemplate
from pydantic import BaseModel

load_dotenv(Path(__file__).resolve().parents[2] / ".env")

logger = logging.getLogger(__name__)
T = TypeVar("T", bound=BaseModel)

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
DEFAULT_GEMINI_MODEL = "gemini-2.5-flash"
DEFAULT_OPENROUTER_MODEL = "meta-llama/llama-3.1-8b-instruct:free"
DEFAULT_TIMEOUT_SECONDS = 20.0
MAX_RETRIES = 1


class LLMProviderError(RuntimeError):
    """Raised when configured providers cannot return valid structured output."""


class LLMClient:
    """Gemini-primary, OpenRouter-fallback client with bounded async I/O."""

    def __init__(
        self,
        timeout_seconds: float | None = None,
        max_retries: int = MAX_RETRIES,
    ):
        configured_timeout = (
            timeout_seconds
            if timeout_seconds is not None
            else float(os.getenv("LLM_TIMEOUT_SECONDS", DEFAULT_TIMEOUT_SECONDS))
        )
        if configured_timeout <= 0:
            raise ValueError("LLM timeout must be greater than zero")
        self.timeout_seconds = configured_timeout
        self.max_retries = min(MAX_RETRIES, max(0, max_retries))
        self._openrouter_key = os.getenv("OPENROUTER_API_KEY")
        self._openrouter_model = os.getenv(
            "LLM_FALLBACK_MODEL", DEFAULT_OPENROUTER_MODEL
        )
        self._gemini_model = os.getenv(
            "GEMINI_CHAT_MODEL",
            os.getenv("LLM_PRIMARY_MODEL", DEFAULT_GEMINI_MODEL),
        )
        self._gemini_client = None
        if os.getenv("GEMINI_API_KEY"):
            try:
                from google import genai

                self._gemini_client = genai.Client(
                    api_key=os.environ["GEMINI_API_KEY"]
                )
            except ImportError:
                logger.warning("google-genai is unavailable; Gemini is disabled")

    async def complete_structured(
        self,
        prompt: ChatPromptTemplate,
        response_model: type[T],
        values: dict[str, Any],
        *,
        max_tokens: int,
        temperature: float = 0.1,
    ) -> T:
        """Format a LangChain prompt and return a Pydantic-validated response."""
        parser = PydanticOutputParser(pydantic_object=response_model)
        messages = prompt.partial(
            format_instructions=parser.get_format_instructions()
        ).format_messages(**values)
        providers = []
        if self._gemini_client is not None:
            providers.append(("Gemini", self._complete_gemini))
        if self._openrouter_key:
            providers.append(("OpenRouter", self._complete_openrouter))
        if not providers:
            raise LLMProviderError("No LLM provider is configured")

        failures: list[str] = []
        for provider_name, complete in providers:
            try:
                raw = await self._with_retries(
                    complete,
                    messages,
                    max_tokens=max_tokens,
                    temperature=temperature,
                )
                return parser.parse(raw)
            except Exception as exc:
                logger.warning(
                    "%s report-generation request failed (%s)",
                    provider_name,
                    type(exc).__name__,
                )
                failures.append(f"{provider_name}: {type(exc).__name__}")

        raise LLMProviderError(
            "No configured LLM provider returned valid output ("
            + "; ".join(failures)
            + ")"
        )

    async def _with_retries(
        self,
        complete: Callable[..., Awaitable[str]],
        messages: list[BaseMessage],
        **kwargs: Any,
    ) -> str:
        for attempt in range(self.max_retries + 1):
            try:
                return await asyncio.wait_for(
                    complete(messages, **kwargs),
                    timeout=self.timeout_seconds,
                )
            except Exception as exc:
                if attempt >= self.max_retries or not self._is_retryable(exc):
                    raise
                delay = min(0.25 * (2**attempt), 1.0)
                logger.info(
                    "Transient report-provider failure; retry %d/%d in %.2fs",
                    attempt + 1,
                    self.max_retries,
                    delay,
                )
                await asyncio.sleep(delay)
        raise AssertionError("Retry loop exited unexpectedly")

    @staticmethod
    def _is_retryable(exc: Exception) -> bool:
        if isinstance(
            exc,
            (httpx.TimeoutException, httpx.TransportError, asyncio.TimeoutError),
        ):
            return True
        status_code = getattr(exc, "status_code", None)
        response = getattr(exc, "response", None)
        if response is not None:
            status_code = getattr(response, "status_code", status_code)
        return status_code == 429 or (
            isinstance(status_code, int) and 500 <= status_code < 600
        )

    async def _complete_gemini(
        self,
        messages: list[BaseMessage],
        *,
        max_tokens: int,
        temperature: float,
    ) -> str:
        if self._gemini_client is None:
            raise LLMProviderError("Gemini is not configured")
        contents = "\n\n".join(
            f"{message.type.upper()}: {message.content}" for message in messages
        )
        response = await self._gemini_client.aio.models.generate_content(
            model=self._gemini_model,
            contents=contents,
            config={
                "temperature": temperature,
                "max_output_tokens": max_tokens,
                "top_p": 0.95,
            },
        )
        text = getattr(response, "text", "") or ""
        if not text.strip():
            raise ValueError("Gemini returned an empty response")
        return text.strip()

    async def _complete_openrouter(
        self,
        messages: list[BaseMessage],
        *,
        max_tokens: int,
        temperature: float,
    ) -> str:
        payload = {
            "model": self._openrouter_model,
            "messages": [
                {
                    "role": {
                        "system": "system",
                        "human": "user",
                        "ai": "assistant",
                    }.get(message.type, "user"),
                    "content": message.content,
                }
                for message in messages
            ],
            "max_tokens": max_tokens,
            "temperature": temperature,
        }
        headers = {
            "Authorization": f"Bearer {self._openrouter_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": os.getenv("APP_URL", "http://localhost:3000"),
        }
        async with httpx.AsyncClient(
            timeout=httpx.Timeout(self.timeout_seconds)
        ) as client:
            response = await client.post(
                OPENROUTER_URL,
                headers=headers,
                json=payload,
            )
            response.raise_for_status()
            data = response.json()

        choices = data.get("choices", [])
        if not choices:
            raise ValueError("OpenRouter returned no completion choices")
        text = choices[0].get("message", {}).get("content", "")
        if not isinstance(text, str) or not text.strip():
            raise ValueError("OpenRouter returned an empty completion")
        return text.strip()
