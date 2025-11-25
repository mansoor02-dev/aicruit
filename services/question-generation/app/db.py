# app/db.py
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
import os

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+asyncpg://postgres:postgres@localhost/interview_db"
)

engine = create_async_engine(DATABASE_URL, echo=False)
AsyncSessionLocal = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


class InterviewDB:
    @staticmethod
    async def get_resume_by_id(resume_id: str):
        async with AsyncSessionLocal() as db:
            result = await db.execute(
                text("SELECT parsed_json FROM resumes WHERE id = :rid"),
                {"rid": resume_id}
            )
            row = result.fetchone()
            return row[0] if row else None

    @staticmethod
    async def create_ai_session(interview_id: str, session_id: str, resume_id: str, job_description: str):
        async with AsyncSessionLocal() as db:
            result = await db.execute(
                text("""
                    INSERT INTO ai_interview_sessions 
                    (interview_id, session_id, resume_id, job_description)
                    VALUES (:iid, :sid, :rid, :jd)
                    RETURNING id
                """),
                {"iid": interview_id, "sid": session_id, "rid": resume_id, "jd": job_description}
            )
            await db.commit()
            return result.scalar()

    @staticmethod
    async def add_turn(session_id: str, turn_number: int, **data):
        async with AsyncSessionLocal() as db:
            await db.execute(
                text("""
                    INSERT INTO ai_interview_turns
                    (session_id, turn_number, question, user_answer, is_followup, topic,
                     depth_score, pass, confidence, feedback)
                    VALUES
                    (:sid, :tn, :q, :a, :fu, :t, :ds, :p, :c, :f)
                """),
                {"sid": session_id, "tn": turn_number, **data}
            )
            await db.commit()

    @staticmethod
    async def end_ai_session(session_id: str):
        async with AsyncSessionLocal() as db:
            await db.execute(
                text("""
                    UPDATE ai_interview_sessions 
                    SET ended_at = NOW(), status = 'completed'
                    WHERE session_id = :sid
                """),
                {"sid": session_id}
            )
            await db.commit()