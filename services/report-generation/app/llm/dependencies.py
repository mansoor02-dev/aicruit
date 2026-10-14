"""FastAPI dependencies for shared LLM client lifecycle."""

from functools import lru_cache

from .client import LLMClient


@lru_cache(maxsize=1)
def get_llm_client() -> LLMClient:
    """Return one configured client per worker process."""
    return LLMClient()
