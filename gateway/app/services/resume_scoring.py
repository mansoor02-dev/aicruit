import logging
import os
from typing import Optional
import httpx

logger = logging.getLogger(__name__)
RESUME_PARSER_URL = os.getenv("RESUME_PARSER_URL", "http://resume-parser:8006")


async def score_resume_for_job(resume: dict, job: dict) -> Optional[int]:
    """Call resume-parser /score-fit. Return overall (0-100) or None on any failure."""
    url = f"{RESUME_PARSER_URL}/score-fit"
    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            r = await client.post(url, json={"resume": resume, "job": job})
            r.raise_for_status()
            data = r.json()
            if not isinstance(data, dict) or "overall" not in data:
                logger.warning("resume_scoring.bad_shape", extra={"data": data})
                return None
            overall = max(0, min(100, int(data["overall"])))
            logger.info(
                "resume_scoring.success",
                extra={
                    "overall": overall,
                    "sub": {
                        k: data.get(k)
                        for k in (
                            "skills_match",
                            "experience_match",
                            "education_match",
                            "project_match",
                        )
                    },
                    "rationale": data.get("rationale"),
                },
            )
            return overall
    except (httpx.HTTPError, ValueError, KeyError, TypeError) as e:
        logger.warning("resume_scoring.failed", extra={"error": str(e)})
        return None
