from pydantic import BaseModel
from typing import Optional
from uuid import UUID


class JobStageCreate(BaseModel):
    name: str
    position: Optional[int] = None


class JobStageUpdate(BaseModel):
    name: Optional[str] = None


class JobStageResponse(BaseModel):
    id: UUID
    position: int
    name: str

    class Config:
        from_attributes = True


class StageReorderItem(BaseModel):
    id: UUID
    position: int
