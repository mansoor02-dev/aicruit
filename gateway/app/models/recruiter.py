from ..core.db import Base
from sqlalchemy import Column, String, DateTime, func, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import declarative_base, relationship
import uuid

class RecruiterModel(Base):
    __tablename__ = "recruiters"

    # The ID is a Foreign Key to Users, ensuring 1-to-1 mapping
    id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    
    # Link to the Company they work for
    company_id = Column(UUID(as_uuid=True), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False)
    is_admin = Column(String, default='false')

    # Relationships
    user = relationship("UserModel", back_populates="recruiter")
    company = relationship("CompanyModel", back_populates="recruiters")