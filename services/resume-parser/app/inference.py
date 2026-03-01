from llama_cpp import Llama
from google import genai
import os
from dotenv import load_dotenv
load_dotenv() 

MODEL_PATH = os.getenv("MODEL_PATH", "models/qwen2.5-1.5b-instruct-q4_k_m.gguf")
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

_llm = None
_gemini_client = None


def _get_local_model() -> Llama:
    global _llm
    if _llm is None:
        _llm = Llama(
            model_path=MODEL_PATH,
            n_ctx=4096,
            n_threads=6,
            n_gpu_layers=0,
            use_mmap=True,
            verbose=False,
            chat_format="chatml"
        )
    return _llm


def _get_gemini_client():
    global _gemini_client
    if _gemini_client is None:
        if not GEMINI_API_KEY:
            raise ValueError("GEMINI_API_KEY not set in environment.")
        _gemini_client = genai.Client(api_key=GEMINI_API_KEY)
    return _gemini_client


def _run_local(text: str) -> str:
    llm = _get_local_model()
    response = llm.create_chat_completion(
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": f"Parse this resume and return filled JSON:\n\n{text}"}
        ],
        max_tokens=1500,
        temperature=0.1,
        response_format={"type": "json_object"}
    )
    return response["choices"][0]["message"]["content"].strip()


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


def run_inference(text: str, backend: str | None = "gemini") -> str:
    if backend == "local":
        return _run_local(text)
    return _run_gemini(text)