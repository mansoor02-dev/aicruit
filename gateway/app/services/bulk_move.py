"""Bulk move applications by AI match score.

Pure compute (`compute_bulk_move`) is separated from the DB-bound writer
(`execute_bulk_move`) so the core logic can be unit-tested without a DB.
"""
from typing import List, Optional, Iterable
from uuid import UUID

from sqlalchemy.orm import Session

from ..models.application_model import ApplicationModel
from ..models.job_stage_model import JobStageModel
from ..models.application import BulkMoveResponse, BulkMoveSkipped


class StageNotFoundError(Exception):
    pass


class NoNextStageError(Exception):
    pass


def compute_bulk_move(
    applications: Iterable,
    source_stage,
    target_stage,
    min_score: int,
) -> BulkMoveResponse:
    """Pure: bucket applications into moved / skipped without DB writes."""
    moved: List[UUID] = []
    skipped: List[BulkMoveSkipped] = []

    for app in applications:
        if getattr(app, "status", None) == "REJECTED":
            continue
        score = getattr(app, "ai_match_score", None)
        if score is None:
            skipped.append(
                BulkMoveSkipped(
                    application_id=app.id,
                    reason="no_score",
                    ai_match_score=None,
                )
            )
        elif score < min_score:
            skipped.append(
                BulkMoveSkipped(
                    application_id=app.id,
                    reason="below_threshold",
                    ai_match_score=score,
                )
            )
        else:
            moved.append(app.id)

    return BulkMoveResponse(
        moved=moved,
        skipped=skipped,
        target_stage={"id": str(target_stage.id), "name": target_stage.name},
    )


def _load_stage(db: Session, job_id: UUID, stage_id: UUID) -> JobStageModel:
    stage = (
        db.query(JobStageModel)
        .filter(JobStageModel.id == stage_id, JobStageModel.job_id == job_id)
        .first()
    )
    if stage is None:
        raise StageNotFoundError("Stage not found")
    return stage


def _resolve_target_stage(
    db: Session,
    job_id: UUID,
    source: JobStageModel,
    target_stage_id: Optional[UUID],
) -> JobStageModel:
    if target_stage_id is not None:
        target = (
            db.query(JobStageModel)
            .filter(
                JobStageModel.id == target_stage_id,
                JobStageModel.job_id == job_id,
            )
            .first()
        )
        if target is None:
            raise StageNotFoundError("Target stage not found on this job")
        return target

    next_stage = (
        db.query(JobStageModel)
        .filter(
            JobStageModel.job_id == job_id,
            JobStageModel.position == source.position + 1,
        )
        .first()
    )
    if next_stage is None:
        raise NoNextStageError("Source stage has no next stage")
    return next_stage


def execute_bulk_move(
    db: Session,
    job_id: UUID,
    stage_id: UUID,
    min_score: int,
    target_stage_id: Optional[UUID],
    dry_run: bool = False,
) -> BulkMoveResponse:
    """Load source/target, compute the plan, and (unless dry_run) bulk-update."""
    source = _load_stage(db, job_id, stage_id)
    target = _resolve_target_stage(db, job_id, source, target_stage_id)

    # Determine if `source` is the first stage on this job. The board endpoint
    # display-buckets orphan applications (stage_id IS NULL, status != REJECTED)
    # into the first stage as a fallback, so they should be eligible for bulk
    # move from that column as well.
    all_stages = (
        db.query(JobStageModel)
        .filter(JobStageModel.job_id == job_id)
        .order_by(JobStageModel.position.asc())
        .all()
    )
    is_first_stage = bool(all_stages) and all_stages[0].id == source.id

    if is_first_stage:
        from sqlalchemy import or_
        applications = (
            db.query(ApplicationModel)
            .filter(
                ApplicationModel.job_id == job_id,
                or_(
                    ApplicationModel.stage_id == stage_id,
                    ApplicationModel.stage_id.is_(None),
                ),
                ApplicationModel.status != "REJECTED",
            )
            .all()
        )
    else:
        applications = (
            db.query(ApplicationModel)
            .filter(
                ApplicationModel.job_id == job_id,
                ApplicationModel.stage_id == stage_id,
                ApplicationModel.status != "REJECTED",
            )
            .all()
        )

    plan = compute_bulk_move(applications, source, target, min_score)

    if not dry_run and plan.moved:
        moved_ids = list(plan.moved)
        db.query(ApplicationModel).filter(
            ApplicationModel.id.in_(moved_ids)
        ).update(
            {"stage_id": target.id, "status": target.name},
            synchronize_session=False,
        )
        db.commit()

    return plan
