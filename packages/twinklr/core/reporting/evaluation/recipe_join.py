"""Strict recipe-to-completed-show evaluation join."""

from __future__ import annotations

from pathlib import Path

from twinklr.core.reporting.evaluation.show_record import (
    ShowEvaluationRecord,
    load_show_evaluation_record,
)


def evaluations_for_recipe(
    recipe_id: str,
    record_paths: list[Path],
) -> list[tuple[Path, ShowEvaluationRecord]]:
    """Return completed records using a recipe; invalid records fail the whole query."""
    if not recipe_id.strip():
        raise ValueError("recipe_id must be non-empty")
    matches = []
    for path in sorted(record_paths):
        record = load_show_evaluation_record(path)
        if recipe_id in record.deterministic.recipe_ids:
            matches.append((path, record))
    return matches


__all__ = ["evaluations_for_recipe"]
