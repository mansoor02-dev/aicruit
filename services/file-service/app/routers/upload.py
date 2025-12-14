from fastapi import APIRouter, UploadFile, File, HTTPException
import os
import uuid
from datetime import datetime
from ..db import get_db_session, FileUpload
from ..models import FileUploadResponse

router = APIRouter()

UPLOAD_DIR = "/app/uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)


@router.post("/upload-file", response_model=FileUploadResponse)
async def upload_file(file: UploadFile = File(...), file_type: str = "other"):
    try:
        # Create folder for file type
        folder = os.path.join(UPLOAD_DIR, file_type)
        os.makedirs(folder, exist_ok=True)

        # Unique file name
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        extension = file.filename.split(".")[-1] if "." in file.filename else ""
        filename = f"{file_type}_{timestamp}.{extension}" if extension else f"{file_type}_{timestamp}"

        filepath = os.path.join(folder, filename)

        # Save file and compute size
        data = await file.read()
        with open(filepath, "wb") as buffer:
            buffer.write(data)
        size = len(data)

        file_url = f"/static/{file_type}/{filename}"

        # Insert file metadata into database and return id
        session = get_db_session()
        try:
            file_row = FileUpload(
                file_type=file_type,
                file_url=file_url,
                original_filename=file.filename,
                mime_type=file.content_type,
                size=size,
            )
            session.add(file_row)
            session.commit()
            session.refresh(file_row)
            file_id = str(file_row.id) if file_row.id is not None else None
        finally:
            session.close()

        return {
            "status": "success",
            "file_url": file_url,
            "message": "File uploaded successfully",
            "id": file_id,
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
