"""Promotion of staged recipes into the template catalog.

Copies reviewed staged recipe JSON files into the builtins directory
and registers them in index.json so they become part of the active
template catalog.
"""

from __future__ import annotations

import json
import logging
import shutil
from pathlib import Path
from typing import Any

from twinklr.core.recipe_builder.models import PromotionResult
from twinklr.core.sequencer.templates.group.recipe import EffectRecipe

logger = logging.getLogger(__name__)


def _load_index(templates_dir: Path) -> dict[str, Any]:
    """Load the current index.json from the templates directory."""
    index_path = templates_dir / "index.json"
    if not index_path.exists():
        return {"schema_version": "template-index.v1", "total": 0, "entries": []}
    result: dict[str, Any] = json.loads(index_path.read_text(encoding="utf-8"))
    return result


def _write_index(templates_dir: Path, index: dict[str, Any]) -> None:
    """Write the updated index.json back to disk."""
    index["total"] = len(index["entries"])
    index_path = templates_dir / "index.json"
    index_path.write_text(json.dumps(index, indent=2) + "\n", encoding="utf-8")


def _index_entry_from_recipe(recipe: EffectRecipe, filename: str) -> dict:
    """Build an index.json entry from an EffectRecipe."""
    return {
        "recipe_id": recipe.recipe_id,
        "name": recipe.name,
        "template_type": recipe.template_type.value,
        "visual_intent": recipe.visual_intent.value,
        "tags": list(recipe.tags),
        "source": recipe.provenance.source,
        "file": f"builtins/{filename}",
    }


def promote_staged_recipes(
    *,
    staged_dir: Path,
    templates_dir: Path,
) -> PromotionResult:
    """Promote staged recipes into builtins/ and register in index.json.

    Reads each JSON file from ``staged_dir``, validates it as an
    ``EffectRecipe``, copies it to ``templates_dir/builtins/``, and
    appends an entry to ``templates_dir/index.json``.

    Recipes whose ``recipe_id`` already appears in the index are
    skipped. Invalid JSON files are also skipped with a warning.

    Args:
        staged_dir: Directory containing staged recipe JSON files.
        templates_dir: Root templates directory (contains ``index.json``
            and ``builtins/`` subdirectory).

    Returns:
        PromotionResult with counts and IDs.

    Raises:
        FileNotFoundError: If ``staged_dir`` does not exist.
    """
    if not staged_dir.exists():
        raise FileNotFoundError(f"Staged directory not found: {staged_dir}")

    builtins_dir = templates_dir / "builtins"
    builtins_dir.mkdir(parents=True, exist_ok=True)

    index = _load_index(templates_dir)
    existing_ids = {e["recipe_id"] for e in index["entries"]}

    promoted_ids: list[str] = []
    skipped_ids: list[str] = []

    staged_files = sorted(staged_dir.glob("*.json"))
    if not staged_files:
        logger.info("No staged recipes found in %s", staged_dir)
        return PromotionResult()

    for staged_file in staged_files:
        stem = staged_file.stem
        try:
            data = json.loads(staged_file.read_text(encoding="utf-8"))
            recipe = EffectRecipe.model_validate(data)
        except Exception:
            logger.warning("Skipping invalid recipe file: %s", staged_file.name)
            skipped_ids.append(stem)
            continue

        if recipe.recipe_id in existing_ids:
            logger.info(
                "Skipping %s — already in index", recipe.recipe_id,
            )
            skipped_ids.append(recipe.recipe_id)
            continue

        dest = builtins_dir / staged_file.name
        shutil.copy2(staged_file, dest)

        entry = _index_entry_from_recipe(recipe, staged_file.name)
        index["entries"].append(entry)
        existing_ids.add(recipe.recipe_id)
        promoted_ids.append(recipe.recipe_id)

        logger.info("Promoted %s → %s", recipe.recipe_id, dest)

    _write_index(templates_dir, index)

    result = PromotionResult(
        promoted=len(promoted_ids),
        skipped=len(skipped_ids),
        promoted_ids=promoted_ids,
        skipped_ids=skipped_ids,
    )
    logger.info(
        "Promotion complete: %d promoted, %d skipped",
        result.promoted,
        result.skipped,
    )
    return result
