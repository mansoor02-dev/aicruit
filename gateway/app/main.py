from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .routes import auth, job, interview, job_interview_settings, snapshot, email
from dotenv import load_dotenv
import os

load_dotenv()
app = FastAPI()

# Configure CORS from env
FRONTEND_ORIGINS = os.getenv("FRONTEND_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000").split(",")

app.add_middleware(
	CORSMiddleware,
	allow_origins=FRONTEND_ORIGINS if FRONTEND_ORIGINS != [''] else ["*"],
	allow_credentials=True,
	allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
	allow_headers=["*"],
)

# Register routes
app.include_router(auth.router)
app.include_router(interview.router, prefix="/interview", tags=["Interview"])
app.include_router(job.router, prefix="/job", tags=["Jobs"])
app.include_router(job_interview_settings.router, prefix="/job", tags=["Job Interview Settings"])
app.include_router(snapshot.router)
app.include_router(email.router, prefix="/email", tags=["Email"])

@app.get("/health", tags=["health"])
def _health():
    return {"status": "ok"}
