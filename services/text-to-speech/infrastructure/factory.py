"""
Infrastructure – Factory + Dependency Injection.

Resolves provider type → concrete TTSService instance.
Supports automatic fallback chaining.
"""
import logging
import os
from pathlib import Path
from typing import Optional

from domain.interfaces import TTSService

logger = logging.getLogger(__name__)

ProviderType = str  # "api" | "local" | "auto"


class TTSFactory:
    """
    Creates TTSService instances by name.

    Provider resolution order for "auto":
      1. local (piper) if model files present
      2. local (pyttsx3) if pyttsx3 available
      3. api  (gTTS)    if network reachable
    """

    @staticmethod
    def create(provider_type: ProviderType = "auto") -> TTSService:
        provider_type = provider_type.lower().strip()

        if provider_type == "api":
            return TTSFactory._make_api()
        elif provider_type == "local":
            return TTSFactory._make_local()
        elif provider_type == "auto":
            return TTSFactory._auto()
        else:
            raise ValueError(f"Unknown provider type '{provider_type}'. Choose: api | local | auto")

    @staticmethod
    def _make_api() -> TTSService:
        from infrastructure.api_tts import GTTSAdapter
        adapter = GTTSAdapter()
        if not adapter.is_available():
            raise RuntimeError("gTTS API adapter unavailable (no network or gtts not installed).")
        logger.info("Selected provider: %s", adapter.provider_name)
        return adapter

    @staticmethod
    def _make_local() -> TTSService:
        # Try Piper first (better quality)
        from infrastructure.local_tts import PiperTTSAdapter, Pyttsx3Adapter

        piper = PiperTTSAdapter(
            model_dir=Path(os.getenv("PIPER_MODEL_PATH", str(PiperTTSAdapter._DEFAULT_MODEL_DIR)))
        )
        if piper.is_available():
            logger.info("Selected provider: piper_local")
            return piper

        logger.warning("piper-tts not installed; falling back to pyttsx3")
        p3 = Pyttsx3Adapter()
        if p3.is_available():
            logger.info("Selected provider: pyttsx3_local")
            return p3

        raise RuntimeError(
            "No local TTS provider available. "
            "Install one of: pip install piper-tts  OR  pip install pyttsx3"
        )

    @staticmethod
    def _auto() -> TTSService:
        try:
            return TTSFactory._make_local()
        except RuntimeError:
            pass
        try:
            return TTSFactory._make_api()
        except RuntimeError:
            pass
        raise RuntimeError("No TTS provider is available. Install pyttsx3 or gtts.")

    @staticmethod
    def create_with_fallback(
        primary: ProviderType = "api",
        fallback: ProviderType = "local",
    ) -> tuple[TTSService, Optional[TTSService]]:
        """Return (primary_service, fallback_service) for use with SynthesizeSpeechUseCase."""
        primary_svc = TTSFactory.create(primary)
        try:
            fallback_svc = TTSFactory.create(fallback)
        except RuntimeError as e:
            logger.warning("Fallback provider unavailable: %s", e)
            fallback_svc = None
        return primary_svc, fallback_svc