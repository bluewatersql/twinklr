#!/usr/bin/env python3
"""Evaluate recipe dictionary quality from a feature engineering run.

Reports:
- Total promoted recipes
- Lane/type distribution (BASE, RHYTHM, ACCENT)
- Family coverage (distinct effect families across layers)
- Average layer count
- Stack-signature coverage (recipes with multi-layer stack provenance)

Usage:
    uv run python scripts/evaluate_recipe_dictionary.py
    uv run python scripts/evaluate_recipe_dictionary.py --fe-dir data/features/feature_engineering
    uv run python scripts/evaluate_recipe_dictionary.py --format json
"""

from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path
import sys
from typing import Any

from twinklr.core.sequencer.templates.group.recipe import EffectRecipe

_DEFAULT_FE_DIR = Path("data/features/feature_engineering")
_RECIPE_CATALOG_FILE = "recipe_catalog.json"


def _load_recipes(fe_dir: Path) -> list[EffectRecipe]:
    """Load promoted recipes from the recipe catalog artifact."""
    catalog_path = fe_dir / _RECIPE_CATALOG_FILE
    if not catalog_path.exists():
        print(f"ERROR: Recipe catalog not found at {catalog_path}", file=sys.stderr)
        sys.exit(1)

    data = json.loads(catalog_path.read_text(encoding="utf-8"))
    recipes_raw: list[dict[str, Any]]
    if isinstance(data, list):
        recipes_raw = data
    elif isinstance(data, dict) and "recipes" in data:
        recipes_raw = data["recipes"]
    else:
        print(f"ERROR: Unexpected format in {catalog_path}", file=sys.stderr)
        sys.exit(1)

    return [EffectRecipe.model_validate(r) for r in recipes_raw]


def evaluate(recipes: list[EffectRecipe]) -> dict[str, Any]:
    """Compute quality metrics for a recipe dictionary.

    Args:
        recipes: List of promoted EffectRecipe instances.

    Returns:
        Dictionary of metric name to value.
    """
    total = len(recipes)

    # Lane distribution
    lane_counts: Counter[str] = Counter()
    for r in recipes:
        lane_counts[r.template_type.value] += 1

    # Family coverage: distinct effect families across all layers
    families: set[str] = set()
    for r in recipes:
        for layer in r.layers:
            families.add(layer.effect_type.lower().replace(" ", "_"))

    # Average layer count
    layer_counts = [len(r.layers) for r in recipes]
    avg_layers = sum(layer_counts) / total if total > 0 else 0.0

    # Stack-signature coverage: recipes with > 1 layer from stack synthesis
    stack_recipes = [r for r in recipes if len(r.layers) > 1 and r.provenance.source == "mined"]
    stack_coverage = len(stack_recipes) / total if total > 0 else 0.0

    # Unresolved clusters (recipes with no model affinities as a proxy)
    no_affinity_count = sum(1 for r in recipes if not r.model_affinities)

    return {
        "total_promoted_recipes": total,
        "lane_distribution": dict(lane_counts.most_common()),
        "distinct_effect_families": len(families),
        "effect_families": sorted(families),
        "average_layer_count": round(avg_layers, 2),
        "stack_signature_count": len(stack_recipes),
        "stack_signature_coverage": round(stack_coverage, 4),
        "recipes_without_model_affinity": no_affinity_count,
    }


def _print_human(metrics: dict[str, Any]) -> None:
    """Print metrics in human-readable format."""
    bar = "=" * 60
    print(f"\n{bar}")
    print("  Recipe Dictionary Evaluation Report")
    print(bar)
    print(f"  Total promoted recipes:        {metrics['total_promoted_recipes']}")
    print()
    print("  Lane distribution:")
    for lane, count in metrics["lane_distribution"].items():
        print(f"    {lane:20s} {count}")
    print()
    print(f"  Distinct effect families:      {metrics['distinct_effect_families']}")
    print(f"  Average layer count:           {metrics['average_layer_count']}")
    print(f"  Stack-signature recipes:       {metrics['stack_signature_count']}")
    print(f"  Stack-signature coverage:      {metrics['stack_signature_coverage']:.1%}")
    print(f"  Recipes w/o model affinity:    {metrics['recipes_without_model_affinity']}")
    print()
    print("  Effect families:")
    for fam in metrics["effect_families"]:
        print(f"    - {fam}")
    print(bar)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Evaluate recipe dictionary quality.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--fe-dir",
        type=Path,
        default=_DEFAULT_FE_DIR,
        help=f"Feature engineering output directory (default: {_DEFAULT_FE_DIR}).",
    )
    parser.add_argument(
        "--format",
        choices=["human", "json"],
        default="human",
        help="Output format (default: human).",
    )
    args = parser.parse_args()

    recipes = _load_recipes(args.fe_dir)
    metrics = evaluate(recipes)

    if args.format == "json":
        print(json.dumps(metrics, indent=2))
    else:
        _print_human(metrics)


if __name__ == "__main__":
    main()
