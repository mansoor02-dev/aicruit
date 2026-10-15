"""Lazy Gemini embeddings via ``GoogleGenerativeAIEmbeddings``.

Embeddings are only needed by the heuristic evaluation fallback, so the
client is built lazily on first use and a missing ``GEMINI_API_KEY`` is
tolerated (``get()`` returns ``None``). In that case the heuristic drops the
semantic term and renormalises the remaining weights. No network call is
made at startup, so OpenRouter-only deployments start cleanly.
"""

from __future__ import annotations

import logging
import math

from langchain_google_genai import GoogleGenerativeAIEmbeddings

from app.config import Settings

logger = logging.getLogger(__name__)


def _cosine(first: list[float], second: list[float]) -> float:
    dot = sum(a * b for a, b in zip(first, second))
    norm = math.sqrt(sum(a * a for a in first)) * math.sqrt(
        sum(b * b for b in second)
    )
    if norm <= 0:
        return 0.0
    return max(0.0, min(1.0, dot / norm))


class EmbeddingProvider:
    """Owns one lazily-created embeddings client (no module-level state)."""

    def __init__(self, settings: Settings):
        self._settings = settings
        self._embedder: GoogleGenerativeAIEmbeddings | None = None
        self._initialised = False

    def get(self) -> GoogleGenerativeAIEmbeddings | None:
        """Return the embeddings client, building it once on first use."""
        if not self._initialised:
            self._initialised = True
            if self._settings.gemini_api_key:
                self._embedder = GoogleGenerativeAIEmbeddings(
                    model=self._settings.embedding_model,
                    google_api_key=self._settings.gemini_api_key,
                    output_dimensionality=self._settings.embedding_dims,
                )
            else:
                logger.info(
                    "GEMINI_API_KEY is not set; embeddings are unavailable "
                    "and heuristic scoring will skip the semantic term"
                )
        return self._embedder

    async def similarity(self, first: str, second: str) -> float:
        """Cosine similarity of two texts via ``aembed_documents`` (async).

        Raises when embeddings are unavailable or the call fails; callers
        map failures to the neutral 0.5 score.
        """
        embedder = self.get()
        if embedder is None:
            raise RuntimeError(
                "Embeddings are not configured (missing GEMINI_API_KEY)"
            )
        vectors = await embedder.aembed_documents([first, second])
        return _cosine(vectors[0], vectors[1])
