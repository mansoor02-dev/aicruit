import os
import shutil
import time
from fastapi import APIRouter, UploadFile, File, HTTPException
from fastapi.responses import JSONResponse
from dotenv import load_dotenv
router = APIRouter()
# Load environment variables from a .env file
load_dotenv()
UPLOAD_DIR = os.getenv("UPLOAD_DIR", "/tmp/uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)

# Load Whisper SMALL once at startup
try:
    import whisper
    WHISPER_MODEL = whisper.load_model("small")
except Exception as e:
    WHISPER_MODEL = None
    WHISPER_ERROR = e


@router.post("/transcribe")
async def transcribe(file: UploadFile = File(...)):
    if WHISPER_MODEL is None:
        raise HTTPException(
            status_code=500,
            detail=f"Whisper model failed to load: {WHISPER_ERROR}"
        )

    try:
        # Save file
        filename = file.filename or f"audio_{int(time.time())}.wav"
        save_path = os.path.join(UPLOAD_DIR, filename)

        with open(save_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        # Transcribe with small model
        result = WHISPER_MODEL.transcribe(save_path)
        transcription = result.get("text", "")

        return JSONResponse({"transcription": transcription, "model": "small"})

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
