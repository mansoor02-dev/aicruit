from pydantic import BaseModel
from typing import Optional


class FileUploadResponse(BaseModel):
    status: str
    file_url: str
    message: Optional[str] = None
    id: Optional[str] = None
