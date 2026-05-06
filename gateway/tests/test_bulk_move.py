"""Tests for bulk move by AI score (Slice A)."""
import uuid
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from app.services import bulk_move as bulk_move_svc
from app.services.bulk_move import (
    compute_bulk_move,
    execute_bulk_move,
    NoNextStageError,
)


def _app(score, status="APPLIED"):
    return SimpleNamespace(id=uuid.uuid4(), ai_match_score=score, status=status)


def _stage(name, position):
    return SimpleNamespace(id=uuid.uuid4(), name=name, position=position)


def test_compute_bulk_move_promotes_above_threshold():
    apps = [_app(80), _app(50), _app(20)]
    source = _stage("Applied", 0)
    target = _stage("Screening", 1)

    result = compute_bulk_move(apps, source, target, min_score=70)

    assert result.moved == [apps[0].id]
    assert len(result.skipped) == 2
    reasons = sorted([s.reason for s in result.skipped])
    assert reasons == ["below_threshold", "below_threshold"]
    skipped_ids = {s.application_id for s in result.skipped}
    assert skipped_ids == {apps[1].id, apps[2].id}
    assert result.target_stage == {"id": str(target.id), "name": "Screening"}


def test_compute_bulk_move_excludes_null_scores():
    apps = [_app(None), _app(90)]
    source = _stage("Applied", 0)
    target = _stage("Screening", 1)

    result = compute_bulk_move(apps, source, target, min_score=70)

    assert result.moved == [apps[1].id]
    assert len(result.skipped) == 1
    assert result.skipped[0].application_id == apps[0].id
    assert result.skipped[0].reason == "no_score"
    assert result.skipped[0].ai_match_score is None


def test_compute_bulk_move_excludes_rejected():
    rejected = _app(95, status="REJECTED")
    keep = _app(80)
    source = _stage("Applied", 0)
    target = _stage("Screening", 1)

    result = compute_bulk_move([rejected, keep], source, target, min_score=70)

    moved_or_skipped = set(result.moved) | {s.application_id for s in result.skipped}
    assert rejected.id not in moved_or_skipped
    assert result.moved == [keep.id]


def _make_query_chain(return_value):
    """Build a MagicMock that supports .filter(...).first() returning given value."""
    q = MagicMock()
    q.filter.return_value.first.return_value = return_value
    return q


def _make_stages_query(stages):
    """Build a MagicMock for the all_stages query: .filter(...).order_by(...).all()."""
    q = MagicMock()
    q.filter.return_value.order_by.return_value.all.return_value = list(stages)
    return q


def test_execute_bulk_move_422_on_last_stage():
    job_id = uuid.uuid4()
    stage_id = uuid.uuid4()
    source = _stage("Final", 5)
    source.id = stage_id

    db = MagicMock()
    # Sequence of db.query(...) calls inside execute_bulk_move:
    #  1) load source stage  -> returns source
    #  2) resolve next stage -> returns None (no next)
    db.query.side_effect = [
        _make_query_chain(source),
        _make_query_chain(None),
    ]

    with pytest.raises(NoNextStageError):
        execute_bulk_move(db, job_id, stage_id, min_score=70, target_stage_id=None)


def test_bulk_move_includes_orphans_when_source_is_first_stage():
    """Pure-function test: if source is the first stage, applications with
    stage_id=None must be eligible for the move (matches board fallback)."""
    job_id = uuid.uuid4()
    stage_a = _stage("Applied", 0)
    stage_b = _stage("Screening", 1)
    target = _stage("Final", 2)

    orphan = SimpleNamespace(
        id=uuid.uuid4(), ai_match_score=80, status="APPLIED", stage_id=None
    )
    in_a = SimpleNamespace(
        id=uuid.uuid4(), ai_match_score=90, status="APPLIED", stage_id=stage_a.id
    )
    in_b = SimpleNamespace(
        id=uuid.uuid4(), ai_match_score=85, status="APPLIED", stage_id=stage_b.id
    )

    # --- Case 1: source = first stage (A) -> orphan IS in moved ---
    apps_query_a = MagicMock()
    apps_query_a.filter.return_value.all.return_value = [in_a, orphan]
    db_a = MagicMock()
    db_a.query.side_effect = [
        _make_query_chain(stage_a),                  # load source
        _make_query_chain(target),                   # resolve target by id
        _make_stages_query([stage_a, stage_b]),      # all stages on job
        apps_query_a,                                # applications query
    ]

    result_a = execute_bulk_move(
        db_a, job_id, stage_a.id, min_score=70, target_stage_id=target.id,
        dry_run=True,
    )
    assert orphan.id in result_a.moved
    assert in_a.id in result_a.moved

    # --- Case 2: source = stage B (not first) -> orphan NOT eligible ---
    apps_query_b = MagicMock()
    # When source is not first, the SQL filter would exclude the orphan; mirror
    # that here by only returning the in_b application from .all().
    apps_query_b.filter.return_value.all.return_value = [in_b]
    db_b = MagicMock()
    db_b.query.side_effect = [
        _make_query_chain(stage_b),                  # load source
        _make_query_chain(target),                   # resolve target by id
        _make_stages_query([stage_a, stage_b]),      # all stages on job
        apps_query_b,                                # applications query
    ]

    result_b = execute_bulk_move(
        db_b, job_id, stage_b.id, min_score=70, target_stage_id=target.id,
        dry_run=True,
    )
    moved_or_skipped_b = set(result_b.moved) | {s.application_id for s in result_b.skipped}
    assert orphan.id not in moved_or_skipped_b
    assert in_b.id in result_b.moved


def test_execute_bulk_move_resolves_next_stage_when_target_omitted():
    job_id = uuid.uuid4()
    stage_id = uuid.uuid4()
    source = _stage("Applied", 0)
    source.id = stage_id
    next_stage = _stage("Screening", 1)

    # Empty applications list -> no update path triggered
    apps_query = MagicMock()
    apps_query.filter.return_value.all.return_value = []

    db = MagicMock()
    db.query.side_effect = [
        _make_query_chain(source),      # load source
        _make_query_chain(next_stage),  # resolve next stage by position+1
        _make_stages_query([source, next_stage]),  # all stages on job
        apps_query,                     # applications query
    ]

    result = execute_bulk_move(
        db, job_id, stage_id, min_score=70, target_stage_id=None
    )

    assert result.target_stage == {"id": str(next_stage.id), "name": "Screening"}
    assert result.moved == []
    assert result.skipped == []


def test_execute_bulk_move_dry_run_does_not_call_update():
    job_id = uuid.uuid4()
    stage_id = uuid.uuid4()
    source = _stage("Applied", 0)
    source.id = stage_id
    next_stage = _stage("Screening", 1)

    apps = [_app(90), _app(50)]
    apps_query = MagicMock()
    apps_query.filter.return_value.all.return_value = apps

    db = MagicMock()
    db.query.side_effect = [
        _make_query_chain(source),
        _make_query_chain(next_stage),
        _make_stages_query([source, next_stage]),
        apps_query,
    ]

    result = execute_bulk_move(
        db, job_id, stage_id, min_score=70, target_stage_id=None, dry_run=True
    )

    # One should be moved logically, one skipped.
    assert result.moved == [apps[0].id]
    assert len(result.skipped) == 1

    # No commit should have happened on dry_run.
    db.commit.assert_not_called()
    # Four reads: source, next-stage, all-stages, applications. No fifth for update.
    assert db.query.call_count == 4
