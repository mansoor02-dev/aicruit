from ..core.db import Base
from sqlalchemy import Column, String, DateTime, func, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import declarative_base, relationship


class CandidateModel(Base):
    __tablename__ = "candidates"
    id = Column(UUID(as_uuid=True), ForeignKey("users.id"), primary_key=True)
    phone = Column(String(50), nullable=True)
    user = relationship("UserModel", back_populates="candidate")
    applications = relationship("ApplicationModel", back_populates="candidate", cascade="all, delete-orphan")