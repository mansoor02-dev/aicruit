from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import RedirectResponse, Response
from fastapi.middleware.cors import CORSMiddleware
from app.routers import upload
from app.storage import get_storage, GCSStorage, LocalStorage
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


@app.get("/health")
def health():
    return {"status": "ok"}


# Serve uploaded files. Behaviour depends on STORAGE_BACKEND:
#   - local: mount the upload directory as static files (zero-overhead disk serve)
#   - gcs:   redirect to a short-lived signed URL so bytes never traverse Cloud Run
_storage = get_storage()
if isinstance(_storage, LocalStorage):
    app.mount("/static", StaticFiles(directory=_storage.upload_dir), name="static")
elif isinstance(_storage, GCSStorage):
    @app.get("/static/{key:path}")
    def serve_gcs(key: str):
        if not _storage.exists(key):
            return Response(status_code=404)
        signed_url = _storage.serve(key)
        return RedirectResponse(url=signed_url, status_code=302)
