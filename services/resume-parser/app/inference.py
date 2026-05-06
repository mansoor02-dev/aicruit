from google import genai
import os
from dotenv import load_dotenv
load_dotenv()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL = "gemini-2.5-flash"

SYSTEM_PROMPT = """You are a resume parser. Extract information from the resume text and return a JSON object.
You MUST fill in all fields you find. Do not return empty fields if the information exists in the resume.

Return this exact JSON structure filled with data from the resume:
{
  "personal_info": {"name": "...", "email": "...", "phone": "...", "linkedin": "...", "github": "...", "location": "..."},
  "skills": ["skill1", "skill2"],
  "experience": [{"title": "...", "company": "...", "duration": "...", "description": "..."}],
  "education": [{"degree": "...", "institution": "...", "duration": "...", "location": "..."}],
  "projects": [{"name": "...", "tech": "...", "description": "..."}],
  "certifications": [],
  "publications": [],
  "interests": [],
  "languages": []
}"""

_gemini_client = None


def _get_gemini_client():
    global _gemini_client
    if _gemini_client is None:
        if not GEMINI_API_KEY:
            raise ValueError("GEMINI_API_KEY not set in environment.")
        _gemini_client = genai.Client(api_key=GEMINI_API_KEY)
    return _gemini_client


def _run_gemini(text: str) -> str:
    client = _get_gemini_client()
    response = client.models.generate_content(
        model=GEMINI_MODEL,
        contents=f"Parse this resume and return filled JSON:\n\n{text}",
        config={
            "system_instruction": SYSTEM_PROMPT,
            "response_mime_type": "application/json",
            "temperature": 0.1
        }
    )
    return response.text.strip()


def run_inference(text: str) -> str:
    return _run_gemini(text)


def run_score_inference(system_prompt: str, user_payload: str) -> dict:
    """Call Gemini 2.5 Flash with a custom system prompt and JSON-mode user payload.
    Returns the parsed JSON dict. Raises on transport / JSON errors.
    """
    import json as _json
    client = _get_gemini_client()
    response = client.models.generate_content(
        model=GEMINI_MODEL,
        contents=user_payload,
        config={
            "system_instruction": system_prompt,
            "response_mime_type": "application/json",
            "temperature": 0.1,
        },
    )
    return _json.loads(response.text)