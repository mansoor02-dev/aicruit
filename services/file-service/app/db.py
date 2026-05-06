import os
from sqlalchemy import create_engine, Column, String, Text, BigInteger, DateTime
from sqlalchemy.orm import sessionmaker, declarative_base
from sqlalchemy.sql import func

DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    DATABASE_URL = (
        f"postgresql+psycopg2://{os.getenv('DB_USER','admin')}:{os.getenv('DB_PASS','admin123')}"
        f"@{os.getenv('DB_HOST','localhost')}:{os.getenv('DB_PORT','5432')}/{os.getenv('DB_NAME','aicruit')}"
    )

engine = create_engine(DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


class FileUpload(Base):
    __tablename__ = 'file_uploads'

    id = Column(String, primary_key=True, server_default=func.gen_random_uuid())
    user_id = Column(String, nullable=True)
    file_type = Column(String(50), nullable=False)
    file_url = Column(Text, nullable=False)
    original_filename = Column(Text, nullable=False)
    mime_type = Column(String(100), nullable=True)
    size = Column(BigInteger, nullable=True)
    created_at = Column(DateTime, server_default=func.now())


def get_db_session():
    return SessionLocal()


def init_db():
    Base.metadata.create_all(bind=engine)