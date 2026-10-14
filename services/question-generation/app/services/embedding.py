import os
import time
from typing import Any, Dict, List, Optional

import numpy as np
from dotenv import load_dotenv

load_dotenv()

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
