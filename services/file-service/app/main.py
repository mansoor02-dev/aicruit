from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from app.routers import upload

app = FastAPI()

app.include_router(upload.router)

# Serve uploaded files
app.mount("/static", StaticFiles(directory="/app/uploads"), name="static")
