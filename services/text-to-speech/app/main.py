"""
TTS Microservice — FastAPI entry point.
"""

import asyncio
from pathlib import Path
from functools import partial

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse

from . import gtts_engine
from . import pipertts_engine
from .schemas import TTSRequest, TTSResponse

# ── Config ───────────────────────────────────────────────────────────────────

AUDIO_DIR = Path("audio_files")
AUDIO_DIR.mkdir(exist_ok=True)

MEDIA_TYPES = {
    ".mp3": "audio/mpeg",
    ".wav": "audio/wav",
}

# ── App ──────────────────────────────────────────────────────────────────────

app = FastAPI(
    title="TTS Microservice",
    description="Convert text to speech using gTTS (MP3) or PiperTTS (WAV).",
    version="2.0.0",
)

# ── Routes ───────────────────────────────────────────────────────────────────

@app.post("/synthesize", response_model=TTSResponse, summary="Convert text to speech")
async def synthesize(request: TTSRequest):
    """
    Synthesize text and return a download URL for the audio file.
    Choose `engine: "gtts"` or `engine: "piper"` and fill in the matching options block.
    """
    loop = asyncio.get_event_loop()

    try:
        if request.engine == "gtts":
            opts = request.gtts or {}
            fn = partial(
                gtts_engine.synthesize,
                text=request.text,
                output_dir=AUDIO_DIR,
                **opts.model_dump(),
            )
            fmt = "mp3"

        else:  # piper
            opts = request.piper or {}
            fn = partial(
                pipertts_engine.synthesize,
                text=request.text,
                output_dir=AUDIO_DIR,
                **opts.model_dump(),
            )
            fmt = "wav"

        # Run blocking I/O in a thread so the event loop stays free
        file_id, _ = await loop.run_in_executor(None, fn)

    except FileNotFoundError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Synthesis failed: {e}")

    filename = f"{file_id}.{fmt}"
    return TTSResponse(
        file_id=file_id,
        download_url=f"/download/{filename}",
        engine=request.engine,
        format=fmt,
    )


@app.get("/download/{filename}", summary="Download generated audio file")
async def download(filename: str):
    """Stream a previously generated audio file."""
    file_path = AUDIO_DIR / filename

    if not file_path.exists():
        raise HTTPException(status_code=404, detail="File not found or has been removed.")

    media_type = MEDIA_TYPES.get(file_path.suffix.lower(), "application/octet-stream")
    return FileResponse(path=str(file_path), media_type=media_type, filename=filename)


@app.get("/health", summary="Health check", include_in_schema=False)
async def health():
    return {"status": "ok"}