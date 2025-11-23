from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from app.routers import upload
import os

app = FastAPI()

# Configure CORS so the frontend (e.g. Next.js dev at localhost:3000) can call this service
FRONTEND_ORIGINS = os.getenv("FRONTEND_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000").split(",")

app.add_middleware(
	CORSMiddleware,
	allow_origins=FRONTEND_ORIGINS if FRONTEND_ORIGINS != [''] else ["*"],
	allow_credentials=True,
	allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
	allow_headers=["*"],
)

app.include_router(upload.router)

# Serve uploaded files
app.mount("/static", StaticFiles(directory="/app/uploads"), name="static")
