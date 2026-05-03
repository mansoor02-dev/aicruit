"""
Auto-schedule service for AI interviews.

Distributes a set of eligible candidates across a date range with one
interview per candidate, front-loaded (extras land on earlier days).
Each candidate's interview gets a 1-day validity window: 00:00 to
23:59:59 in the job's timezone, stored as UTC timestamps.
"""

from datetime import date, datetime, time, timedelta, timezone
from typing import List, Tuple, Optional
from uuid import UUID
from zoneinfo import ZoneInfo

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from ..models.application_model import ApplicationModel
from ..models.interview_model import InterviewModel
from ..models.job_model import JobModel


def distribute(n_candidates: int, n_days: int) -> List[int]:
    """Front-loaded distribution. Extras land on earlier days.

    Examples:
        distribute(23, 5) -> [5, 5, 5, 4, 4]
        distribute(10, 5) -> [2, 2, 2, 2, 2]
        distribute(3, 5)  -> [1, 1, 1, 0, 0]
        distribute(0, 5)  -> [0, 0, 0, 0, 0]
    """
    if n_days <= 0:
        return []
    base = n_candidates // n_days
    extras = n_candidates % n_days
    return [base + 1 if i < extras else base for i in range(n_days)]


def compute_windows(
    start_date: date, n_days: int, tz_name: str
) -> List[Tuple[datetime, datetime]]:
    """Compute (scheduled_at, expires_at) UTC pairs for each day in the range.

    Each window is inclusive: 00:00:00 to 23:59:59 in the given timezone,
    converted to UTC for storage. Range is inclusive of both endpoints.
    """
    tz = ZoneInfo(tz_name)
    windows: List[Tuple[datetime, datetime]] = []
    for i in range(n_days):
        d = start_date + timedelta(days=i)
        local_start = datetime.combine(d, time(0, 0, 0), tzinfo=tz)
        local_end = datetime.combine(d, time(23, 59, 59), tzinfo=tz)
        windows.append(
            (local_start.astimezone(timezone.utc), local_end.astimezone(timezone.utc))
        )
    return windows


def auto_schedule(
    db: Session,
    job: JobModel,
    stage_id: UUID,
    start_date: date,
    end_date: date,
    dry_run: bool,
) -> dict:
    """Orchestrate auto-scheduling. Returns {assigned: [...], skipped: [...]}."""
    if end_date < start_date:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="end_date must be on or after start_date",
        )

    tz_name = job.timezone or "UTC"
    try:
        ZoneInfo(tz_name)
    except Exception:
        tz_name = "UTC"

    n_days = (end_date - start_date).days + 1

    # Eligible candidates: applications in stage, not REJECTED.
    apps = (
        db.query(ApplicationModel)
        .filter(ApplicationModel.job_id == job.id)
        .filter(ApplicationModel.stage_id == stage_id)
        .filter(ApplicationModel.status != "REJECTED")
        .order_by(ApplicationModel.created_at.asc())
        .all()
    )

    eligible: List[ApplicationModel] = []
    skipped: List[dict] = []
    for app in apps:
        active = (
            db.query(InterviewModel)
            .filter(InterviewModel.application_id == app.id)
            .filter(InterviewModel.status.in_(("scheduled", "in_progress")))
            .first()
        )
        if active is not None:
            skipped.append(
                {"application_id": str(app.id), "reason": "already_scheduled"}
            )
        else:
            eligible.append(app)

    distribution = distribute(len(eligible), n_days)
    windows = compute_windows(start_date, n_days, tz_name)

    assigned: List[dict] = []
    new_rows: List[InterviewModel] = []

    cursor = 0
    for day_idx, count in enumerate(distribution):
        if count <= 0:
            continue
        scheduled_at, expires_at = windows[day_idx]
        day_iso = (start_date + timedelta(days=day_idx)).isoformat()
        for _ in range(count):
            if cursor >= len(eligible):
                break
            app = eligible[cursor]
            cursor += 1
            assigned.append(
                {
                    "application_id": str(app.id),
                    "day": day_iso,
                    "expires_at": expires_at.isoformat(),
                }
            )
            if not dry_run:
                new_rows.append(
                    InterviewModel(
                        application_id=app.id,
                        scheduled_at=scheduled_at,
                        expires_at=expires_at,
                        status="scheduled",
                    )
                )

    if not dry_run and new_rows:
        try:
            for row in new_rows:
                db.add(row)
            db.commit()
        except Exception:
            db.rollback()
            raise

    return {"assigned": assigned, "skipped": skipped}
