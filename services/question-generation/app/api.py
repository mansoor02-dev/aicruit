# app/api.py
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from app.interview_service import create_session, get_next_question

app = FastAPI(title="AI Interviewer API")

class StartInterviewRequest(BaseModel):
    interview_id: str       # Your real UUID from interviews table
    resume_id: str          # UUID from resumes table
    job_description: str

class AnswerRequest(BaseModel):
    session_id: str
    answer: str

@app.post("/start-interview")
async def start(req: StartInterviewRequest):
    try:
        resp = await create_session(
            interview_id=req.interview_id,
            resume_id=req.resume_id,
            job_description=req.job_description
        )
        return resp
    except Exception as e:
        raise HTTPException(500, str(e))

@app.post("/answer")
async def answer(req: AnswerRequest):
    try:
        return await get_next_question(req.session_id, req.answer)
    except ValueError:
        raise HTTPException(404, "Session not found")
    except Exception as e:
        raise HTTPException(500, str(e))