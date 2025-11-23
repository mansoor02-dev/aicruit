from fastapi import APIRouter, UploadFile, File, HTTPException
import os
from datetime import datetime

router = APIRouter()

UPLOAD_DIR = "/app/uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

@router.post("/upload-file")
async def upload_file(file: UploadFile = File(...), file_type: str = "other"):
    try:
        # Create folder for file type
        folder = os.path.join(UPLOAD_DIR, file_type)
        os.makedirs(folder, exist_ok=True)

        # Unique file name
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        extension = file.filename.split(".")[-1]
        filename = f"{file_type}_{timestamp}.{extension}"

        filepath = os.path.join(folder, filename)

        # Save file
        with open(filepath, "wb") as buffer:
            buffer.write(await file.read())

        file_url = f"/static/{file_type}/{filename}"

        return {
            "status": "success",
            "file_url": file_url,
            "message": "File uploaded successfully"
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
