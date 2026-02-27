"""
Infrastructure – API-based TTS adapter.

Uses gTTS (Google Translate TTS) – completely free, no API key required.
Falls back gracefully when offline or rate-limited.
"""
import io
import logging
import time
from functools import wraps
from typing import Callable

from domain.entities import SynthesisRequest, SynthesisResponse
from domain.interfaces import TTSService

logger = logging.getLogger(__name__)


# ── retry decorator ──────────────────────────────────────────────────────────
def _retry(max_attempts: int = 3, backoff: float = 1.5):
    def decorator(fn: Callable):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            delay = 1.0
            for attempt in range(1, max_attempts + 1):
                try:
                    return fn(*args, **kwargs)
                except Exception as exc:
                    if attempt == max_attempts:
                        raise
                    logger.warning("Attempt %d failed (%s). Retrying in %.1fs…", attempt, exc, delay)
                    time.sleep(delay)
                    delay *= backoff
        return wrapper
    return decorator


class GTTSAdapter(TTSService):
    """
    Free TTS via Google Translate (gTTS).

    - No API key needed.
    - Output is MP3 from the API; we convert to WAV in memory using pydub / wave.
    - Rate: ~80 req/min is safe; we add a tiny sleep to be polite.
    """

    # Map generic language codes to gTTS-compatible ones
    _LANG_MAP: dict[str, str] = {
        "en": "en",
        "fr": "fr",
        "de": "de",
        "es": "es",
        "it": "it",
        "pt": "pt",
        "nl": "nl",
        "ru": "ru",
        "ja": "ja",
        "zh": "zh",
        "ar": "ar",
        "hi": "hi",
    }

    def __init__(self, slow: bool = False, timeout: float = 10.0):
        self._slow = slow
        self._timeout = timeout

    @property
    def provider_name(self) -> str:
        return "gtts_api"

    def is_available(self) -> bool:
        try:
            import gtts  # noqa
            import socket
            socket.setdefaulttimeout(3)
            socket.socket(socket.AF_INET, socket.SOCK_STREAM).connect(("8.8.8.8", 53))
            return True
        except Exception:
            return False

    @_retry(max_attempts=3, backoff=1.5)
    def synthesize(self, request: SynthesisRequest) -> SynthesisResponse:
        from gtts import gTTS

        lang = self._LANG_MAP.get(request.language, request.language)
        mp3_buf = io.BytesIO()

        tts = gTTS(text=request.text, lang=lang, slow=self._slow)
        tts.write_to_fp(mp3_buf)
        mp3_buf.seek(0)

        audio_bytes, sample_rate, duration = self._mp3_to_wav(mp3_buf.read(), request.speaking_rate)

        return SynthesisResponse(
            audio_bytes=audio_bytes,
            sample_rate=sample_rate,
            duration=duration,
            provider=self.provider_name,
        )

    @staticmethod
    def _mp3_to_wav(mp3_bytes: bytes, speed: float) -> tuple[bytes, int, float]:
        """Convert MP3 bytes → WAV bytes, optionally adjusting speed."""
        try:
            from pydub import AudioSegment
            seg = AudioSegment.from_mp3(io.BytesIO(mp3_bytes))
            if speed != 1.0:
                # Simple speed adjustment by resampling
                new_frame_rate = int(seg.frame_rate * speed)
                seg = seg._spawn(seg.raw_data, overrides={"frame_rate": new_frame_rate})
                seg = seg.set_frame_rate(22050)
            wav_buf = io.BytesIO()
            seg.export(wav_buf, format="wav")
            duration = len(seg) / 1000.0
            return wav_buf.getvalue(), seg.frame_rate, duration
        except ImportError:
            # pydub not available – return raw MP3 wrapped as-is
            # (caller should handle mp3 output format)
            logger.warning("pydub not installed; returning raw MP3 bytes as audio_bytes")
            return mp3_bytes, 22050, 0.0