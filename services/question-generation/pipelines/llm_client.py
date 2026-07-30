"""
Unified LLM client for the Question Generation service.

2-tier strategy:
  Primary  → Gemini 2.5 Flash (direct Google GenAI SDK)
  Fallback → Llama 3.1 8B Instruct (via OpenRouter)
"""

import os
import json
import logging
import httpx
from typing import Type, TypeVar
from pydantic import BaseModel

logger = logging.getLogger(__name__)
T = TypeVar("T", bound=BaseModel)

# ── OpenRouter fallback settings ─────────────────────────────────────────────
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
FALLBACK_MODEL = os.getenv("LLM_FALLBACK_MODEL", "meta-llama/llama-3.1-8b-instruct:free")

# ── Gemini primary settings ──────────────────────────────────────────────────
GEMINI_MODEL = os.getenv("LLM_PRIMARY_MODEL", "gemini-2.5-flash")


class LLMClient:
    """Async LLM client: Gemini primary, OpenRouter fallback."""

    def __init__(self):
        self._gemini_client = None
        self._openrouter_key = os.getenv("OPENROUTER_API_KEY")
        self._gemini_key = os.getenv("GEMINI_API_KEY")

        if self._gemini_key:
            try:
                from google import genai
                self._gemini_client = genai.Client(api_key=self._gemini_key)
            except ImportError:
                logger.warning("google-genai not installed; Gemini unavailable")

        if not self._gemini_client and not self._openrouter_key:
            raise ValueError(
                "Neither GEMINI_API_KEY nor OPENROUTER_API_KEY is set"
            )

        self._openrouter_headers = {
            "Authorization": f"Bearer {self._openrouter_key or ''}",
            "Content-Type": "application/json",
            "HTTP-Referer": os.getenv("APP_URL", "http://localhost:3000"),
        }

    # ── Primary: Gemini ──────────────────────────────────────────────────

    def _gemini_complete(
        self,
        prompt: str,
        system: str,
        max_tokens: int = 1500,
    ) -> str:
        """Synchronous Gemini call."""
        full_prompt = f"SYSTEM: {system}\n\nUSER: {prompt}"
        response = self._gemini_client.models.generate_content(
            model=GEMINI_MODEL,
            contents=full_prompt,
            config={
                "temperature": 0.1,
                "max_output_tokens": max(max_tokens, 2048),
                "top_p": 0.95,
            },
        )
        text = getattr(response, "text", "") or ""
        return text.strip()

    # ── Fallback: OpenRouter ─────────────────────────────────────────────

    async def _openrouter_complete(
        self,
        prompt: str,
        system: str,
        max_tokens: int = 1500,
    ) -> str:
        payload = {
            "model": FALLBACK_MODEL,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": prompt},
            ],
            "max_tokens": max_tokens,
        }
        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(
                OPENROUTER_URL,
                headers=self._openrouter_headers,
                json=payload,
            )
            resp.raise_for_status()
            data = resp.json()
            choices = data.get("choices", [])
            if not choices:
                raise RuntimeError("Empty response from OpenRouter")
            return choices[0].get("message", {}).get("content", "").strip()

    # ── Public API ───────────────────────────────────────────────────────

    async def complete(
        self,
        prompt: str,
        system: str = "You are a helpful AI assistant for a recruitment platform.",
        model: str = None,
        max_tokens: int = 1500,
    ) -> str:
        """Text completion. Tries Gemini first, falls back to OpenRouter."""
        import asyncio

        # Try Gemini (primary)
        if self._gemini_client:
            try:
                loop = asyncio.get_event_loop()
                return await loop.run_in_executor(
                    None, self._gemini_complete, prompt, system, max_tokens
                )
            except Exception as e:
                logger.warning(f"Gemini failed ({e}), trying OpenRouter fallback")

        # Fallback: OpenRouter
        if self._openrouter_key:
            return await self._openrouter_complete(prompt, system, max_tokens)

        raise RuntimeError("All LLM providers failed")

    async def complete_json(
        self,
        prompt: str,
        response_model: Type[T],
        system: str = None,
        model: str = None,
    ) -> T:
        """
        Structured JSON completion. Returns validated Pydantic model instance.
        """
        schema = response_model.model_json_schema()
        sys_prompt = system or (
            f"You are a data extraction assistant. "
            f"Always respond with valid JSON matching this schema: {json.dumps(schema)}. "
            f"No markdown, no explanation — pure JSON only."
        )
        raw = await self.complete(prompt, sys_prompt, model)
        raw = raw.strip()
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        return response_model.model_validate_json(raw.strip())
