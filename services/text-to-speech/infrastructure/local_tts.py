"""
Infrastructure – Local CPU-based TTS adapter.

Strategy (best CPU quality/speed tradeoff):
  1. piper-tts   – ONNX-based, ~50 ms/sentence on CPU, very natural voices
  2. pyttsx3     – pure CPU, system TTS, always available as last resort

Why Piper?
  • ONNX Runtime inference → fast on CPU (no PyTorch needed at runtime)
  • Pre-trained neural acoustic models (VITS-based)
  • ~20-50 ms synthesis for typical sentences on a 4-core CPU
  • No GPU, no CUDA
  • Models downloadable once, cached locally
  • Multiple languages/voices

Why pyttsx3 as fallback?
  • Zero-download, uses OS speech engine (espeak on Linux, SAPI on Windows)
  • Deterministic latency, acceptable quality for quick prototypes
"""
import io
import logging
import os
import threading
import wave
from pathlib import Path
from typing import Optional

from domain.entities import SynthesisRequest, SynthesisResponse
from domain.interfaces import TTSService

logger = logging.getLogger(__name__)

# ── Piper adapter ─────────────────────────────────────────────────────────────

class PiperTTSAdapter(TTSService):
    """
    Uses piper-tts (pip install piper-tts) with ONNX models.

    Model discovery order:
      1. $PIPER_MODEL_PATH env var
      2. ~/.local/share/piper/models/
      3. ./models/

    If no model found → raises RuntimeError (factory will fall back to pyttsx3).
    """

    _DEFAULT_MODEL_DIR = Path.home() / ".local" / "share" / "piper" / "models"
    _lock = threading.Lock()
    _voice_cache: dict[str, object] = {}  # voice_id → piper.PiperVoice

    def __init__(self, model_dir: Optional[Path] = None, default_voice: str = "en_US-lessac-medium"):
        self._model_dir = model_dir or Path(
            os.getenv("PIPER_MODEL_PATH", str(self._DEFAULT_MODEL_DIR))
        )
        self._default_voice = default_voice
        self._model_dir.mkdir(parents=True, exist_ok=True)

    @property
    def provider_name(self) -> str:
        return "piper_local"

    def is_available(self) -> bool:
        try:
            import piper  # noqa
            return True
        except ImportError:
            return False

    def _load_voice(self, voice_id: str):
        """Singleton load per voice – thread-safe."""
        with self._lock:
            if voice_id not in self._voice_cache:
                from piper import PiperVoice
                model_path = self._model_dir / f"{voice_id}.onnx"
                if not model_path.exists():
                    raise RuntimeError(
                        f"Piper model not found: {model_path}. "
                        f"Download with: python -m piper.download {voice_id}"
                    )
                logger.info("Loading Piper voice %s (first call – will warm up)", voice_id)
                self._voice_cache[voice_id] = PiperVoice.load(str(model_path))
                logger.info("Piper voice %s loaded and ready", voice_id)
        return self._voice_cache[voice_id]

    def synthesize(self, request: SynthesisRequest) -> SynthesisResponse:
        voice_id = request.voice_id if request.voice_id != "default" else self._default_voice
        voice = self._load_voice(voice_id)

        buf = io.BytesIO()
        with wave.open(buf, "wb") as wf:
            voice.synthesize(request.text, wf, length_scale=1.0 / request.speaking_rate)

        buf.seek(0)
        with wave.open(buf) as wf:
            sample_rate = wf.getframerate()
            n_frames = wf.getnframes()
            duration = n_frames / sample_rate

        return SynthesisResponse(
            audio_bytes=buf.getvalue(),
            sample_rate=sample_rate,
            duration=duration,
            provider=self.provider_name,
        )


# ── pyttsx3 adapter ───────────────────────────────────────────────────────────

class Pyttsx3Adapter(TTSService):
    """
    System TTS via pyttsx3.  Always available; quality depends on OS engine.
    Linux: espeak-ng.  macOS: NSSpeechSynthesizer.  Windows: SAPI5.

    Thread-safety: pyttsx3 is NOT thread-safe; we serialise with a lock.
    """
    _lock = threading.Lock()
    _engine = None  # lazy singleton

    @property
    def provider_name(self) -> str:
        return "pyttsx3_local"

    def is_available(self) -> bool:
        try:
            import pyttsx3  # noqa
            return True
        except ImportError:
            return False

    def _get_engine(self):
        with self._lock:
            if self._engine is None:
                import pyttsx3
                self._engine = pyttsx3.init()
            return self._engine

    def synthesize(self, request: SynthesisRequest) -> SynthesisResponse:
        import tempfile, os
        engine = self._get_engine()
        with self._lock:
            # Apply rate (words per minute; default ~200)
            base_rate = 200
            engine.setProperty("rate", int(base_rate * request.speaking_rate))

            # Voice selection
            voices = engine.getProperty("voices")
            voice = self._pick_voice(voices, request.language, request.voice_id)
            if voice:
                engine.setProperty("voice", voice.id)

            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
                tmp_path = tmp.name

            try:
                engine.save_to_file(request.text, tmp_path)
                engine.runAndWait()
                with open(tmp_path, "rb") as f:
                    audio_bytes = f.read()
            finally:
                os.unlink(tmp_path)

        # Parse WAV header for metadata
        try:
            with wave.open(io.BytesIO(audio_bytes)) as wf:
                sample_rate = wf.getframerate()
                duration = wf.getnframes() / sample_rate
        except Exception:
            sample_rate, duration = 22050, 0.0

        return SynthesisResponse(
            audio_bytes=audio_bytes,
            sample_rate=sample_rate,
            duration=duration,
            provider=self.provider_name,
        )

    @staticmethod
    def _pick_voice(voices, language: str, voice_id: str):
        if not voices:
            return None
        lang_lower = language.lower()
        for v in voices:
            if voice_id not in ("default",) and voice_id.lower() in (v.id or "").lower():
                return v
        for v in voices:
            if lang_lower in (v.id or "").lower() or lang_lower in (v.name or "").lower():
                return v
        return voices[0]