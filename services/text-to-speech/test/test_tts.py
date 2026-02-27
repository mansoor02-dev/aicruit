"""
Unit tests – no real TTS calls made (all providers mocked).

Run:
  pytest tests/ -v
"""
import io
import struct
import wave
from unittest.mock import MagicMock, patch, PropertyMock

import pytest
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


# ── helpers ──────────────────────────────────────────────────────────────────

def _make_wav(sample_rate: int = 22050, duration_s: float = 0.1) -> bytes:
    """Return a minimal valid WAV byte blob."""
    n_frames = int(sample_rate * duration_s)
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(b"\x00\x00" * n_frames)
    return buf.getvalue()


# ── Domain ───────────────────────────────────────────────────────────────────

class TestSynthesisRequest:
    def test_valid_request(self):
        from domain.entities import SynthesisRequest
        req = SynthesisRequest(text="Hello world")
        assert req.language == "en"
        assert req.speaking_rate == 1.0

    def test_empty_text_raises(self):
        from domain.entities import SynthesisRequest
        with pytest.raises(ValueError, match="empty"):
            SynthesisRequest(text="   ")

    def test_invalid_rate_raises(self):
        from domain.entities import SynthesisRequest
        with pytest.raises(ValueError, match="speaking_rate"):
            SynthesisRequest(text="Hi", speaking_rate=5.0)

    def test_invalid_pitch_raises(self):
        from domain.entities import SynthesisRequest
        with pytest.raises(ValueError, match="pitch"):
            SynthesisRequest(text="Hi", pitch=99.0)

    def test_invalid_format_raises(self):
        from domain.entities import SynthesisRequest
        with pytest.raises(ValueError, match="output_format"):
            SynthesisRequest(text="Hi", output_format="ogg")


# ── Application ──────────────────────────────────────────────────────────────

class TestSynthesizeSpeechUseCase:
    def _mock_service(self, provider_name="mock", wav_bytes=None):
        svc = MagicMock()
        svc.provider_name = provider_name
        wav = wav_bytes or _make_wav()
        from domain.entities import SynthesisResponse
        svc.synthesize.return_value = SynthesisResponse(
            audio_bytes=wav, sample_rate=22050, duration=0.1, provider=provider_name
        )
        return svc

    def test_basic_synthesis(self):
        from domain.entities import SynthesisRequest
        from application.use_cases import SynthesizeSpeechUseCase
        svc = self._mock_service()
        uc = SynthesizeSpeechUseCase(svc)
        resp = uc.execute(SynthesisRequest(text="Hello"))
        assert resp.audio_bytes
        svc.synthesize.assert_called_once()

    def test_cache_hit_second_call(self):
        from domain.entities import SynthesisRequest
        from application.use_cases import SynthesizeSpeechUseCase, _CACHE
        svc = self._mock_service()
        uc = SynthesizeSpeechUseCase(svc)
        text = f"Cache test unique {id(svc)}"  # unique to avoid cross-test cache collision
        req = SynthesisRequest(text=text)
        uc.execute(req)
        resp2 = uc.execute(req)
        assert resp2.cached
        assert svc.synthesize.call_count == 1  # second call served from cache

    def test_fallback_on_primary_failure(self):
        from domain.entities import SynthesisRequest
        from application.use_cases import SynthesizeSpeechUseCase
        primary = MagicMock()
        primary.provider_name = "failing"
        primary.synthesize.side_effect = RuntimeError("API down")
        fallback = self._mock_service("fallback")
        uc = SynthesizeSpeechUseCase(primary, fallback=fallback)
        resp = uc.execute(SynthesisRequest(text=f"Fallback test {id(primary)}"))
        assert resp.provider == "fallback"

    def test_no_fallback_raises(self):
        from domain.entities import SynthesisRequest
        from application.use_cases import SynthesizeSpeechUseCase
        primary = MagicMock()
        primary.provider_name = "failing"
        primary.synthesize.side_effect = RuntimeError("gone")
        uc = SynthesizeSpeechUseCase(primary)
        with pytest.raises(RuntimeError):
            uc.execute(SynthesisRequest(text=f"no fallback {id(primary)}"))

    def test_chunking_long_text(self):
        from domain.entities import SynthesisRequest
        from application.use_cases import SynthesizeSpeechUseCase
        svc = self._mock_service()
        uc = SynthesizeSpeechUseCase(svc)
        # > 500 chars in multiple sentences
        long_text = "Hello world. " * 60
        uc.execute(SynthesisRequest(text=long_text))
        assert svc.synthesize.call_count > 1

    def test_text_too_long_raises(self):
        from domain.entities import SynthesisRequest
        from application.use_cases import SynthesizeSpeechUseCase
        svc = self._mock_service()
        uc = SynthesizeSpeechUseCase(svc)
        with pytest.raises(ValueError, match="50 000"):
            uc.execute(SynthesisRequest(text="x" * 50_001))


# ── Infrastructure – Factory ──────────────────────────────────────────────────

class TestTTSFactory:
    def test_unknown_provider_raises(self):
        from infrastructure.factory import TTSFactory
        with pytest.raises(ValueError, match="Unknown provider"):
            TTSFactory.create("banana")

    def test_create_api_returns_gtts_adapter(self):
        from infrastructure.factory import TTSFactory
        from infrastructure.api_tts import GTTSAdapter
        with patch.object(GTTSAdapter, "is_available", return_value=True):
            svc = TTSFactory.create("api")
        assert isinstance(svc, GTTSAdapter)

    def test_create_local_prefers_piper(self):
        from infrastructure.factory import TTSFactory
        from infrastructure.local_tts import PiperTTSAdapter
        with patch.object(PiperTTSAdapter, "is_available", return_value=True):
            svc = TTSFactory.create("local")
        assert isinstance(svc, PiperTTSAdapter)

    def test_create_local_falls_back_to_pyttsx3(self):
        from infrastructure.factory import TTSFactory
        from infrastructure.local_tts import PiperTTSAdapter, Pyttsx3Adapter
        with patch.object(PiperTTSAdapter, "is_available", return_value=False), \
             patch.object(Pyttsx3Adapter, "is_available", return_value=True):
            svc = TTSFactory.create("local")
        assert isinstance(svc, Pyttsx3Adapter)


# ── Infrastructure – GTTSAdapter ─────────────────────────────────────────────

class TestGTTSAdapter:
    def test_synthesize_returns_response(self):
        from infrastructure.api_tts import GTTSAdapter
        from domain.entities import SynthesisRequest

        adapter = GTTSAdapter()
        fake_mp3 = b"\xff\xe3" + b"\x00" * 100  # fake MP3 header

        with patch("infrastructure.api_tts.gTTS") as mock_gtts_cls, \
             patch.object(GTTSAdapter, "_mp3_to_wav", return_value=(_make_wav(), 22050, 0.1)):
            instance = mock_gtts_cls.return_value
            instance.write_to_fp = lambda buf: buf.write(fake_mp3)
            result = adapter.synthesize(SynthesisRequest(text="Hello"))

        assert result.provider == "gtts_api"
        assert result.audio_bytes

    def test_retry_on_failure(self):
        from infrastructure.api_tts import GTTSAdapter
        from domain.entities import SynthesisRequest

        adapter = GTTSAdapter()
        call_count = 0

        def flaky_write(buf):
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ConnectionError("temporary")
            buf.write(b"\x00" * 10)

        with patch("infrastructure.api_tts.gTTS") as mock_cls, \
             patch.object(GTTSAdapter, "_mp3_to_wav", return_value=(_make_wav(), 22050, 0.1)), \
             patch("time.sleep"):  # don't actually sleep
            mock_cls.return_value.write_to_fp = flaky_write
            result = adapter.synthesize(SynthesisRequest(text="Retry test"))

        assert call_count == 3


# ── REST API ─────────────────────────────────────────────────────────────────

class TestFastAPIEndpoints:
    @pytest.fixture
    def client(self):
        from fastapi.testclient import TestClient
        from interface.api import app
        return TestClient(app)

    def test_health_endpoint(self, client):
        resp = client.get("/health")
        assert resp.status_code == 200
        assert "providers" in resp.json()

    def test_providers_endpoint(self, client):
        resp = client.get("/providers")
        assert resp.status_code == 200
        ids = [p["id"] for p in resp.json()["providers"]]
        assert "api" in ids and "local" in ids

    def test_synthesize_returns_audio(self, client):
        from domain.entities import SynthesisResponse
        mock_resp = SynthesisResponse(
            audio_bytes=_make_wav(), sample_rate=22050, duration=0.1, provider="mock"
        )
        with patch("interface.api.TTSFactory") as mock_factory, \
             patch("interface.api.SynthesizeSpeechUseCase") as mock_uc_cls:
            mock_factory.create_with_fallback.return_value = (MagicMock(), None)
            mock_uc_cls.return_value.execute.return_value = mock_resp

            resp = client.post("/synthesize", json={"text": "Hello", "provider": "api"})

        assert resp.status_code == 200
        assert resp.headers["content-type"].startswith("audio/wav")

    def test_synthesize_empty_text_rejected(self, client):
        resp = client.post("/synthesize", json={"text": ""})
        assert resp.status_code == 422