import os
import shutil
import time
from fastapi import APIRouter, UploadFile, File, HTTPException
from fastapi.responses import JSONResponse
from dotenv import load_dotenv
from groq import Groq

router = APIRouter()
# Load environment variables from a .env file
load_dotenv()
UPLOAD_DIR = os.getenv("UPLOAD_DIR", "/tmp/uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)

# Initialize Groq client
try:
    GROQ_CLIENT = Groq(api_key=os.getenv("GROQ_API_KEY"))
    GROQ_AVAILABLE = True
    GROQ_ERROR = None
except Exception as e:
    GROQ_CLIENT = None
    GROQ_AVAILABLE = False
    GROQ_ERROR = e


@router.post("/transcribe")
async def transcribe(file: UploadFile = File(...)):
    if not GROQ_AVAILABLE:
        raise HTTPException(
            status_code=500,
            detail=f"Groq transcription service unavailable: {GROQ_ERROR}"
        )

    try:
        # Save file
        filename = file.filename or f"audio_{int(time.time())}.wav"
        save_path = os.path.join(UPLOAD_DIR, filename)

        with open(save_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        # Groq Whisper API
        try:
            with open(save_path, "rb") as audio_file:
                transcription = GROQ_CLIENT.audio.transcriptions.create(
                    file=(filename, audio_file.read()),
                    model="whisper-large-v3",
                    temperature=0,
                    response_format="verbose_json",
                )
                return JSONResponse({
                    "transcription": transcription.text,
                    "model": "groq-whisper-large-v3"
                })
        except Exception as groq_error:
            raise HTTPException(
                status_code=500,
                detail=f"Groq transcription failed: {str(groq_error)}"
            )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))