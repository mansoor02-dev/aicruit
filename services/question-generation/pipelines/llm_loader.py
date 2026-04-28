import os
from typing import Any, Dict, List, Optional

from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()


class OpenRouterChat:
    """Wrapper for OpenRouter API (OpenAI-compatible)."""

    def __init__(self, model_name: str = "openai/gpt-oss-120b:free"):
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
            print(f"⚠️  OpenRouter failed ({e}), falling back to Gemini…")
            return GeminiChat().create_chat_completion(
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
            )


class GeminiChat:
    """Wrapper for Google Gemini API."""

    def __init__(self, model_name: str = "gemini-2.5-flash"):
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

        response = self.client.models.generate_content(
            model=self.model_name,
            contents=prompt,
            config={"temperature": temperature, "max_output_tokens": max_tokens, "top_p": 0.95},
        )
        text = getattr(response, "text", "") or ""

        return {"choices": [{"message": {"role": "assistant", "content": text.strip()}}]}


class LLMLoader:
    """Loads and caches an LLM callable (OpenRouter or Gemini)."""

    def __init__(self, model_type: str = "openrouter"):
        self.model_type = model_type
        self._llm: Optional[Any] = None

    def get_llm(self) -> Any:
        if self._llm is not None:
            return self._llm

        if self.model_type == "openrouter":
            self._llm = OpenRouterChat().create_chat_completion
        else:
            self._llm = GeminiChat().create_chat_completion

        return self._llm


# ---------------------------------------------------------------------------
# Embedder singleton — loads once, reuses forever within the process
# ---------------------------------------------------------------------------
from pathlib import Path

_EMBEDDER_CACHE_DIR = str(Path(__file__).resolve().parents[1] / "cache" / "models")
_embedder_instance = None


def get_embedder(model_name: str = "all-MiniLM-L6-v2"):
    """
    Return a cached SentenceTransformer instance.
    - First call: downloads (if needed) and loads the model (~2-3s).
    - Subsequent calls: returns instantly (same object).
    - Model files are stored in cache/models/ inside the project.
    """
    global _embedder_instance
    if _embedder_instance is not None:
        return _embedder_instance

    from sentence_transformers import SentenceTransformer

    Path(_EMBEDDER_CACHE_DIR).mkdir(parents=True, exist_ok=True)
    _embedder_instance = SentenceTransformer(
        model_name, device="cpu", cache_folder=_EMBEDDER_CACHE_DIR
    )
    _embedder_instance.max_seq_length = 128
    return _embedder_instance