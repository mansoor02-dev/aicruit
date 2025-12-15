from ..core.db import Base
from sqlalchemy import Column, String, DateTime, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import declarative_base, relationship
import uuid

class CompanyModel(Base):
    __tablename__ = "companies"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(255), nullable=False)
    logo_url = Column(String, nullable=True)
    website = Column(String(255), nullable=True)
    subscription_status = Column(String(50), default="ACTIVE")
    created_at = Column(DateTime, default=func.now())

    # Relationship: One Company has Many Recruiters
    recruiters = relationship("RecruiterModel", back_populates="company")

    # Relationship: One Company has Many Jobs
    jobs = relationship("JobModel", back_populates="company")