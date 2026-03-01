"""
Interface – FastAPI REST API

Start with:
  uvicorn interface.api:app --host 0.0.0.0 --port 8000

Endpoints:
  POST /synthesize          – synthesize text, returns a download URL
  GET  /audio/<filename>    – download the generated audio file
  GET  /health              – provider health check
  GET  /providers           – list available providers

Flow:
  1. Backend POSTs text to /synthesize
  2. API returns { "url": "http://host/audio/abc123.wav", ... }
  3. Backend uses that URL however it needs (play, store, forward, etc.)
"""
import logging
import os
import uuid
from pathlib import Path

logger = logging.getLogger(__name__)

# ── Audio file storage ────────────────────────────────────────────────────────
AUDIO_DIR = Path(os.getenv("AUDIO_OUTPUT_DIR", "/tmp/tts_audio"))
AUDIO_DIR.mkdir(parents=True, exist_ok=True)


def create_app():
    from fastapi import FastAPI, HTTPException, Request
    from fastapi.responses import FileResponse
    from pydantic import BaseModel, Field

    from domain.entities import SynthesisRequest
    from application.use_cases import SynthesizeSpeechUseCase
    from infrastructure.factory import TTSFactory

    app = FastAPI(
        title="TTS System",
        description="Text-to-Speech API – returns a download URL for generated audio",
        version="2.0.0",
    )

    # ── Request schema ────────────────────────────────────────────────────────
    class SynthesizeBody(BaseModel):
        text: str = Field(..., min_length=1, max_length=50_000)
        provider: str = Field("auto", pattern="^(api|local|auto)$")
        voice_id: str = "default"
        language: str = "en"
        speaking_rate: float = Field(0.75, ge=0.5, le=2.0)  # 0.75 = natural question pace
        pitch: float = Field(0.0, ge=-10.0, le=10.0)
        output_format: str = Field("wav", pattern="^(wav|mp3)$")
        enable_fallback: bool = True

    # ── POST /synthesize ──────────────────────────────────────────────────────
    @app.post("/synthesize", summary="Convert text to speech, get back a download URL")
    async def synthesize(body: SynthesizeBody, request: Request):
        try:
            tts_request = SynthesisRequest(
                text=body.text,
                voice_id=body.voice_id,
                language=body.language,
                speaking_rate=body.speaking_rate,
                pitch=body.pitch,
                output_format=body.output_format,
            )

            if body.enable_fallback:
                other = "local" if body.provider == "api" else "api"
                primary_svc, fallback_svc = TTSFactory.create_with_fallback(body.provider, other)
            else:
                primary_svc = TTSFactory.create(body.provider)
                fallback_svc = None

            use_case = SynthesizeSpeechUseCase(primary_svc, fallback=fallback_svc)
            response = use_case.execute(tts_request)

            # Save audio to disk and return a URL
            filename = f"{uuid.uuid4().hex}.{body.output_format}"
            file_path = AUDIO_DIR / filename
            file_path.write_bytes(response.audio_bytes)

            base_url = str(request.base_url).rstrip("/")
            download_url = f"{base_url}/audio/{filename}"

            return {
                "url": download_url,
                "filename": filename,
                "format": body.output_format,
                "duration": round(response.duration, 3),
                "provider": response.provider,
                "cached": response.cached,
                "speaking_rate": body.speaking_rate,
            }

        except ValueError as e:
            raise HTTPException(status_code=422, detail=str(e))
        except RuntimeError as e:
            raise HTTPException(status_code=503, detail=str(e))
        except Exception:
            logger.exception("Unexpected error during synthesis")
            raise HTTPException(status_code=500, detail="Internal synthesis error")

    # ── GET /audio/<filename> ─────────────────────────────────────────────────
    @app.get("/audio/{filename}", summary="Download generated audio file")
    async def download_audio(filename: str):
        if "/" in filename or ".." in filename:
            raise HTTPException(status_code=400, detail="Invalid filename")

        file_path = AUDIO_DIR / filename
        if not file_path.exists():
            raise HTTPException(status_code=404, detail="Audio file not found")

        media_type = "audio/wav" if filename.endswith(".wav") else "audio/mpeg"
        return FileResponse(path=str(file_path), media_type=media_type, filename=filename)

    # ── GET /health ───────────────────────────────────────────────────────────
    @app.get("/health", summary="Health check")
    def health():
        results = {}
        for p in ("api", "local"):
            try:
                svc = TTSFactory.create(p)
                results[p] = {"available": svc.is_available(), "provider": svc.provider_name}
            except RuntimeError as e:
                results[p] = {"available": False, "error": str(e)}
        return {"status": "ok", "providers": results}

    # ── GET /providers ────────────────────────────────────────────────────────
    @app.get("/providers", summary="List available providers")
    def providers():
        return {
            "providers": [
                {"id": "api",   "description": "Google Translate TTS (gTTS) – free, requires internet"},
                {"id": "local", "description": "Piper or pyttsx3 – fully offline CPU inference"},
                {"id": "auto",  "description": "Auto-selects best available provider"},
            ]
        }

    return app


app = create_app()