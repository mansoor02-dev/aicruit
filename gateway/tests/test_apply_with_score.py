"""Unit tests for the AI match score lookup used by apply_to_job (Wave 2 Slice D)."""
from unittest.mock import MagicMock
from uuid import uuid4

from app.routes.job import _resolve_ai_match_score


def test_resolve_returns_overall_when_row_exists():
    fake_row = MagicMock(overall=72)
    db = MagicMock()
    db.query.return_value.filter_by.return_value.first.return_value = fake_row

    result = _resolve_ai_match_score(db, uuid4(), uuid4())

    assert result == 72


def test_resolve_returns_none_when_no_row():
    db = MagicMock()
    db.query.return_value.filter_by.return_value.first.return_value = None

    result = _resolve_ai_match_score(db, uuid4(), uuid4())

    assert result is None
