from ..core.db import Base
from sqlalchemy import Column, String, DateTime, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import declarative_base, relationship
import uuid

class UserModel(Base):
    __tablename__ = "users"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email = Column(String, unique=True, index=True, nullable=False)
    full_name = Column(String, nullable=False)
    # password_hash = Column(String, nullable=False)
    cognito_sub = Column(String, unique=True, nullable=True)
    email_verified = Column(String, default='false')
    role = Column(String,nullable=False, default='CANDIDATE')
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
    recruiter = relationship("RecruiterModel", back_populates="user", uselist=False, cascade="all, delete-orphan")
    candidate = relationship("CandidateModel", back_populates="user", uselist=False, cascade="all, delete-orphan")
    