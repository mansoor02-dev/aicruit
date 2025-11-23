from pydantic import BaseModel

class FileUploadResponse(BaseModel):
    status: str
    file_url: str
