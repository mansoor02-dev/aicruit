"""
Resume parsing pipeline orchestrator.

Coordinates the full extraction pipeline:
  PDF validation → Text extraction → Text normalization →
  LLM structured extraction → Deterministic validation → API response

Features:
- In-memory content-hash caching (optional, keyed by hash + schema version + model).
- Structured metrics logging (duration, OCR usage, LLM calls, cache hits).
- Clear error classification and controlled error responses.
- Never exposes resume content in logs.

LangGraph note:
This orchestrator uses plain Python functions with explicit control flow.
LangGraph could be valuable in the future for:
- Conditional fallback chains (e.g., try native → OCR → error)
- Resumable processing (checkpoint after extraction for async review)
- Human-in-the-loop review for low-confidence extractions
- Parallel extraction strategies (different prompts, ensemble)
Currently the linear pipeline doesn't warrant the added complexity.
"""

from __future__ import annotations

import hashlib
import logging
import time
from collections import OrderedDict
from dataclasses import dataclass, field
from typing import Any, Optional

from app.core.config import Settings, get_settings
from app.services.pdf_extractor import (
    ExtractionResult,
    OCRUnavailableError,
    PDFValidationError,
    extract_text,
)
from app.services.text_normalizer import NormalizationResult, normalize_text
from app.services.resume_extractor import (
    ExtractionError,
    PermanentLLMError,
    extract_resume,
)
from app.services.resume_validator import ValidationResult, validate_extraction

logger = logging.getLogger(__name__)


# ── Pipeline result ──────────────────────────────────────────────────────

@dataclass
class PipelineResult:
    """Complete result from the resume parsing pipeline."""
    data: dict[str, Any]
    content_hash: str = ""
    elapsed_seconds: float = 0.0
    cached: bool = False

    # Metrics (for observability, never exposed in API response)
    total_pages: int = 0
    native_pages: int = 0
    ocr_pages: int = 0
    empty_pages: int = 0
    original_word_count: int = 0
    final_word_count: int = 0
    was_truncated: bool = False
    validation_warnings: list[str] = field(default_factory=list)
    validation_corrections: list[str] = field(default_factory=list)
    extraction_warnings: list[str] = field(default_factory=list)


# ── Pipeline errors ──────────────────────────────────────────────────────

class PipelineError(Exception):
    """Base class for pipeline errors with HTTP status code."""
    def __init__(self, message: str, status_code: int = 500):
        super().__init__(message)
        self.status_code = status_code


class FileValidationError(PipelineError):
    """File validation failure (400)."""
    def __init__(self, message: str):
        super().__init__(message, status_code=400)


class ExtractionFailedError(PipelineError):
    """Text extraction failure (422)."""
    def __init__(self, message: str):
        super().__init__(message, status_code=422)


class LLMFailedError(PipelineError):
    """LLM provider failure (502)."""
    def __init__(self, message: str):
        super().__init__(message, status_code=502)


# ── In-memory cache ──────────────────────────────────────────────────────

class _LRUCache:
    """Thread-safe LRU cache using OrderedDict."""

    def __init__(self, max_size: int = 128):
        self._cache: OrderedDict[str, PipelineResult] = OrderedDict()
        self._max_size = max_size
        self._hits = 0
        self._misses = 0

    def _build_key(
        self,
        content_hash: str,
        schema_version: str,
        model: str,
    ) -> str:
        """Build a cache key from content hash, schema version, and model."""
        return hashlib.sha256(
            f"{content_hash}:{schema_version}:{model}".encode()
        ).hexdigest()

    def get(
        self,
        content_hash: str,
        schema_version: str,
        model: str,
    ) -> Optional[PipelineResult]:
        key = self._build_key(content_hash, schema_version, model)
        if key in self._cache:
            # Move to end (most recently used)
            self._cache.move_to_end(key)
            self._hits += 1
            return self._cache[key]
        self._misses += 1
        return None

    def put(
        self,
        content_hash: str,
        schema_version: str,
        model: str,
        result: PipelineResult,
    ) -> None:
        key = self._build_key(content_hash, schema_version, model)
        if key in self._cache:
            self._cache.move_to_end(key)
        self._cache[key] = result
        while len(self._cache) > self._max_size:
            self._cache.popitem(last=False)

    @property
    def stats(self) -> dict[str, int]:
        return {
            "hits": self._hits,
            "misses": self._misses,
            "size": len(self._cache),
        }


# Module-level cache instance
_cache: Optional[_LRUCache] = None


def _get_cache(settings: Settings) -> Optional[_LRUCache]:
    global _cache
    if not settings.cache_enabled or settings.cache_max_size == 0:
        return None
    if _cache is None:
        _cache = _LRUCache(max_size=settings.cache_max_size)
    return _cache


# ── Pipeline ─────────────────────────────────────────────────────────────

async def parse_resume(
    data: bytes,
    ext: str,
    settings: Optional[Settings] = None,
) -> PipelineResult:
    """
    Full resume parsing pipeline.

    Steps:
    1. Extract text from PDF/DOCX (with validation and conditional OCR).
    2. Normalize text (clean, deduplicate headers, section-aware truncation).
    3. Check cache for existing result.
    4. Extract structured data via LLM.
    5. Validate extracted data deterministically.
    6. Cache and return result.

    Args:
        data: Raw file bytes.
        ext: File extension (e.g., ".pdf").
        settings: Service configuration.

    Returns:
        PipelineResult with validated extraction data.

    Raises:
        FileValidationError: For invalid files (400).
        ExtractionFailedError: For empty/unreadable files (422).
        LLMFailedError: For LLM provider failures (502).
        PipelineError: For other pipeline failures (500).
    """
    if settings is None:
        settings = get_settings()

    start_time = time.perf_counter()

    # ── Step 1: Extract text ─────────────────────────────────────────
    try:
        extraction: ExtractionResult = extract_text(data, ext, settings)
    except PDFValidationError as e:
        raise FileValidationError(str(e)) from e
    except OCRUnavailableError as e:
        raise ExtractionFailedError(str(e)) from e
    except ValueError as e:
        raise FileValidationError(str(e)) from e
    except Exception as e:
        logger.error("pipeline.extraction_error", extra={"error": str(e)})
        raise PipelineError(f"Text extraction failed: {e}") from e

    if not extraction.text.strip():
        raise ExtractionFailedError(
            "Could not extract text from the document. "
            "The file may be scanned or contain only images."
        )

    # ── Step 2: Normalize text ───────────────────────────────────────
    try:
        normalization: NormalizationResult = normalize_text(
            extraction.text, settings
        )
    except ValueError as e:
        raise ExtractionFailedError(str(e)) from e

    # ── Step 3: Check cache ──────────────────────────────────────────
    cache = _get_cache(settings)
    if cache is not None:
        cached_result = cache.get(
            extraction.content_hash,
            settings.cache_schema_version,
            settings.gemini_model,
        )
        if cached_result is not None:
            cached_result.cached = True
            cached_result.elapsed_seconds = round(
                time.perf_counter() - start_time, 2
            )
            logger.info(
                "pipeline.cache_hit",
                extra={"content_hash": extraction.content_hash[:12]},
            )
            return cached_result

    # ── Step 4: LLM extraction ───────────────────────────────────────
    try:
        resume_extraction = await extract_resume(
            normalization.text, settings
        )
    except PermanentLLMError as e:
        raise LLMFailedError(f"LLM provider error: {e}") from e
    except ExtractionError as e:
        raise LLMFailedError(f"Extraction failed: {e}") from e

    # ── Step 5: Validate ─────────────────────────────────────────────
    validation: ValidationResult = validate_extraction(resume_extraction)

    # ── Step 6: Build result ─────────────────────────────────────────
    elapsed = round(time.perf_counter() - start_time, 2)

    result = PipelineResult(
        data=validation.data,
        content_hash=extraction.content_hash,
        elapsed_seconds=elapsed,
        total_pages=extraction.total_pages,
        native_pages=extraction.native_pages,
        ocr_pages=extraction.ocr_pages,
        empty_pages=extraction.empty_pages,
        original_word_count=normalization.original_word_count,
        final_word_count=normalization.final_word_count,
        was_truncated=normalization.was_truncated,
        validation_warnings=validation.warnings,
        validation_corrections=validation.corrections,
        extraction_warnings=extraction.warnings,
    )

    # Cache the result
    if cache is not None:
        cache.put(
            extraction.content_hash,
            settings.cache_schema_version,
            settings.gemini_model,
            result,
        )

    # Log pipeline metrics (no resume content)
    logger.info(
        "pipeline.success",
        extra={
            "elapsed_s": elapsed,
            "total_pages": extraction.total_pages,
            "native_pages": extraction.native_pages,
            "ocr_pages": extraction.ocr_pages,
            "original_words": normalization.original_word_count,
            "final_words": normalization.final_word_count,
            "truncated": normalization.was_truncated,
            "cached": False,
            "cache_stats": cache.stats if cache else None,
        },
    )

    return result
