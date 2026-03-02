"""
Candidate feedback generation logic — uses LLM for personalised feedback.
"""

from typing import Any, List

from .models import ScoredEntry, CandidateReport
from .llm_loader import call_llm_json


_CANDIDATE_PROMPT = """You are a friendly career coach giving feedback to an interview candidate.

Below is the candidate's interview performance (score is out of 10):

{entries_text}

Based on the remarks and scores, generate personalised feedback.

Rules:
- Strengths: 2-3 specific, encouraging sentences about what they did well.
- Improvements: 2-3 polite, constructive suggestions for areas to work on.
- Do NOT include any numeric scores in the feedback.
- Tone must be warm and motivating.

Return JSON only:
{{
  "strengths": ["...", "..."],
  "improvements": ["...", "..."]
}}

JSON:"""


def _format_entries(entries: List[ScoredEntry]) -> str:
    lines = []
    for e in entries:
        lines.append(f"- [{e.category}] Q: {e.q[:80]}  |  Remark: {e.remark[:120]}")
    return "\n".join(lines)


def _parse_string_list(raw: Any) -> List[str]:
    """Safely coerce the LLM output into a list of strings."""
    if isinstance(raw, list):
        return [str(item).strip() for item in raw if str(item).strip()]
    return []


def build_candidate_report(llm: Any, entries: List[ScoredEntry]) -> CandidateReport:
    """Ask the LLM for personalised candidate feedback."""
    prompt = _CANDIDATE_PROMPT.format(entries_text=_format_entries(entries))
    result = call_llm_json(llm, prompt, max_tokens=400)

    if result:
        strengths = _parse_string_list(result.get("strengths", []))
        improvements = _parse_string_list(result.get("improvements", []))
        if strengths and improvements:
            return CandidateReport(strengths=strengths[:3], improvements=improvements[:3])

    # Fallback: derive basic feedback from remarks
    strengths: List[str] = []
    improvements: List[str] = []
    for e in entries:
        if e.score >= 7.0:
            strengths.append(f"Well done on {e.category} — your response showed solid understanding.")
        elif e.score < 5.0:
            improvements.append(f"Consider deepening your knowledge of {e.category} for stronger answers.")

    if not strengths:
        strengths.append("You showed willingness to attempt all questions, which is a positive sign.")
    if not improvements:
        improvements.append("Keep practising a wide range of topics to sharpen your interview skills.")

    return CandidateReport(strengths=strengths[:3], improvements=improvements[:3])
