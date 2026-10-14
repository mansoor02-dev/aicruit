"""
LangChain-based structured resume extraction using Google Gemini.

Uses langchain-google-genai ChatGoogleGenerativeAI for model integration.
Leverages Gemini's native JSON mode via `response_mime_type` for reliable
structured output without a separate parsing step.

Features:
- Single LLM call on the normal path (no second call for validation).
- One bounded repair attempt if initial output fails schema validation.
- Exponential backoff with jitter for transient errors (rate limits, timeouts).
- Concurrency limiter to prevent service overload.
- Structured metrics logging for observability.

LangGraph note:
- This module uses plain Python functions with explicit control flow.
- LangGraph could be introduced if we need conditional fallback chains,
  resumable processing, human-in-the-loop review, or parallel extraction
  strategies. The current linear pipeline doesn't warrant it.
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from typing import Optional

from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential_jitter,
)

from app.core.config import Settings, get_settings
from app.prompts import RESUME_EXTRACTION_SYSTEM_PROMPT, RESUME_EXTRACTION_USER_TEMPLATE
from app.schemas.resume import ResumeExtraction

logger = logging.getLogger(__name__)

# ── Concurrency limiter (module-level singleton) ─────────────────────────

_semaphore: Optional[asyncio.Semaphore] = None


def _get_semaphore(settings: Settings) -> asyncio.Semaphore:
    global _semaphore
    if _semaphore is None:
        _semaphore = asyncio.Semaphore(settings.max_concurrent_llm_calls)
    return _semaphore


# ── Error classification ─────────────────────────────────────────────────

class TransientLLMError(Exception):
    """Retryable LLM error (rate limit, timeout, temporary unavailability)."""
    pass


class PermanentLLMError(Exception):
    """Non-retryable LLM error (auth failure, invalid model, etc.)."""
    pass


class ExtractionError(Exception):
    """Error during structured extraction (schema validation failure, etc.)."""
    pass


def _classify_error(exc: Exception) -> Exception:
    """Classify a raw provider exception as transient or permanent."""
    msg = str(exc).lower()

    # Transient errors worth retrying
    transient_markers = [
        "rate limit", "429", "quota", "resource exhausted",
        "503", "service unavailable", "deadline exceeded",
        "timeout", "connection", "timed out",
        "500", "internal server error",
    ]
    for marker in transient_markers:
        if marker in msg:
            return TransientLLMError(str(exc))

    # Permanent errors
    permanent_markers = [
        "401", "403", "invalid api key", "permission denied",
        "model not found", "invalid model",
    ]
    for marker in permanent_markers:
        if marker in msg:
            return PermanentLLMError(str(exc))

    # Default to transient (safer for unknown errors)
    return TransientLLMError(str(exc))


# ── LangChain model construction ─────────────────────────────────────────

def _build_chain(settings: Settings):
    """
    Build the LangChain chat model for Gemini.

    Uses ChatGoogleGenerativeAI from langchain-google-genai.
    Configures native JSON mode for structured output.
    """
    from langchain_google_genai import ChatGoogleGenerativeAI

    llm = ChatGoogleGenerativeAI(
        model=settings.gemini_model,
        google_api_key=settings.gemini_api_key,
        temperature=settings.llm_temperature,
        max_output_tokens=settings.llm_max_output_tokens,
        top_p=0.95,
        timeout=settings.llm_timeout_seconds,
    )

    return llm


def _invoke_llm_sync(
    resume_text: str,
    settings: Settings,
) -> ResumeExtraction | str:
    """
    Invoke Gemini with structured output, falling back to its raw JSON mode.

    This synchronous call runs in an executor when used by the async pipeline.
    """
    from langchain_core.messages import HumanMessage, SystemMessage

    llm = _build_chain(settings)

    messages = [
        SystemMessage(content=RESUME_EXTRACTION_SYSTEM_PROMPT),
        HumanMessage(content=RESUME_EXTRACTION_USER_TEMPLATE.format(
            resume_text=resume_text
        )),
    ]

    try:
        structured_llm = llm.with_structured_output(ResumeExtraction)
        structured_result = structured_llm.invoke(messages)
        if isinstance(structured_result, ResumeExtraction):
            return structured_result
        return ResumeExtraction.model_validate(structured_result)
    except Exception as structured_error:
        logger.warning(
            "resume_extractor.structured_output_failed",
            extra={"error": str(structured_error)},
        )

    try:
        response = llm.invoke(messages)
        raw_text = response.content
        if isinstance(raw_text, list):
            raw_text = " ".join(str(part) for part in raw_text)
        if not isinstance(raw_text, str):
            raise ExtractionError("LLM returned neither structured data nor text")
        return raw_text.strip()
    except Exception as e:
        raise _classify_error(e) from e


# ── Retry-wrapped extraction ─────────────────────────────────────────────

@retry(
    retry=retry_if_exception_type(TransientLLMError),
    stop=stop_after_attempt(3),  # 1 initial + 2 retries
    wait=wait_exponential_jitter(initial=1, max=30, jitter=5),
    reraise=True,
)
def _invoke_with_retry(resume_text: str, settings: Settings) -> ResumeExtraction | str:
    """LLM invocation with retry on transient errors."""
    return _invoke_llm_sync(resume_text, settings)


# ── JSON parsing and validation ──────────────────────────────────────────

def _parse_llm_output(raw: ResumeExtraction | dict | str) -> ResumeExtraction:
    """
    Parse raw LLM output into a ResumeExtraction schema.

    Handles common LLM output quirks:
    - Markdown code fences around JSON
    - Leading/trailing whitespace
    """
    if isinstance(raw, ResumeExtraction):
        return raw
    if isinstance(raw, dict):
        try:
            return ResumeExtraction.model_validate(raw)
        except Exception as e:
            raise ExtractionError(f"LLM output does not match schema: {e}") from e

    text = raw.strip()

    # Strip markdown code fences
    if text.startswith("```"):
        lines = text.split("\n")
        # Remove first line (```json or ```)
        lines = lines[1:]
        # Remove last line if it's ```)
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text = "\n".join(lines).strip()

    try:
        data = json.loads(text)
    except json.JSONDecodeError as e:
        raise ExtractionError(f"LLM output is not valid JSON: {e}") from e

    try:
        return ResumeExtraction.model_validate(data)
    except Exception as e:
        raise ExtractionError(f"LLM output does not match schema: {e}") from e


# ── Public API ────────────────────────────────────────────────────────────

async def extract_resume(
    resume_text: str,
    settings: Optional[Settings] = None,
) -> ResumeExtraction:
    """
    Extract structured resume data from text using LLM.

    This is the main entry point for LLM-based extraction.

    Pipeline:
    1. Invoke LLM with retry on transient errors.
    2. Parse JSON output into ResumeExtraction schema.
    3. On schema validation failure, attempt one repair (re-parse with lenient defaults).
    4. Return validated ResumeExtraction.

    Args:
        resume_text: Normalized resume text.
        settings: Service configuration.

    Returns:
        ResumeExtraction with extracted data.

    Raises:
        PermanentLLMError: If the LLM provider returns a non-retryable error.
        ExtractionError: If extraction fails after all attempts.
    """
    if settings is None:
        settings = get_settings()

    if not settings.gemini_api_key:
        raise PermanentLLMError("GEMINI_API_KEY is not configured")

    sem = _get_semaphore(settings)
    start_time = time.perf_counter()
    retry_count = 0

    async with sem:
        try:
            loop = asyncio.get_event_loop()
            raw_output: ResumeExtraction | str = await loop.run_in_executor(
                None, _invoke_with_retry, resume_text, settings
            )
        except TransientLLMError as e:
            elapsed = time.perf_counter() - start_time
            logger.error(
                "resume_extractor.llm_exhausted",
                extra={"elapsed_s": round(elapsed, 2), "error": str(e)},
            )
            raise ExtractionError(
                f"LLM extraction failed after retries: {e}"
            ) from e
        except PermanentLLMError:
            raise

    elapsed = time.perf_counter() - start_time

    # Parse output
    try:
        result = _parse_llm_output(raw_output)
    except ExtractionError:
        # One repair attempt: try to extract JSON from the raw output
        import re
        json_match = (
            re.search(r"\{.*\}", raw_output, re.DOTALL)
            if isinstance(raw_output, str)
            else None
        )
        if json_match:
            try:
                result = _parse_llm_output(json_match.group())
                logger.info("resume_extractor.repair_succeeded")
            except ExtractionError:
                raise
        else:
            raise

    # Log metrics (never log resume content)
    logger.info(
        "resume_extractor.success",
        extra={
            "elapsed_s": round(elapsed, 2),
            "skills_count": len(result.skills),
            "experience_count": len(result.experience),
            "education_count": len(result.education),
            "has_email": bool(result.personal_info.email),
            "has_phone": bool(result.personal_info.phone),
        },
    )

    return result
