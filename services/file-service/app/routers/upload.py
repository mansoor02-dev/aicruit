from fastapi import APIRouter, UploadFile, File, HTTPException
import uuid
from datetime import datetime
from ..db import get_db_session, FileUpload
from ..models import FileUploadResponse
from ..storage import get_storage

router = APIRouter()


@router.post("/upload-file", response_model=FileUploadResponse)
async def upload_file(file: UploadFile = File(...), file_type: str = "other"):
    try:
        # Unique file name
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        extension = file.filename.split(".")[-1] if "." in file.filename else ""
        suffix = uuid.uuid4().hex[:8]
        filename = (
            f"{file_type}_{timestamp}_{suffix}.{extension}"
            if extension
            else f"{file_type}_{timestamp}_{suffix}"
        )

        # Storage key is "<file_type>/<filename>" — same on local disk and in GCS
        key = f"{file_type}/{filename}"

        data = await file.read()
        size = len(data)

        storage = get_storage()
        public_url = storage.save(data, key, content_type=file.content_type)

        # Persist a stable logical URL. We keep the legacy "/uploads/<key>" prefix that
        # the gateway already knows how to translate into a /static/<key> URL, so existing
        # consumers continue to work unchanged.
        file_url = f"/uploads/{key}"

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
            "public_url": public_url,
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
