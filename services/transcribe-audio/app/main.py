from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.routers.transcribe import router as transcribe_router
import os

app = FastAPI(title="transcribe-audio")

FRONTEND_ORIGINS = os.getenv("FRONTEND_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000").split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=FRONTEND_ORIGINS if FRONTEND_ORIGINS != [''] else ["*"],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

app.include_router(transcribe_router)


@app.get("/")
def root():
    return {"status": "ok", "service": "transcribe-audio"}
