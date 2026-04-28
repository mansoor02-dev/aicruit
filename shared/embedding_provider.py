import os
import logging
from abc import ABC, abstractmethod
from typing import List

logger = logging.getLogger(__name__)


class EmbeddingProvider(ABC):
    DIMENSIONS = 768

    @abstractmethod
    def embed(self, texts: List[str]) -> List[List[float]]:
        """Embed a batch of texts. Returns list of 768-dim float vectors."""
        pass

    def embed_one(self, text: str) -> List[float]:
        """Convenience method for single text."""
        if not text or not text.strip():
            return [0.0] * self.DIMENSIONS
        return self.embed([text])[0]


class ONNXProvider(EmbeddingProvider):
    """
    Local ONNX inference via fastembed.
    Model: BAAI/bge-m3 — multilingual, 768-dim, MTEB top performer.
    RAM: ~90MB after load. No GPU needed. No internet after first download.
    First run downloads model (~570MB) to ~/.cache/fastembed/
    """
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        try:
            from fastembed import TextEmbedding
            logger.info("Loading bge-m3 ONNX model...")
            self.model = TextEmbedding("BAAI/bge-m3")
            self._initialized = True
            logger.info("bge-m3 loaded successfully")
        except ImportError:
            raise RuntimeError("fastembed not installed. Run: pip install fastembed")

    def embed(self, texts: List[str]) -> List[List[float]]:
        results = list(self.model.embed(texts))
        return [r.tolist() for r in results]

class GoogleProvider(EmbeddingProvider):
    """
    Google text-embedding-004 via API.
    Same 768-dim space. Use for SaaS production scale.
    Requires: GOOGLE_API_KEY env var
    Free tier: 1,500 req/min, no cost.
    """
    def __init__(self):
        try:
            import google.generativeai as genai
            api_key = os.getenv("GOOGLE_API_KEY")
            if not api_key:
                raise ValueError("GOOGLE_API_KEY env var not set")
            genai.configure(api_key=api_key)
            self.genai = genai
        except ImportError:
            raise RuntimeError("google-generativeai not installed. Run: pip install google-generativeai")

    def embed(self, texts: List[str]) -> List[List[float]]:
        result = self.genai.embed_content(
            model="models/text-embedding-004",
            content=texts,
            task_type="RETRIEVAL_DOCUMENT"
        )
        embeddings = result.get("embedding", [])
        if isinstance(embeddings[0], float):
            return [embeddings]
        return embeddings
    
_provider_instance: EmbeddingProvider = None

def get_provider() -> EmbeddingProvider:
    """
    Returns singleton embedding provider based on EMBEDDING_PROVIDER env var.
    Default: onnx
    Valid values: onnx, google
    """
    global _provider_instance
    if _provider_instance is not None:
        return _provider_instance

    provider_name = os.getenv("EMBEDDING_PROVIDER", "onnx").lower()
    logger.info(f"Initializing embedding provider: {provider_name}")

    if provider_name == "onnx":
        _provider_instance = ONNXProvider()
    elif provider_name == "google":
        _provider_instance = GoogleProvider()
    else:
        raise ValueError(f"Unknown EMBEDDING_PROVIDER: '{provider_name}'. Valid: onnx, ollama, google")

    return _provider_instance