from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .routes import auth, job, interview, job_interview_settings
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
	allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
	allow_headers=["*"],
)

# Register routes
app.include_router(auth.router)
app.include_router(interview.router, prefix="/interview", tags=["Interview"])
app.include_router(job.router, prefix="/job", tags=["Jobs"])
app.include_router(job_interview_settings.router, prefix="/job", tags=["Job Interview Settings"])
