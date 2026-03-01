import os
from sqlalchemy import create_engine, Column, String, Text, DateTime, JSON
from sqlalchemy.orm import sessionmaker, declarative_base
from sqlalchemy.sql import func

DATABASE_URL = os.getenv("DATABASE_URL") or (
    f"postgresql+psycopg2://{os.getenv('DB_USER','admin')}:{os.getenv('DB_PASS','admin123')}@{os.getenv('DB_HOST','localhost')}:{os.getenv('DB_PORT','5432')}/{os.getenv('DB_NAME','aicruit')}"
)

engine = create_engine(DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


class Resume(Base):
    __tablename__ = 'resumes'

    id = Column(String, primary_key=True)
    candidate_id = Column(String, nullable=True)
    file_url = Column(Text, nullable=False)
    parsed_text = Column(Text, nullable=True)
    parsed_skills = Column(JSON, nullable=True)
    created_at = Column(DateTime, server_default=func.now())


def get_db_session():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    Base.metadata.create_all(bind=engine)

