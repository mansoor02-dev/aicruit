"""Immutable dataset repository (no shared mutable state).

Question selection used to rely on ``QuestionGenerator.used_question_ids``,
a process-wide set shared by every interview on a worker. Selection is now
stateless per request: callers compute ``exclude_ids`` from the request's own
history (matching history ``Q`` text against dataset questions after
stripping the conversational prefix) and pass it in. The repository itself
never mutates, so it is thread-safe to share across requests.
"""

from __future__ import annotations

import csv
import logging
import random
from pathlib import Path
from typing import Any

from app.services.text import strip_conversational_prefix

logger = logging.getLogger(__name__)


class DatasetRepository:
    """Read-only wrapper around the CSV question bank rows."""

    def __init__(self, rows: list[dict[str, Any]]):
        self._rows: tuple[dict[str, Any], ...] = tuple(rows)

    @classmethod
    def load_csv(cls, path: str | Path) -> "DatasetRepository":
        """Load ``Id,Question,Answer,Category,Difficulty`` rows (latin1)."""
        dataset_path = Path(path)
        with dataset_path.open(newline="", encoding="latin1") as dataset_file:
            rows = list(csv.DictReader(dataset_file))
        logger.info("Dataset loaded: %s questions", len(rows))
        return cls(rows)

    def __len__(self) -> int:
        return len(self._rows)

    @staticmethod
    def _text(row: dict[str, Any]) -> str:
        return row.get("Question") or row.get("question", "")

    def derive_exclude_ids(
        self, previous_qa: list[dict[str, Any]] | None
    ) -> set[Any]:
        """Ids of dataset questions already asked in this request's history."""
        if not previous_qa:
            return set()
        # Map normalised dataset question text -> Id.
        by_text = {self._text(row).strip(): row.get("Id") for row in self._rows}
        exclude: set[Any] = set()
        for qa in previous_qa:
            asked = strip_conversational_prefix(
                str(qa.get("Q", "") or "").strip()
            )
            match = by_text.get(asked)
            if match is not None:
                exclude.add(match)
        return exclude

    def pick_question(
        self,
        topics_covered: list[str] | None = None,
        difficulty: str = "medium",
        category: str | None = None,
        exclude_ids: set[Any] | None = None,
        rng: random.Random | None = None,
    ) -> dict[str, Any]:
        """Select a question, progressively relaxing constraints.

        Mirrors the previous selection order: category filter with full-dataset
        fallback; difficulty and unused; relax unused if <3; relax difficulty;
        last resort. Prefers rows whose category is not among the last 3
        covered topics. Pure: never records the selection anywhere.
        """
        topics_covered = topics_covered or []
        exclude_ids = exclude_ids or set()
        rng = rng or random
        difficulty = (difficulty or "medium").lower()

        if category:
            base = [
                row
                for row in self._rows
                if str(row.get("Category", "")).lower() == category.lower()
            ] or list(self._rows)
        else:
            base = list(self._rows)

        if not base:
            raise ValueError("The question dataset is empty")

        pool = [
            row
            for row in base
            if str(row.get("Difficulty", "")).lower() == difficulty
            and row.get("Id") not in exclude_ids
        ]
        if len(pool) < 3:
            pool = [
                row
                for row in base
                if str(row.get("Difficulty", "")).lower() == difficulty
            ]
        if not pool:
            pool = [
                row for row in base if row.get("Id") not in exclude_ids
            ]
        if not pool:
            pool = base

        recent_topics = set(topics_covered[-3:])
        fresh = [row for row in pool if row.get("Category") not in recent_topics]
        return rng.choice(fresh if fresh else pool)
