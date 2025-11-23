from fastapi import APIRouter, UploadFile, File, HTTPException
import os
import uuid
from datetime import datetime
from ..db import get_db_connection
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
        conn = get_db_connection()
        cur = conn.cursor()
        insert_sql = (
            "INSERT INTO file_uploads (file_type, file_url, original_filename, mime_type, size)"
            " VALUES (%s, %s, %s, %s, %s) RETURNING id"
        )
        cur.execute(insert_sql, (file_type, file_url, file.filename, file.content_type, size))
        returned = cur.fetchone()
        conn.commit()
        cur.close()
        conn.close()

        file_id = str(returned[0]) if returned and returned[0] is not None else None

        return {
            "status": "success",
            "file_url": file_url,
            "message": "File uploaded successfully",
            "id": file_id,
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
