import os
import time
from typing import Any, Dict, List, Optional

import numpy as np
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
            print(f"OpenRouter failed ({e}), falling back to Gemini...")
            return GeminiChat().create_chat_completion(
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
            )


class GeminiChat:
    """Wrapper for Google Gemini API."""

    def __init__(self, model_name: Optional[str] = None):
        model_name = model_name or os.getenv("GEMINI_CHAT_MODEL", "gemini-2.5-flash")
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


def get_default_chat() -> Any:
    """
    Return a default chat client. Prefers Gemini when GEMINI_API_KEY is set,
    otherwise falls back to OpenRouter.
    """
    if os.getenv("GEMINI_API_KEY"):
        return GeminiChat()
    return OpenRouterChat()


class LLMLoader:
    """Loads and caches an LLM callable (Gemini by default, OpenRouter fallback)."""

    def __init__(self, model_type: str = "gemini"):
        self.model_type = model_type
        self._llm: Optional[Any] = None

    def get_llm(self) -> Any:
        if self._llm is not None:
            return self._llm

        # Prefer Gemini when key is available, regardless of requested type,
        # falling back to OpenRouter only when Gemini is unconfigured.
        if os.getenv("GEMINI_API_KEY"):
            self._llm = GeminiChat().create_chat_completion
        else:
            self._llm = OpenRouterChat().create_chat_completion

        return self._llm


# ---------------------------------------------------------------------------
# Embedder singleton  Gemini API embeddings (gemini-embedding-001)
# ---------------------------------------------------------------------------

class GeminiEmbedder:
    """
    Drop-in replacement for the previous SentenceTransformer embedder.

    Uses Google's Gemini embedding API (`gemini-embedding-001`).
    The API L2-normalizes embeddings by default, so `normalize_embeddings`
    kwarg is accepted but ignored (already normalized).
    """

    def __init__(
        self,
        model_name: Optional[str] = None,
        dim: Optional[int] = None,
    ):
        self.model_name = model_name or os.getenv("EMBEDDING_MODEL", "gemini-embedding-001")
        self.dim = int(dim or os.getenv("EMBEDDING_DIMS", "768"))

        api_key = os.environ.get("GEMINI_API_KEY")
        if not api_key:
            raise ValueError("GEMINI_API_KEY environment variable not set")

        try:
            from google import genai
        except ImportError:
            raise ImportError(
                "google-genai package not installed. Run: pip install 'google-genai>=0.3.0'"
            )

        self.client = genai.Client(api_key=api_key)

    def encode(
        self,
        texts: List[str],
        batch_size: int = 100,
        **_kwargs: Any,
    ) -> np.ndarray:
        """
        Embed a list of texts. Returns np.ndarray of shape (N, dim).

        Accepts `normalize_embeddings` and `convert_to_numpy` kwargs for
        SentenceTransformer compatibility (both effectively always true here).
        """
        if isinstance(texts, str):
            texts = [texts]
        if not texts:
            return np.zeros((0, self.dim), dtype=np.float32)

        all_embeddings: List[List[float]] = []

        for start in range(0, len(texts), batch_size):
            batch = texts[start:start + batch_size]

            last_err: Optional[Exception] = None
            for attempt in range(3):
                try:
                    resp = self.client.models.embed_content(
                        model=self.model_name,
                        contents=batch,
                        config={"output_dimensionality": self.dim},
                    )
                    for emb in resp.embeddings:
                        values = getattr(emb, "values", None) or getattr(emb, "value", None) or emb
                        all_embeddings.append(list(values))
                    break
                except Exception as e:
                    last_err = e
                    if attempt < 2:
                        time.sleep(2 ** attempt)  # 1s, 2s, 4s
                    else:
                        raise RuntimeError(
                            f"Gemini embed_content failed after 3 attempts: {last_err}"
                        ) from last_err

        return np.asarray(all_embeddings, dtype=np.float32)


_embedder_instance: Optional[GeminiEmbedder] = None


def get_embedder() -> GeminiEmbedder:
    """Return a cached GeminiEmbedder singleton."""
    global _embedder_instance
    if _embedder_instance is None:
        _embedder_instance = GeminiEmbedder()
    return _embedder_instance
