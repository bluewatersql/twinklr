#!/usr/bin/env python3
"""Enrich builtin group templates with real xLights effect types and params.

For each template in data/templates/builtins/:
1. Resolves the effect type via effect_map.resolve_effect_type(recipe_id)
2. Replaces placeholder layer effect_type values with the resolved xLights type
3. Populates layer params from effect_map presets (in ParamValue format)
4. Writes the enriched template back

This script is idempotent: running it twice produces the same result.

Usage:
    uv run python scripts/enrich_builtin_templates.py
    uv run python scripts/enrich_builtin_templates.py --dry-run
"""

from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path
import sys
from typing import Any

# Ensure packages are importable
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "packages"))

from twinklr.core.sequencer.display.templates.effect_map import resolve_effect_type

logger = logging.getLogger(__name__)

# Placeholder effect_type values that need resolution
PLACEHOLDERS = frozenset(
    {"ABSTRACT", "GEOMETRIC", "IMAGERY", "TEXTURE", "HYBRID", "ORGANIC", "PLACEHOLDER"}
)

_PROJECT_ROOT = Path(__file__).resolve().parents[1]
_BUILTINS_DIR = _PROJECT_ROOT / "data" / "templates" / "builtins"
_INDEX_PATH = _PROJECT_ROOT / "data" / "templates" / "index.json"


def _to_param_value(value: Any) -> dict[str, Any]:
    """Convert a plain value to ParamValue format: {\"value\": X}.

    Args:
        value: Raw parameter value.

    Returns:
        Dict in ParamValue schema format.
    """
    return {"value": value}


# Fallback params for effects that have no presets in _EFFECT_PRESETS
_EFFECT_FALLBACK_PARAMS: dict[str, dict[str, Any]] = {
    "Pictures": {
        "movement": _to_param_value("none"),
        "speed": _to_param_value(10),
    },
    "On": {
        "_preset": _to_param_value("default"),
    },
}


def enrich_template(data: dict[str, Any]) -> tuple[dict[str, Any], int]:
    """Enrich a single template's layers with resolved effect types and params.

    Args:
        data: Raw template JSON dict.

    Returns:
        Tuple of (enriched data dict, number of layers modified).
    """
    recipe_id = data["recipe_id"]
    resolved = resolve_effect_type(recipe_id)
    changed = False

    layers = data.get("layers", [])
    enriched_layers: list[dict[str, Any]] = []

    for layer in layers:
        layer = dict(layer)  # shallow copy
        current_type = layer.get("effect_type", "")

        # Replace placeholder or mismatched effect types
        if current_type in PLACEHOLDERS or current_type != resolved.effect_type:
            layer["effect_type"] = resolved.effect_type
            changed = True

        # Populate params from presets if currently empty
        if not layer.get("params") and resolved.defaults:
            layer["params"] = {key: _to_param_value(val) for key, val in resolved.defaults.items()}
            changed = True
        elif not layer.get("params") and not resolved.defaults:
            # No presets available -- provide a minimal fallback param
            # so every template has at least one populated param
            layer["params"] = _EFFECT_FALLBACK_PARAMS.get(
                resolved.effect_type,
                {"_preset": _to_param_value("default")},
            )
            changed = True
        elif layer.get("params"):
            # Already has params -- ensure they're in ParamValue format
            new_params: dict[str, Any] = {}
            for key, val in layer["params"].items():
                if isinstance(val, dict) and "value" in val:
                    new_params[key] = val  # already ParamValue
                else:
                    new_params[key] = _to_param_value(val)
                    changed = True
            layer["params"] = new_params

        enriched_layers.append(layer)

    data = dict(data)
    data["layers"] = enriched_layers
    return data, 1 if changed else 0


def regenerate_index(builtins_dir: Path, index_path: Path) -> int:
    """Regenerate the template index.json from the builtin files.

    Args:
        builtins_dir: Path to builtins/ directory.
        index_path: Path to write index.json.

    Returns:
        Total number of entries in the index.
    """
    entries: list[dict[str, Any]] = []

    for path in sorted(builtins_dir.glob("*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        entries.append(
            {
                "recipe_id": data["recipe_id"],
                "name": data["name"],
                "template_type": data["template_type"],
                "visual_intent": data["visual_intent"],
                "tags": data.get("tags", []),
                "source": data.get("provenance", {}).get("source", "builtin"),
                "file": f"builtins/{path.name}",
            }
        )

    index = {
        "schema_version": "template-index.v1",
        "total": len(entries),
        "entries": entries,
    }

    index_path.write_text(
        json.dumps(index, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return len(entries)


def main() -> None:
    parser = argparse.ArgumentParser(description="Enrich builtin templates.")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print what would change without writing files.",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Enable verbose logging.",
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(levelname)s: %(message)s",
    )

    if not _BUILTINS_DIR.exists():
        logger.error("Builtins directory not found: %s", _BUILTINS_DIR)
        sys.exit(1)

    files = sorted(_BUILTINS_DIR.glob("*.json"))
    logger.info("Found %d builtin templates in %s", len(files), _BUILTINS_DIR)

    total_modified = 0
    for path in files:
        data = json.loads(path.read_text(encoding="utf-8"))
        enriched, modified = enrich_template(data)

        if modified > 0:
            total_modified += 1
            logger.debug("Enriched %s (%d layers modified)", path.stem, modified)

            if not args.dry_run:
                path.write_text(
                    json.dumps(enriched, indent=2, ensure_ascii=False) + "\n",
                    encoding="utf-8",
                )

    logger.info(
        "Enriched %d/%d templates%s",
        total_modified,
        len(files),
        " (dry run)" if args.dry_run else "",
    )

    # Regenerate index
    if not args.dry_run:
        count = regenerate_index(_BUILTINS_DIR, _INDEX_PATH)
        logger.info("Regenerated index.json with %d entries", count)
    else:
        logger.info("Skipping index regeneration (dry run)")


if __name__ == "__main__":
    main()
