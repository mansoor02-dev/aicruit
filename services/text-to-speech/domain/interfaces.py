"""Domain interfaces - abstract contracts only."""
from abc import ABC, abstractmethod
from .entities import SynthesisRequest, SynthesisResponse


class TTSService(ABC):
    """Port that every TTS backend must implement."""

    @abstractmethod
    def synthesize(self, request: SynthesisRequest) -> SynthesisResponse:
        ...

    @abstractmethod
    def is_available(self) -> bool:
        """Health-check without raising."""
        ...

    @property
    @abstractmethod
    def provider_name(self) -> str:
        ...