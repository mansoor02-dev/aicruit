"""
Interface – FastAPI REST API (optional)

Start with:
  uvicorn interface.api:app --host 0.0.0.0 --port 8000

Endpoints:
  POST /synthesize   – returns WAV (or MP3) audio file
  GET  /health       – provider health check
  GET  /providers    – list available providers
"""
import io
import logging
from typing import Optional

logger = logging.getLogger(__name__)


def create_app():
    """Factory function so tests can create isolated instances."""
    from fastapi import FastAPI, HTTPException
    from fastapi.responses import StreamingResponse
    from pydantic import BaseModel, Field

    from domain.entities import SynthesisRequest
    from application.use_cases import SynthesizeSpeechUseCase
    from infrastructure.factory import TTSFactory

    app = FastAPI(
        title="TTS System",
        description="Production-grade Text-to-Speech REST API",
        version="1.0.0",
    )

    # ── Request / Response schemas ───────────────────────────────────────────
    class SynthesizeBody(BaseModel):
        text: str = Field(..., min_length=1, max_length=50_000)
        provider: str = Field("auto", pattern="^(api|local|auto)$")
        voice_id: str = "default"
        language: str = "en"
        speaking_rate: float = Field(1.0, ge=0.5, le=2.0)
        pitch: float = Field(0.0, ge=-10.0, le=10.0)
        output_format: str = Field("wav", pattern="^(wav|mp3)$")
        enable_fallback: bool = True

    # ── Routes ───────────────────────────────────────────────────────────────
    @app.post("/synthesize", summary="Convert text to speech")
    async def synthesize(body: SynthesizeBody):
        try:
            request = SynthesisRequest(
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
            response = use_case.execute(request)

            media_type = "audio/wav" if body.output_format == "wav" else "audio/mpeg"
            headers = {
                "X-Provider": response.provider,
                "X-Duration": str(round(response.duration, 3)),
                "X-Cached": str(response.cached).lower(),
                "Content-Disposition": f'attachment; filename="speech.{body.output_format}"',
            }

            return StreamingResponse(
                io.BytesIO(response.audio_bytes),
                media_type=media_type,
                headers=headers,
            )

        except ValueError as e:
            raise HTTPException(status_code=422, detail=str(e))
        except RuntimeError as e:
            raise HTTPException(status_code=503, detail=str(e))
        except Exception as e:
            logger.exception("Unexpected error during synthesis")
            raise HTTPException(status_code=500, detail="Internal synthesis error")

    @app.get("/health", summary="Health check")
    def health():
        from infrastructure.factory import TTSFactory
        results = {}
        for p in ("api", "local"):
            try:
                svc = TTSFactory.create(p)
                results[p] = {"available": svc.is_available(), "provider": svc.provider_name}
            except RuntimeError as e:
                results[p] = {"available": False, "error": str(e)}
        return {"status": "ok", "providers": results}

    @app.get("/providers", summary="List providers")
    def providers():
        return {
            "providers": [
                {"id": "api", "description": "Google Translate TTS (gTTS) – free, requires internet"},
                {"id": "local", "description": "Piper or pyttsx3 – fully offline CPU inference"},
                {"id": "auto", "description": "Auto-selects best available provider"},
            ]
        }

    return app


# Allow `uvicorn interface.api:app`
app = create_app()