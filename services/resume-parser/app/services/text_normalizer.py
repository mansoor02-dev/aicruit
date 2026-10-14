"""
Deterministic text normalization for extracted resume text.

This module cleans PDF/OCR-extracted text while preserving meaningful
content: section headings, dates, contact info, employment history, etc.

The normalization pipeline:
1. Remove control characters (preserve newlines, tabs)
2. Remove PDF extraction artifacts (page markers, long digit noise)
3. Detect and remove repeated headers/footers (safe heuristic)
4. Normalize whitespace
5. Section-aware truncation to respect the LLM token budget

No information is silently discarded. If truncation is necessary, the
function returns a truncation warning.
"""

from __future__ import annotations

import re
import logging
from dataclasses import dataclass, field
from typing import Optional

from app.core.config import Settings, get_settings

logger = logging.getLogger(__name__)

# ── Pre-compiled patterns ─────────────────────────────────────────────────

_RE_CONTROL_CHARS = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
_RE_PAGE_MARKERS = re.compile(
    r"\b(?:page\s*\d+\s*(?:of\s*\d+)?)\b", re.IGNORECASE
)
_RE_LONG_DIGIT_NOISE = re.compile(r"\b\d{15,}\b")
_RE_MULTI_WHITESPACE = re.compile(r"[ \t]+")
_RE_BLANK_LINES = re.compile(r"\n{3,}")

# Section heading patterns for section-aware truncation
_SECTION_PATTERNS = re.compile(
    r"^(?:experience|work\s*experience|employment|professional\s*experience|"
    r"education|academic|skills|technical\s*skills|projects|"
    r"certifications?|publications?|interests|hobbies|languages|"
    r"summary|objective|profile|about(?:\s*me)?|"
    r"awards?|honors?|volunteer|references)"
    r"\s*:?\s*$",
    re.IGNORECASE | re.MULTILINE,
)


# ── Result type ───────────────────────────────────────────────────────────

@dataclass
class NormalizationResult:
    """Result of text normalization."""
    text: str
    original_word_count: int
    final_word_count: int
    was_truncated: bool = False
    truncation_message: str = ""
    removed_headers_footers: int = 0


# ── Header/footer detection ──────────────────────────────────────────────

def _detect_repeated_headers_footers(text: str) -> tuple[str, int]:
    """
    Detect and remove repeated headers/footers.

    Heuristic: Split text into page-like chunks (by double newline gaps).
    If the first or last line of 3+ chunks is identical (>10 chars),
    treat it as a header/footer and remove all occurrences.

    Only removes exact matches to avoid false positives.
    """
    # Split into page-like sections
    sections = re.split(r"\n{2,}", text)
    if len(sections) < 3:
        return text, 0

    # Check first lines
    first_lines: dict[str, int] = {}
    last_lines: dict[str, int] = {}

    for section in sections:
        lines = [l.strip() for l in section.strip().split("\n") if l.strip()]
        if not lines:
            continue
        fl = lines[0]
        if len(fl) > 10:
            first_lines[fl] = first_lines.get(fl, 0) + 1
        if len(lines) > 1:
            ll = lines[-1]
            if len(ll) > 10:
                last_lines[ll] = last_lines.get(ll, 0) + 1

    removed = 0
    # Remove lines appearing in 3+ sections
    for line_text, count in {**first_lines, **last_lines}.items():
        if count >= 3:
            text = text.replace(line_text, "")
            removed += count
            logger.debug(
                "text_normalizer.removed_repeated",
                extra={"line_preview": line_text[:40], "count": count},
            )

    return text, removed


# ── Section-aware truncation ──────────────────────────────────────────────

def _truncate_section_aware(text: str, max_words: int) -> tuple[str, str]:
    """
    Truncate text to max_words using section-aware strategy.

    Priority (highest first):
    1. Contact info / personal details (first ~200 words)
    2. Skills section
    3. Experience section
    4. Education section
    5. Projects section
    6. Everything else

    Returns:
        Tuple of (truncated_text, truncation_message).
    """
    words = text.split()
    if len(words) <= max_words:
        return text, ""

    # Find section boundaries
    lines = text.split("\n")
    sections: list[tuple[str, int, int]] = []  # (name, start_line, end_line)
    current_section = "header"
    current_start = 0

    for i, line in enumerate(lines):
        match = _SECTION_PATTERNS.match(line.strip())
        if match:
            if current_start < i:
                sections.append((current_section, current_start, i))
            current_section = line.strip().lower()
            current_start = i

    # Add final section
    if current_start < len(lines):
        sections.append((current_section, current_start, len(lines)))

    if not sections:
        # No sections detected — simple truncation
        truncated = " ".join(words[:max_words])
        return truncated, (
            f"Text truncated from {len(words)} to {max_words} words "
            f"(no section structure detected)"
        )

    # Build text by priority, keeping within budget
    priority_order = [
        "header",  # Personal info at the top
        "skills", "technical skills",
        "experience", "work experience", "employment", "professional experience",
        "education", "academic",
        "projects",
        "summary", "objective", "profile", "about me", "about",
    ]

    included_text_parts: list[str] = []
    remaining_words = max_words
    included_sections: list[str] = []

    # First pass: include sections by priority
    for target in priority_order:
        for sec_name, start, end in sections:
            if target in sec_name.lower() and sec_name not in included_sections:
                sec_text = "\n".join(lines[start:end])
                sec_words = sec_text.split()
                if len(sec_words) <= remaining_words:
                    included_text_parts.append(sec_text)
                    remaining_words -= len(sec_words)
                    included_sections.append(sec_name)
                elif remaining_words > 50:
                    # Partial inclusion
                    included_text_parts.append(" ".join(sec_words[:remaining_words]))
                    remaining_words = 0
                    included_sections.append(sec_name + " (partial)")

    # Second pass: include any remaining sections
    for sec_name, start, end in sections:
        if sec_name not in included_sections and remaining_words > 50:
            sec_text = "\n".join(lines[start:end])
            sec_words = sec_text.split()
            if len(sec_words) <= remaining_words:
                included_text_parts.append(sec_text)
                remaining_words -= len(sec_words)
                included_sections.append(sec_name)

    truncated = "\n\n".join(included_text_parts)
    message = (
        f"Text truncated from {len(words)} to {len(truncated.split())} words. "
        f"Included sections: {', '.join(included_sections)}"
    )

    return truncated, message


# ── Main normalization function ───────────────────────────────────────────

def normalize_text(
    text: str,
    settings: Optional[Settings] = None,
) -> NormalizationResult:
    """
    Normalize extracted resume text for LLM consumption.

    Args:
        text: Raw extracted text from PDF/DOCX.
        settings: Service configuration.

    Returns:
        NormalizationResult with cleaned text and metadata.

    Raises:
        ValueError: If text is empty after normalization.
    """
    if settings is None:
        settings = get_settings()

    if not text or not text.strip():
        raise ValueError("No text content to normalize (empty extraction)")

    original_words = len(text.split())

    # Step 1: Remove control characters
    text = _RE_CONTROL_CHARS.sub("", text)

    # Step 2: Remove extraction artifacts
    text = _RE_PAGE_MARKERS.sub("", text)
    text = _RE_LONG_DIGIT_NOISE.sub("", text)

    # Step 3: Remove repeated headers/footers
    text, removed_hf = _detect_repeated_headers_footers(text)

    # Step 4: Normalize whitespace
    text = _RE_MULTI_WHITESPACE.sub(" ", text)
    text = _RE_BLANK_LINES.sub("\n\n", text)
    text = text.strip()

    if not text:
        raise ValueError("Text is empty after normalization")

    # Step 5: Section-aware truncation
    was_truncated = False
    truncation_message = ""
    if len(text.split()) > settings.max_input_tokens:
        text, truncation_message = _truncate_section_aware(
            text, settings.max_input_tokens
        )
        was_truncated = True
        if truncation_message:
            logger.warning(
                "text_normalizer.truncated",
                extra={"truncation_message": truncation_message},
            )

    final_words = len(text.split())

    return NormalizationResult(
        text=text,
        original_word_count=original_words,
        final_word_count=final_words,
        was_truncated=was_truncated,
        truncation_message=truncation_message,
        removed_headers_footers=removed_hf,
    )
