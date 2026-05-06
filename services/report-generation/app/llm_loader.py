"""
LLM loader — same pattern as question-generation service.
Supports Gemini (primary) with OpenRouter fallback.
"""

import json
import logging
import os
import re
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from dotenv import load_dotenv
from openai import OpenAI

# Always load .env from the service root, regardless of CWD
_ENV_PATH = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(_ENV_PATH)

logger = logging.getLogger("report-gen")

# Retry settings for rate-limited APIs
_MAX_RETRIES = 3
_RETRY_BASE_DELAY = 5  # seconds


# ── OpenRouter Wrapper ───────────────────────────────────────────────────────

class OpenRouterChat:
    """OpenRouter API (OpenAI-compatible)."""

    def __init__(self, model_name: str = "arcee-ai/trinity-large-preview:free"):
        api_key = os.getenv("OPENROUTER_API_KEY")
        if not api_key:
            raise ValueError("OPENROUTER_API_KEY environment variable not set")

        self.client = OpenAI(base_url="https://openrouter.ai/api/v1", api_key=api_key)
        self.model_name = model_name

    def create_chat_completion(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.1,
        max_tokens: int = 512,
        top_p: float = 0.95,
        **_,
    ) -> Dict[str, Any]:
        try:
            response = self.client.chat.completions.create(
                model=self.model_name,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                top_p=top_p,
            )
            choices = response.choices or []
            msg = choices[0].message if choices else None
            content = msg.content.strip() if msg and msg.content else ""
            return {"choices": [{"message": {"role": "assistant", "content": content}}]}
        except Exception as e:
            logger.warning("OpenRouter failed (%s), falling back to Gemini…", e)
            return GeminiChat().create_chat_completion(
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
            )


# ── Gemini Wrapper ───────────────────────────────────────────────────────────

class GeminiChat:
    """Google Gemini API wrapper.

    Uses gemini-2.0-flash by default (1 500 RPD on the free tier).
    gemini-2.5-flash only allows 20 RPD on the free tier — avoid it.
    """

    def __init__(self, model_name: str = "gemini-2.0-flash"):
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise ValueError("GEMINI_API_KEY environment variable not set")

        try:
            from google import genai
            self.client = genai.Client(api_key=api_key)
        except ImportError:
            raise ImportError(
                "google-genai package not installed. Run: pip install google-genai"
            )

        self.model_name = model_name

    def create_chat_completion(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.1,
        max_tokens: int = 512,
        **_,
    ) -> Dict[str, Any]:
        prompt = "\n".join(f"{m['role'].upper()}: {m['content']}" for m in messages)

        # For thinking models (2.5-*), internal reasoning tokens count
        # towards max_output_tokens.  Keep a generous floor just in case.
        effective_max = max(max_tokens, 2048)

        for attempt in range(1, _MAX_RETRIES + 1):
            try:
                response = self.client.models.generate_content(
                    model=self.model_name,
                    contents=prompt,
                    config={"temperature": temperature, "max_output_tokens": effective_max, "top_p": 0.95},
                )
                text = getattr(response, "text", "") or ""
                return {"choices": [{"message": {"role": "assistant", "content": text.strip()}}]}
            except Exception as e:
                err_str = str(e)
                if "429" in err_str or "RESOURCE_EXHAUSTED" in err_str:
                    wait = _RETRY_BASE_DELAY * attempt
                    logger.warning("Gemini rate-limited (attempt %d/%d). Retrying in %ds…", attempt, _MAX_RETRIES, wait)
                    time.sleep(wait)
                else:
                    raise  # non-retryable error

        # All retries exhausted
        raise RuntimeError(f"Gemini rate-limited after {_MAX_RETRIES} retries")


# ── LLM Loader ───────────────────────────────────────────────────────────────

class LLMLoader:
    """Loads and caches an LLM callable."""

    def __init__(self, model_type: str = "openrouter"):
        self.model_type = model_type
        self._llm: Optional[Any] = None

    def get_llm(self) -> Any:
        if self._llm is not None:
            return self._llm

        if self.model_type == "openrouter":
            self._llm = OpenRouterChat().create_chat_completion
            logger.info("Loaded OpenRouter LLM")
        else:
            self._llm = GeminiChat().create_chat_completion
            logger.info("Loaded Gemini LLM")

        return self._llm


# ── JSON extraction helper ───────────────────────────────────────────────────

def _extract_json(text: str) -> Optional[Dict]:
    """Try multiple strategies to pull a JSON object from raw LLM text."""
    # 1) Direct parse (LLM returned pure JSON)
    stripped = text.strip()
    if stripped.startswith("{"):
        try:
            return json.loads(stripped)
        except json.JSONDecodeError:
            pass

    # 2) Fenced code block: ```json ... ```
    block = re.search(r"```(?:json)?\s*(\{.*\})\s*```", text, re.DOTALL)
    if block:
        try:
            return json.loads(block.group(1))
        except json.JSONDecodeError:
            pass

    # 3) Greedy extraction of outermost { ... }
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            # Clean control characters and retry
            cleaned = re.sub(r"[\x00-\x1f]+", " ", match.group(0))
            try:
                return json.loads(cleaned)
            except json.JSONDecodeError:
                pass

    return None


# ── Convenience helper ───────────────────────────────────────────────────────

def call_llm_json(llm: Any, prompt: str, max_tokens: int = 512) -> Optional[Dict]:
    """Call the LLM and extract the first JSON object from its response."""
    try:
        resp = llm(
            messages=[{"role": "user", "content": prompt}],
            temperature=0.2,
            max_tokens=max_tokens,
        )
        text = resp["choices"][0]["message"]["content"]

        if not text or not text.strip():
            logger.warning("LLM returned empty response")
            return None

        logger.info("LLM response (%d chars): %.200s", len(text), text)

        result = _extract_json(text)
        if result is None:
            logger.warning("Could not extract JSON from LLM response: %.200s", text)
        return result

    except Exception as e:
        logger.error("LLM call failed: %s", e)
    return None
