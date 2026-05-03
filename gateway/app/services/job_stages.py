from typing import List, Optional
from uuid import UUID

from sqlalchemy.orm import Session

from ..models.job_stage_model import JobStageModel
from ..models.application_model import ApplicationModel
from ..models.job_stage import StageReorderItem


class StageNotFoundError(Exception):
    pass


class StageConflictError(Exception):
    def __init__(self, candidate_count: int):
        self.candidate_count = candidate_count
        super().__init__(f"Stage has {candidate_count} candidates")


class StageReorderMismatchError(Exception):
    pass


class InvalidMoveTargetError(Exception):
    pass


def list_stages(db: Session, job_id: UUID) -> List[JobStageModel]:
    return (
        db.query(JobStageModel)
        .filter(JobStageModel.job_id == job_id)
        .order_by(JobStageModel.position.asc())
        .all()
    )


def create_stage(
    db: Session,
    job_id: UUID,
    name: str,
    position: Optional[int] = None,
) -> JobStageModel:
    existing = list_stages(db, job_id)

    if position is None:
        new_position = (max([s.position for s in existing]) + 1) if existing else 0
    else:
        new_position = position
        # Shift conflicting stages up by 1, atomically.
        # Use a temporary high offset to avoid the unique(job_id, position) collision.
        to_shift = [s for s in existing if s.position >= new_position]
        if to_shift:
            # First push them out of range
            for s in to_shift:
                s.position = s.position + 10000
            db.flush()
            # Then assign final +1 positions
            for s in to_shift:
                s.position = s.position - 10000 + 1
            db.flush()

    stage = JobStageModel(job_id=job_id, name=name, position=new_position)
    db.add(stage)
    db.commit()
    db.refresh(stage)
    return stage


def rename_stage(
    db: Session,
    job_id: UUID,
    stage_id: UUID,
    name: str,
) -> JobStageModel:
    stage = (
        db.query(JobStageModel)
        .filter(JobStageModel.id == stage_id, JobStageModel.job_id == job_id)
        .first()
    )
    if not stage:
        raise StageNotFoundError()
    stage.name = name
    db.commit()
    db.refresh(stage)
    return stage


def reorder_stages(
    db: Session,
    job_id: UUID,
    items: List[StageReorderItem],
) -> List[JobStageModel]:
    existing = list_stages(db, job_id)
    existing_ids = {s.id for s in existing}
    body_ids = {item.id for item in items}

    if existing_ids != body_ids:
        raise StageReorderMismatchError()

    by_id = {s.id: s for s in existing}

    # Two-phase update to avoid the unique(job_id, position) constraint
    for item in items:
        by_id[item.id].position = item.position + 10000
    db.flush()

    for item in items:
        by_id[item.id].position = item.position
    db.commit()

    return list_stages(db, job_id)


def delete_stage(
    db: Session,
    job_id: UUID,
    stage_id: UUID,
    move_to: Optional[UUID] = None,
) -> int:
    stage = (
        db.query(JobStageModel)
        .filter(JobStageModel.id == stage_id, JobStageModel.job_id == job_id)
        .first()
    )
    if not stage:
        raise StageNotFoundError()

    count = (
        db.query(ApplicationModel)
        .filter(ApplicationModel.stage_id == stage_id)
        .count()
    )

    if count > 0 and move_to is None:
        raise StageConflictError(candidate_count=count)

    moved = 0
    if count > 0 and move_to is not None:
        target = (
            db.query(JobStageModel)
            .filter(JobStageModel.id == move_to, JobStageModel.job_id == job_id)
            .first()
        )
        if not target:
            raise InvalidMoveTargetError()

        moved = (
            db.query(ApplicationModel)
            .filter(ApplicationModel.stage_id == stage_id)
            .update({ApplicationModel.stage_id: move_to}, synchronize_session=False)
        )

    db.delete(stage)
    db.commit()
    return moved
