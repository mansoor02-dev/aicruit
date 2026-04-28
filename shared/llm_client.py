import os
import json
import logging
import httpx
from typing import Type, TypeVar
from pydantic import BaseModel

logger = logging.getLogger(__name__)
T = TypeVar("T", bound=BaseModel)

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"

PRIMARY_MODEL = os.getenv("LLM_PRIMARY_MODEL", "google/gemini-flash-2.0")
FALLBACK_MODEL = os.getenv("LLM_FALLBACK_MODEL", "meta-llama/llama-3.1-8b-instruct:free")


class LLMClient:
    def __init__(self):
        self.api_key = os.getenv("OPENROUTER_API_KEY")
        if not self.api_key:
            raise ValueError("OPENROUTER_API_KEY env var not set")
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": os.getenv("APP_URL", "http://localhost:3000"),
        }

    async def complete(
        self,
        prompt: str,
        system: str = "You are a helpful AI assistant for a recruitment platform.",
        model: str = None,
        max_tokens: int = 1500,
    ) -> str:
        """Simple text completion. Returns string."""
        model = model or PRIMARY_MODEL
        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": prompt},
            ],
            "max_tokens": max_tokens,
        }
        
        async with httpx.AsyncClient(timeout=60.0) as client:
            try:
                resp = await client.post(OPENROUTER_URL, headers=self.headers, json=payload)
                resp.raise_for_status()
                data = resp.json()
                choices = data.get("choices", [])
                if not choices:
                    raise RuntimeError("Empty response from LLM")

                content = choices[0].get("message", {}).get("content", "")
                return content.strip()
            
            except httpx.HTTPStatusError as e:
                if model != FALLBACK_MODEL:
                    logger.warning(f"Primary model failed ({e.response.status_code}), trying fallback")
                    return await self.complete(prompt, system, FALLBACK_MODEL, max_tokens)
                raise
            except httpx.RequestError as e:
                logger.error(f"Request failed: {str(e)}")
                raise

    async def complete_json(
        self,
        prompt: str,
        response_model: Type[T],
        system: str = None,
        model: str = None,
    ) -> T:
        """
        Structured JSON completion. Returns validated Pydantic model instance.
        Prompt should instruct the LLM to return valid JSON matching the schema.
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