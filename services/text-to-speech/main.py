import os
import logging
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from pydantic import BaseModel, Field
from google.cloud import texttospeech

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Google Cloud TTS Service", version="2.0.0")

# CORS
FRONTEND_ORIGINS = os.getenv("FRONTEND_ORIGINS", "http://localhost:3000").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=FRONTEND_ORIGINS if FRONTEND_ORIGINS != [''] else ["*"],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

# Config
TTS_VOICE = os.getenv("TTS_VOICE", "en-US-Neural2-J")
TTS_SPEAKING_RATE = float(os.getenv("TTS_SPEAKING_RATE", "1.0"))
# Language code is the first two segments of the voice name (e.g. "en-US")
TTS_LANGUAGE_CODE = "-".join(TTS_VOICE.split("-")[:2]) if TTS_VOICE else "en-US"

# Lazy-init client (uses Application Default Credentials)
_client: texttospeech.TextToSpeechClient | None = None


def get_client() -> texttospeech.TextToSpeechClient:
    global _client
    if _client is None:
        _client = texttospeech.TextToSpeechClient()
    return _client


class SynthesizeBody(BaseModel):
    text: str = Field(..., min_length=1, max_length=50000)


@app.post("/synthesize")
async def synthesize(body: SynthesizeBody):
    try:
        client = get_client()
        synthesis_input = texttospeech.SynthesisInput(text=body.text)
        voice = texttospeech.VoiceSelectionParams(
            language_code=TTS_LANGUAGE_CODE,
            name=TTS_VOICE,
        )
        audio_config = texttospeech.AudioConfig(
            audio_encoding=texttospeech.AudioEncoding.MP3,
            speaking_rate=TTS_SPEAKING_RATE,
        )
        response = client.synthesize_speech(
            input=synthesis_input,
            voice=voice,
            audio_config=audio_config,
        )
        return Response(content=response.audio_content, media_type="audio/mpeg")
    except Exception as e:
        logger.exception("TTS synthesis failed")
        raise HTTPException(status_code=500, detail=f"TTS synthesis failed: {str(e)}")


@app.get("/health")
def health():
    return {"status": "ok"}
