import uuid
from ..core.db import Base
from sqlalchemy import Column, String, BigInteger, DateTime, ForeignKey, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

class SnapshotModel(Base):
    __tablename__ = "snapshots"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    interview_id = Column(UUID(as_uuid=True), ForeignKey("interviews.id", ondelete="CASCADE"), nullable=False)
    
    camera_url = Column(String)
    screen_url = Column(String)
    
    client_timestamp = Column(BigInteger)
    server_timestamp = Column(BigInteger)

    created_at = Column(DateTime, default=func.now())
