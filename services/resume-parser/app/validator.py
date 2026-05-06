import json
import re
from typing import Any
from pydantic import BaseModel


class ResumeSchema(BaseModel):
    personal_info: dict[str, Any] = {}
    skills: list[Any] = []
    experience: list[Any] = []
    education: list[Any] = []
    projects: list[Any] = []
    certifications: list[Any] = []
    publications: list[Any] = []
    interests: list[Any] = []
    languages: list[Any] = []


def _extract_json(raw: str) -> str:
    match = re.search(r'\{.*\}', raw, re.DOTALL)
    if match:
        return match.group()
    raise ValueError("No JSON found in model output")


def _clean_email(email: str) -> str:
    return re.sub(r'[#\s]+', '', email).strip()


def _clean_string(value: str) -> str:
    value = value.replace("\u2013", "-").replace("\u2014", "-")
    value = value.replace("\u2019", "'").replace("\u2018", "'")
    value = value.replace("\u201c", '"').replace("\u201d", '"')
    return value.strip()


def _description_to_list(description: str) -> list[str]:
    parts = re.split(r'\n|•|\u2022', description)
    return [p.strip() for p in parts if p.strip()]


def _clean_entries(entries: list) -> list:
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        for key, value in entry.items():
            if isinstance(value, str):
                entry[key] = _clean_string(value)
        if "description" in entry and isinstance(entry["description"], str):
            entry["description"] = _description_to_list(entry["description"])
    return entries


def validate(raw_json: str) -> dict:
    cleaned = _extract_json(raw_json)
    data = json.loads(cleaned)

    if data.get("personal_info", {}).get("email"):
        data["personal_info"]["email"] = _clean_email(data["personal_info"]["email"])

    if data.get("education"):
        for entry in data["education"]:
            if isinstance(entry, dict) and "degree" in entry:
                entry["degree"] = _clean_string(entry["degree"])

    for key in ("experience", "education", "projects", "certifications", "publications"):
        if isinstance(data.get(key), list):
            data[key] = _clean_entries(data[key])

    resume = ResumeSchema(**{k: v for k, v in data.items() if v is not None})
    return resume.model_dump()