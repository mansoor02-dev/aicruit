from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.routers import parse
import os

app = FastAPI(title="Resume Parser Service", version="1.0.0")

# Configure CORS so the frontend can call this service
FRONTEND_ORIGINS = os.getenv("FRONTEND_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000").split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=FRONTEND_ORIGINS if FRONTEND_ORIGINS != [''] else ["*"],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

app.include_router(parse.router)


@app.get("/")
async def root():
    return {"message": "Resume Parser Service", "status": "running"}


@app.get("/health")
async def health():
    return {"status": "healthy"}

