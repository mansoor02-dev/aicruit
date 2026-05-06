"""Idempotent backfill script for kanban stages.

Seeds default `job_stages` rows for jobs that have none and maps every
`applications.stage_id IS NULL` row onto a stage based on its legacy
`status` value. Re-running the script is safe.

Usage:
    python database/migrations/backfill_kanban_stages.py
"""

from __future__ import annotations

import os
import sys
from typing import List, Optional, Tuple
from uuid import UUID

import psycopg2
from psycopg2.extras import RealDictCursor


def _build_database_url() -> str:
    url = os.getenv("DATABASE_URL")
    if url:
        # psycopg2 doesn't understand the SQLAlchemy "+psycopg2" suffix.
        return url.replace("postgresql+psycopg2://", "postgresql://")
    user = os.getenv("DB_USER", "admin")
    password = os.getenv("DB_PASS", "admin123")
    host = os.getenv("DB_HOST", "localhost")
    port = os.getenv("DB_PORT", "5432")
    name = os.getenv("DB_NAME", "aicruit")
    return f"postgresql://{user}:{password}@{host}:{port}/{name}"


def _stage_names_for(ai_enabled: bool) -> List[str]:
    if ai_enabled:
        return ["Applied", "AI Interview", "Shortlisted"]
    return ["Applied", "Shortlisted"]


def _seed_default_stages(cur) -> int:
    """Insert default stages for any job that has none. Returns number of jobs seeded."""
    cur.execute(
        """
        SELECT j.id AS job_id,
               COALESCE(jis.ai_interview_enabled, FALSE) AS ai_enabled
        FROM jobs j
        LEFT JOIN job_interview_settings jis ON jis.job_id = j.id
        WHERE NOT EXISTS (
            SELECT 1 FROM job_stages s WHERE s.job_id = j.id
        )
        """
    )
    rows = cur.fetchall()
    seeded = 0
    for row in rows:
        job_id: UUID = row["job_id"]
        ai_enabled: bool = bool(row["ai_enabled"])
        names = _stage_names_for(ai_enabled)
        for position, name in enumerate(names):
            cur.execute(
                """
                INSERT INTO job_stages (job_id, position, name)
                VALUES (%s, %s, %s)
                ON CONFLICT (job_id, position) DO NOTHING
                """,
                (str(job_id), position, name),
            )
        seeded += 1
    return seeded


def _fetch_stages_for_job(cur, job_id: UUID) -> List[Tuple[UUID, int, str]]:
    cur.execute(
        """
        SELECT id, position, name
        FROM job_stages
        WHERE job_id = %s
        ORDER BY position ASC
        """,
        (str(job_id),),
    )
    return [(r["id"], r["position"], r["name"]) for r in cur.fetchall()]


def _map_status_to_stage_id(
    status: Optional[str],
    stages: List[Tuple[UUID, int, str]],
    ai_enabled: bool,
) -> Optional[UUID]:
    if not stages:
        return None
    if status is None:
        return stages[0][0]
    s = status.upper()
    if s == "REJECTED":
        return None  # leave NULL; status stays REJECTED
    if s in ("APPLIED", "SCREENING"):
        return stages[0][0]
    if s in ("INTERVIEW_SCHEDULED", "INTERVIEW_COMPLETED"):
        if ai_enabled and len(stages) >= 3:
            return stages[1][0]  # middle (AI Interview)
        return stages[-1][0]
    if s == "OFFERED":
        return stages[-1][0]
    # Unknown status: park on first stage
    return stages[0][0]


def _backfill_applications(cur) -> int:
    """For each application with stage_id IS NULL, map legacy status -> stage. Returns count."""
    cur.execute(
        """
        SELECT a.id AS application_id,
               a.job_id,
               a.status,
               COALESCE(jis.ai_interview_enabled, FALSE) AS ai_enabled
        FROM applications a
        LEFT JOIN job_interview_settings jis ON jis.job_id = a.job_id
        WHERE a.stage_id IS NULL
        """
    )
    rows = cur.fetchall()

    # Cache stages per job to avoid re-querying.
    stages_cache: dict = {}
    backfilled = 0
    for row in rows:
        application_id: UUID = row["application_id"]
        job_id: UUID = row["job_id"]
        status: Optional[str] = row["status"]
        ai_enabled: bool = bool(row["ai_enabled"])

        if job_id not in stages_cache:
            stages_cache[job_id] = _fetch_stages_for_job(cur, job_id)
        stages = stages_cache[job_id]

        target_stage_id = _map_status_to_stage_id(status, stages, ai_enabled)
        if target_stage_id is None:
            continue
        cur.execute(
            """
            UPDATE applications
            SET stage_id = %s
            WHERE id = %s AND stage_id IS NULL
            """,
            (str(target_stage_id), str(application_id)),
        )
        if cur.rowcount:
            backfilled += 1
    return backfilled


def main() -> int:
    dsn = _build_database_url()
    print(f"[backfill] connecting to {dsn.split('@')[-1]}")
    conn = psycopg2.connect(dsn)
    conn.autocommit = False
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            seeded_jobs = _seed_default_stages(cur)
            backfilled_apps = _backfill_applications(cur)
        conn.commit()
        print(
            f"[backfill] seeded {seeded_jobs} jobs, "
            f"backfilled {backfilled_apps} applications"
        )
        return 0
    except Exception as exc:
        conn.rollback()
        print(f"[backfill] FAILED: {exc}", file=sys.stderr)
        return 1
    finally:
        conn.close()


if __name__ == "__main__":
    sys.exit(main())
