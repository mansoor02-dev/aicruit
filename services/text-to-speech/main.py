import os
import uuid
import wave
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

# We use the piper TTS library directly
from piper import PiperVoice, SynthesisConfig

app = FastAPI(title="Simplified TTS API")

# Audio file storage
AUDIO_DIR = Path(os.getenv("AUDIO_OUTPUT_DIR", "/tmp/tts_audio"))
AUDIO_DIR.mkdir(parents=True, exist_ok=True)

# Path to the Piper model
MODEL_PATH = "models/en_GB-alba-medium.onnx"

# We load the voice once at startup
voice = None
syn_config = None

try:
    voice = PiperVoice.load(MODEL_PATH)
    syn_config = SynthesisConfig(
        volume=0.8,
        length_scale=0.9,
        noise_scale=0.8,
        noise_w_scale=1.2,
        normalize_audio=False,
    )
    print(f"Successfully loaded Piper voice model: {MODEL_PATH}")
except Exception as e:
    print(f"Error loading Piper voice model at {MODEL_PATH}: {e}")

class SynthesizeBody(BaseModel):
    # Only text is required as per the new simplified requirement
    text: str = Field(..., min_length=1, max_length=50000)

@app.post("/synthesize")
async def synthesize(body: SynthesizeBody, request: Request):
    if not voice:
        raise HTTPException(
            status_code=500, 
            detail=f"Piper model not loaded. Please verify it exists at /app/{MODEL_PATH}"
        )

    filename = f"{uuid.uuid4().hex}.wav"
    file_path = AUDIO_DIR / filename

    try:
        # Generate the audio file using Piper
        with wave.open(str(file_path), "wb") as wav_file:
            voice.synthesize_wav(body.text, wav_file, syn_config=syn_config)

        # Return the audio file directly as a binary stream
        return FileResponse(path=str(file_path), media_type="audio/wav", filename=filename)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"TTS synthesis failed: {str(e)}")


@app.get("/audio/{filename}")
async def download_audio(filename: str):
    if "/" in filename or ".." in filename:
        raise HTTPException(status_code=400, detail="Invalid filename")

    file_path = AUDIO_DIR / filename
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Audio file not found")

    return FileResponse(path=str(file_path), media_type="audio/wav", filename=filename)


@app.get("/health")
def health():
    return {
        "status": "ok",
        "provider": "piper_local",
        "model_loaded": voice is not None,
        "model_path": MODEL_PATH
    }