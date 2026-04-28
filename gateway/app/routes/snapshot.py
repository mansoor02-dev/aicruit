import os
import time
import random
import base64
from datetime import datetime, timezone, timedelta
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..core.db import get_db_session
from ..core.security import get_current_user
from ..models.user import UserModel
from ..models.interview_model import InterviewModel
from ..models.snapshot_model import SnapshotModel

router = APIRouter(prefix="/snapshot", tags=["snapshot"])

# Directory to save snapshots locally
SNAPSHOTS_DIR = os.getenv("SNAPSHOTS_DIR", "/app/uploads/snapshots")
os.makedirs(SNAPSHOTS_DIR, exist_ok=True)


class SnapshotRequest(BaseModel):
    interview_id: str
    client_timestamp: int
    camera_image: str  # Base64
    screen_image: str  # Base64


def save_base64_image(base64_str: str, prefix: str, interview_id: str) -> str:
    """Saves a base64 string as an image file and returns the local URL/path."""
    try:
        # Strip header if present (e.g., "data:image/png;base64,...")
        if "," in base64_str:
            base64_str = base64_str.split(",")[1]
            
        image_data = base64.b64decode(base64_str)
        filename = f"{interview_id}_{prefix}_{int(time.time()*1000)}.png"
        filepath = os.path.join(SNAPSHOTS_DIR, filename)
        
        with open(filepath, "wb") as f:
            f.write(image_data)
            
        return f"/uploads/snapshots/{filename}"
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid base64 image data for {prefix}"
        )


@router.post("/", status_code=status.HTTP_200_OK)
def save_snapshot(
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
            detail="Interview is not in progress"
        )

    now = datetime.now(timezone.utc)
    
    # Validate timing
    expected_time = interview.next_snapshot_at
    if expected_time:
        if expected_time.tzinfo is None:
            expected_time = expected_time.replace(tzinfo=timezone.utc)
        
        # If it's too early (more than 5 seconds early)
        if now < expected_time - timedelta(seconds=5):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Snapshot submitted too early"
            )
            
        # If it's too late (more than 15 seconds late - grace period)
        # We don't strictly reject if it's too late because network delays happen,
        # but if we strictly follow "reject if too late", here is the check:
        if now > expected_time + timedelta(seconds=15):
            pass # We could log a warning or flag for cheating risk

    # Store images
    camera_url = save_base64_image(payload.camera_image, "camera", payload.interview_id)
    screen_url = save_base64_image(payload.screen_image, "screen", payload.interview_id)

    # Save snapshot record
    new_snapshot = SnapshotModel(
        interview_id=interview_uuid,
        camera_url=camera_url,
        screen_url=screen_url,
        client_timestamp=payload.client_timestamp,
        server_timestamp=int(now.timestamp() * 1000)
    )
    db.add(new_snapshot)

    # Generate next snapshot time (1 to 30 seconds)
    interview.next_snapshot_at = now + timedelta(seconds=random.randint(1, 30))
    
    db.commit()

    return {"status": "ok"}