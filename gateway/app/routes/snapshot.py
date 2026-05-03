import os
import time
import random
import base64
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional
from uuid import UUID

import httpx
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..core.db import get_db_session
from ..core.security import get_current_user, RoleChecker
from ..models.user import UserModel
from ..models.interview_model import InterviewModel
from ..models.application_model import ApplicationModel
from ..models.job_model import JobModel
from ..models.snapshot_model import SnapshotModel

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/snapshot", tags=["snapshot"])

# Snapshots are uploaded to the file-service over HTTP. On Cloud Run there
# is no shared volume, so the gateway never writes directly to disk.
FILE_SERVICE_URL = os.getenv("FILE_SERVICE_URL", "http://file-service:8005")


class SnapshotRequest(BaseModel):
    interview_id: str
    client_timestamp: int
    camera_image: str  # Base64
    screen_image: str  # Base64


def _resolve_snapshot_url(stored_path: Optional[str]) -> Optional[str]:
    """Convert a stored relative path (e.g. /uploads/snapshots/x.png) into an
    absolute, browser-reachable URL via the file-service static mount."""
    if stored_path is None:
        return None
    if not isinstance(stored_path, str) or not stored_path:
        return None
    if stored_path.startswith("http://") or stored_path.startswith("https://"):
        return stored_path
    file_service_url = os.getenv(
        "FILE_SERVICE_PUBLIC_URL",
        os.getenv("FILE_SERVICE_URL", "http://localhost:8005"),
    )
    file_service_url = file_service_url.rstrip("/")
    if stored_path.startswith("/uploads/"):
        static_path = "/static/" + stored_path[len("/uploads/"):].lstrip("/")
    elif stored_path.startswith("/static/"):
        static_path = stored_path
    else:
        static_path = "/" + stored_path.lstrip("/")
    return f"{file_service_url}{static_path}"


async def _upload_base64_image(
    client: httpx.AsyncClient,
    base64_str: str,
    prefix: str,
    interview_id: str,
) -> str:
    """Decode a base64 image and POST it to file-service /upload-file as
    multipart form-data. Returns the logical file_url file-service persists."""
    try:
        if "," in base64_str:
            base64_str = base64_str.split(",", 1)[1]
        image_data = base64.b64decode(base64_str)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid base64 image data for {prefix}",
        )

    filename = f"{interview_id}_{prefix}_{int(time.time() * 1000)}.png"
    base = FILE_SERVICE_URL.rstrip("/")
    try:
        resp = await client.post(
            f"{base}/upload-file",
            files={"file": (filename, image_data, "image/png")},
            data={"file_type": "snapshots"},
            timeout=30.0,
        )
    except httpx.HTTPError as e:
        logger.exception("snapshot.upload_failed prefix=%s err=%s", prefix, e)
        raise HTTPException(status_code=502, detail="File service unreachable")

    if resp.status_code != 200:
        logger.error(
            "snapshot.upload_bad_status prefix=%s status=%s body=%s",
            prefix, resp.status_code, resp.text[:300],
        )
        raise HTTPException(status_code=502, detail="Failed to upload snapshot")

    file_url = resp.json().get("file_url", "")
    if not file_url:
        raise HTTPException(status_code=502, detail="File service returned no URL")
    return file_url


@router.post("/", status_code=status.HTTP_200_OK)
async def save_snapshot(
    payload: SnapshotRequest,
    db: Session = Depends(get_db_session),
    current_user: UserModel = Depends(get_current_user),
):
    try:
        interview_uuid = UUID(payload.interview_id)
    except (ValueError, AttributeError):
        raise HTTPException(status_code=400, detail="Invalid interview ID")

    interview = db.query(InterviewModel).filter(InterviewModel.id == interview_uuid).first()
    if not interview:
        raise HTTPException(status_code=404, detail="Interview not found")

    if interview.status != "in_progress":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Interview is not in progress",
        )

    now = datetime.now(timezone.utc)

    expected_time = interview.next_snapshot_at
    if expected_time:
        if expected_time.tzinfo is None:
            expected_time = expected_time.replace(tzinfo=timezone.utc)

        if now < expected_time - timedelta(seconds=5):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Snapshot submitted too early",
            )

        if now > expected_time + timedelta(seconds=15):
            pass

    async with httpx.AsyncClient() as client:
        camera_url = await _upload_base64_image(
            client, payload.camera_image, "camera", payload.interview_id
        )
        screen_url = await _upload_base64_image(
            client, payload.screen_image, "screen", payload.interview_id
        )

    new_snapshot = SnapshotModel(
        interview_id=interview_uuid,
        camera_url=camera_url,
        screen_url=screen_url,
        client_timestamp=payload.client_timestamp,
        server_timestamp=int(now.timestamp() * 1000),
    )
    db.add(new_snapshot)

    interview.next_snapshot_at = now + timedelta(seconds=random.randint(1, 30))

    db.commit()

    logger.info(
        "Snapshot saved interview=%s camera=%s screen=%s",
        payload.interview_id,
        camera_url,
        screen_url,
    )

    return {"status": "ok"}


# =========================================================
# LIST SNAPSHOTS FOR AN INTERVIEW (RECRUITER/ADMIN ONLY)
# =========================================================
@router.get("/interview/{interview_id}", status_code=status.HTTP_200_OK)
def list_snapshots_for_interview(
    interview_id: UUID,
    db: Session = Depends(get_db_session),
    current_user: UserModel = Depends(RoleChecker(["RECRUITER", "ADMIN"])),
):
    """Return all proctoring snapshots for an interview, ordered by server
    timestamp ascending. Recruiter must belong to the same company that owns
    the job tied to this interview."""
    interview = db.query(InterviewModel).filter(InterviewModel.id == interview_id).first()
    if not interview:
        raise HTTPException(status_code=404, detail="Interview not found")

    application = (
        db.query(ApplicationModel)
        .filter(ApplicationModel.id == interview.application_id)
        .first()
    )
    if not application:
        raise HTTPException(status_code=404, detail="Application not found for interview")

    job = db.query(JobModel).filter(JobModel.id == application.job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found for interview")

    if not current_user.recruiter or current_user.recruiter.company_id != job.company_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to view this interview snapshots.",
        )

    rows = (
        db.query(SnapshotModel)
        .filter(SnapshotModel.interview_id == interview_id)
        .order_by(SnapshotModel.server_timestamp.asc())
        .all()
    )

    snapshots = [
        {
            "id": str(s.id),
            "camera_url": _resolve_snapshot_url(s.camera_url),
            "screen_url": _resolve_snapshot_url(s.screen_url),
            "client_timestamp": s.client_timestamp,
            "server_timestamp": s.server_timestamp,
            "created_at": s.created_at.isoformat() if s.created_at else None,
        }
        for s in rows
    ]

    return {
        "interview_id": str(interview_id),
        "interview_status": interview.status,
        "interview_started_at": interview.scheduled_at.isoformat() if interview.scheduled_at else None,
        "snapshots": snapshots,
    }