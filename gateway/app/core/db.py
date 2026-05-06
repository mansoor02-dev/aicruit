import os
from sqlalchemy import create_engine, Column, String, Text, DateTime
from sqlalchemy.orm import sessionmaker, declarative_base
from sqlalchemy.sql import func
from dotenv import load_dotenv

# Load .env before constructing DATABASE_URL
load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL") or (
    f"postgresql+psycopg2://{os.getenv('DB_USER','admin')}:{os.getenv('DB_PASS','admin123')}@{os.getenv('DB_HOST','postgres')}:{os.getenv('DB_PORT','5432')}/{os.getenv('DB_NAME','aicruit')}"
)

engine = create_engine(DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

def get_db_session():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
        
def init_db():
    Base.metadata.create_all(bind=engine)
    
