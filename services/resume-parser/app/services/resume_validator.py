"""
Deterministic resume validation.

Validates extracted resume data without making additional LLM calls.
Focuses on data integrity: field types, formats, required fields, etc.

This module is separate from:
- PDF extraction (services/pdf_extractor.py)
- LLM invocation (services/resume_extractor.py)
- API routing (api.py)

Validation never fabricates data. If a field is invalid, it is cleaned
or set to the schema default, not filled with guessed values.
"""

from __future__ import annotations

import re
import logging
from dataclasses import dataclass, field
from typing import Any

from app.schemas.resume import ResumeExtraction

logger = logging.getLogger(__name__)


# ── Validation result ─────────────────────────────────────────────────────

@dataclass
class ValidationResult:
    """Result of deterministic validation."""
    data: dict[str, Any]
    is_valid: bool = True
    warnings: list[str] = field(default_factory=list)
    corrections: list[str] = field(default_factory=list)


# ── Validators ────────────────────────────────────────────────────────────

_EMAIL_RE = re.compile(r"^[\w.+-]+@[\w-]+\.[a-zA-Z]{2,}$")
_PHONE_RE = re.compile(r"[\d\s\-+().]{7,20}")
_URL_RE = re.compile(r"^https?://\S+$")


def _clean_string(value: str) -> str:
    """Normalize unicode characters in extracted text."""
    value = value.replace("\u2013", "-").replace("\u2014", "-")
    value = value.replace("\u2019", "'").replace("\u2018", "'")
    value = value.replace("\u201c", '"').replace("\u201d", '"')
    return value.strip()


def _description_to_list(description: str | list[str]) -> list[str]:
    """Convert description string to bullet-point list."""
    if isinstance(description, list):
        return [_clean_string(d) for d in description if d.strip()]
    parts = re.split(r"\n|•|\u2022", description)
    return [_clean_string(p) for p in parts if p.strip()]


def _validate_email(email: str) -> tuple[str, list[str]]:
    """Validate and clean email address."""
    warnings = []
    if not email:
        return "", warnings

    cleaned = re.sub(r"[#\s]+", "", email).strip()
    if not _EMAIL_RE.match(cleaned):
        warnings.append(f"Invalid email format: '{cleaned}'")
        return cleaned, warnings  # Keep it but warn

    return cleaned, warnings


def _validate_phone(phone: str) -> tuple[str, list[str]]:
    """Validate phone number format."""
    warnings = []
    if not phone:
        return "", warnings

    # Keep the phone as extracted if it has enough digits
    digits = re.sub(r"\D", "", phone)
    if len(digits) < 7:
        warnings.append(f"Phone number appears too short: '{phone}'")
    elif len(digits) > 15:
        warnings.append(f"Phone number appears too long: '{phone}'")

    return phone.strip(), warnings


def _validate_url(url: str, field_name: str) -> tuple[str, list[str]]:
    """Validate URL format."""
    warnings = []
    if not url:
        return "", warnings

    if not _URL_RE.match(url):
        # Try to fix common issues
        if url.startswith("www."):
            url = "https://" + url
        elif not url.startswith("http"):
            warnings.append(f"{field_name} URL is malformed: '{url}'")

    return url.strip(), warnings


def _clean_experience_entries(entries: list[dict]) -> tuple[list[dict], list[str]]:
    """Clean and validate experience entries."""
    corrections = []
    cleaned = []

    for i, entry in enumerate(entries):
        if not isinstance(entry, dict):
            corrections.append(f"Experience entry {i} is not a dict, skipped")
            continue

        for key, value in entry.items():
            if isinstance(value, str):
                entry[key] = _clean_string(value)

        if "description" in entry:
            entry["description"] = _description_to_list(entry["description"])

        # Ensure required fields exist
        entry.setdefault("title", "")
        entry.setdefault("company", "")
        entry.setdefault("duration", "")
        entry.setdefault("description", [])

        cleaned.append(entry)

    return cleaned, corrections


def _clean_education_entries(entries: list[dict]) -> tuple[list[dict], list[str]]:
    """Clean and validate education entries."""
    corrections = []
    cleaned = []

    for i, entry in enumerate(entries):
        if not isinstance(entry, dict):
            corrections.append(f"Education entry {i} is not a dict, skipped")
            continue

        for key, value in entry.items():
            if isinstance(value, str):
                entry[key] = _clean_string(value)

        entry.setdefault("degree", "")
        entry.setdefault("institution", "")
        entry.setdefault("duration", "")
        entry.setdefault("location", "")

        cleaned.append(entry)

    return cleaned, corrections


def _clean_project_entries(entries: list[dict]) -> tuple[list[dict], list[str]]:
    """Clean and validate project entries."""
    corrections = []
    cleaned = []

    for i, entry in enumerate(entries):
        if not isinstance(entry, dict):
            corrections.append(f"Project entry {i} is not a dict, skipped")
            continue

        for key, value in entry.items():
            if isinstance(value, str):
                entry[key] = _clean_string(value)

        if "description" in entry:
            entry["description"] = _description_to_list(entry["description"])

        entry.setdefault("name", "")
        entry.setdefault("tech", "")
        entry.setdefault("description", [])

        cleaned.append(entry)

    return cleaned, corrections


def _clean_list_entries(entries: list[dict], section_name: str) -> tuple[list[dict], list[str]]:
    """Generic cleaner for certification/publication entries."""
    corrections = []
    cleaned = []

    for i, entry in enumerate(entries):
        if not isinstance(entry, dict):
            if isinstance(entry, str):
                # Convert bare strings to simple dicts
                cleaned.append({"name": entry})
                corrections.append(f"{section_name} entry {i} was a string, converted to dict")
            else:
                corrections.append(f"{section_name} entry {i} is not a dict, skipped")
            continue

        for key, value in entry.items():
            if isinstance(value, str):
                entry[key] = _clean_string(value)

        cleaned.append(entry)

    return cleaned, corrections


# ── Main validation function ──────────────────────────────────────────────

def validate_extraction(extraction: ResumeExtraction) -> ValidationResult:
    """
    Validate and clean extracted resume data.

    Performs deterministic validation without LLM calls:
    - Email format validation
    - Phone number format checks
    - URL format checks
    - String normalization (unicode cleaning)
    - Description splitting into bullet points
    - Missing field defaults

    Args:
        extraction: LLM-extracted resume data.

    Returns:
        ValidationResult with cleaned data and any warnings/corrections.
    """
    data = extraction.to_api_dict()
    warnings: list[str] = []
    corrections: list[str] = []

    # Validate personal_info
    pi = data.get("personal_info", {})
    if isinstance(pi, dict):
        # Email
        if pi.get("email"):
            pi["email"], email_warns = _validate_email(pi["email"])
            warnings.extend(email_warns)

        # Phone
        if pi.get("phone"):
            pi["phone"], phone_warns = _validate_phone(pi["phone"])
            warnings.extend(phone_warns)

        # URLs
        for url_field in ("linkedin", "github"):
            if pi.get(url_field):
                pi[url_field], url_warns = _validate_url(pi[url_field], url_field)
                warnings.extend(url_warns)

        # Clean all string fields
        for key, value in pi.items():
            if isinstance(value, str):
                pi[key] = _clean_string(value)

        data["personal_info"] = pi

    # Validate skills (ensure list of strings)
    skills = data.get("skills", [])
    if isinstance(skills, list):
        data["skills"] = [
            _clean_string(s) for s in skills
            if isinstance(s, str) and s.strip()
        ]

    # Validate experience
    exp = data.get("experience", [])
    if isinstance(exp, list):
        data["experience"], exp_corrections = _clean_experience_entries(exp)
        corrections.extend(exp_corrections)

    # Validate education
    edu = data.get("education", [])
    if isinstance(edu, list):
        data["education"], edu_corrections = _clean_education_entries(edu)
        corrections.extend(edu_corrections)

    # Validate projects
    proj = data.get("projects", [])
    if isinstance(proj, list):
        data["projects"], proj_corrections = _clean_project_entries(proj)
        corrections.extend(proj_corrections)

    # Validate certifications
    certs = data.get("certifications", [])
    if isinstance(certs, list):
        data["certifications"], cert_corrections = _clean_list_entries(certs, "Certification")
        corrections.extend(cert_corrections)

    # Validate publications
    pubs = data.get("publications", [])
    if isinstance(pubs, list):
        data["publications"], pub_corrections = _clean_list_entries(pubs, "Publication")
        corrections.extend(pub_corrections)

    # Ensure interests and languages are lists of strings
    for list_field in ("interests", "languages"):
        items = data.get(list_field, [])
        if isinstance(items, list):
            data[list_field] = [
                _clean_string(s) if isinstance(s, str) else str(s)
                for s in items if s
            ]

    if corrections:
        logger.info(
            "resume_validator.corrections",
            extra={"corrections": corrections},
        )

    return ValidationResult(
        data=data,
        is_valid=True,
        warnings=warnings,
        corrections=corrections,
    )
