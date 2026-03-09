#!/usr/bin/env python3
"""Demo script for the recipe_builder pipeline.

Analyzes the real template catalog, identifies creative opportunities,
and generates new recipe candidates using an LLM (or deterministic
fallback with --dry-run).

Usage:
    uv run python scripts/demo_recipe_builder.py
    uv run python scripts/demo_recipe_builder.py --dry-run
    uv run python scripts/demo_recipe_builder.py --max-opportunities 5
    uv run python scripts/demo_recipe_builder.py --model gpt-4.1-mini --temperature 1.0
"""

from __future__ import annotations

import argparse
import json
import logging
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)-5s %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Demo the recipe_builder pipeline — catalog analysis + LLM generation.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--run-name",
        type=str,
        default="demo_run",
        help="Name for this demo run.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=ROOT / "data" / "recipe_builder",
        help="Root output directory for run artifacts.",
    )
    parser.add_argument(
        "--templates-dir",
        type=Path,
        default=None,
        help="Template catalog directory. Defaults to data/templates/.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Skip LLM calls; use deterministic fallback generation.",
    )
    parser.add_argument(
        "--max-opportunities",
        type=int,
        default=10,
        help="Maximum number of creative opportunities to generate for.",
    )
    parser.add_argument(
        "--model",
        type=str,
        default="gpt-4.1",
        help="LLM model for recipe generation.",
    )
    parser.add_argument(
        "--temperature",
        type=float,
        default=0.9,
        help="LLM sampling temperature (higher = more creative).",
    )
    parser.add_argument(
        "--promote",
        action="store_true",
        help="Promote staged recipes from a previous run into the template catalog.",
    )
    parser.add_argument(
        "--promote-from",
        type=Path,
        default=None,
        help="Run directory to promote from (defaults to output-dir/run-name).",
    )
    return parser.parse_args()


def _section(title: str) -> None:
    print(f"\n{'─' * 60}")
    print(f"  {title}")
    print(f"{'─' * 60}")


def main() -> int:
    args = parse_args()

    # Promote-only mode: skip the pipeline, just promote from a previous run
    if args.promote and args.promote_from:
        from twinklr.core.recipe_builder.pipeline import PipelineConfig

        config = PipelineConfig(
            run_name=args.run_name,
            output_dir=args.output_dir.resolve(),
            templates_dir=args.templates_dir.resolve() if args.templates_dir else None,
        )
        return _promote(args, config)

    print("=" * 60)
    print("  recipe_builder pipeline demo")
    print("=" * 60)
    print(f"  run_name          : {args.run_name}")
    print(f"  output_dir        : {args.output_dir}")
    print(f"  templates_dir     : {args.templates_dir or 'default (data/templates/)'}")
    print(f"  dry_run           : {args.dry_run}")
    print(f"  max_opportunities : {args.max_opportunities}")
    print(f"  model             : {args.model}")
    print(f"  temperature       : {args.temperature}")

    # Create LLM client (unless dry-run)
    llm_client = None
    if not args.dry_run:
        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key:
            print("\n  WARNING: OPENAI_API_KEY not set — falling back to deterministic mode")
            print("  Set OPENAI_API_KEY or use --dry-run for deterministic generation")
        else:
            from twinklr.core.api.llm.openai.client import create_client

            llm_client = create_client(api_key=api_key)
            print(f"  LLM client        : OpenAI ({args.model})")

    from twinklr.core.recipe_builder.pipeline import PipelineConfig, run_pipeline

    config = PipelineConfig(
        run_name=args.run_name,
        output_dir=args.output_dir.resolve(),
        templates_dir=args.templates_dir.resolve() if args.templates_dir else None,
        dry_run=args.dry_run,
        llm_client=llm_client,
        llm_model=args.model,
        llm_temperature=args.temperature,
        max_opportunities=args.max_opportunities,
    )

    manifest = run_pipeline(config)

    # Display results
    _section("Artifacts written")
    for name, path in manifest.artifact_paths.items():
        print(f"  {name:<35} {path}")

    _section("Phase status")
    for ps in manifest.phase_status:
        icon = {
            "completed": "✓",
            "skipped": "–",
            "failed": "✗",
            "not_started": " ",
        }.get(ps.status, "?")
        err = f"  ({ps.error})" if ps.error else ""
        print(f"  [{icon}] {ps.phase}{err}")

    m = manifest.summary_metrics
    _section("Metrics")
    print(f"  Catalog recipes    : {m.total_recipes_in_catalog}")
    print(f"  Opportunities      : {m.opportunities_identified}")
    print(f"  Recipe candidates  : {m.recipe_candidates_generated}")
    print(f"  Metadata candidates: {m.metadata_candidates_generated}")
    print(f"  Validation errors  : {m.validation_errors}")
    print(f"  Validation warnings: {m.validation_warnings}")
    print(f"  Accepted to stage  : {m.accepted_to_stage}")
    print(f"  Review required    : {m.review_required}")
    print(f"  Rejected           : {m.rejected}")

    # Show generated recipes
    staged_dir = Path(manifest.artifact_paths.get("staged_recipes", ""))
    if staged_dir.exists():
        staged_files = list(staged_dir.glob("*.json"))
        if staged_files:
            _section(f"Staged recipes ({len(staged_files)})")
            for f in staged_files:
                data = json.loads(f.read_text())
                effect_types = [layer.get("effect_type", "?") for layer in data.get("layers", [])]
                print(
                    f"  {data.get('name', '?'):<40} "
                    f"family={data.get('effect_family', '?'):<15} "
                    f"energy={data.get('style_markers', {}).get('energy_affinity', '?'):<6} "
                    f"layers={len(data.get('layers', []))} "
                    f"effects={', '.join(effect_types)}"
                )

    print()
    failed = [ps for ps in manifest.phase_status if ps.status == "failed"]
    if failed:
        print(f"WARNING: {len(failed)} phase(s) failed: {[ps.phase for ps in failed]}")
        return 1

    if not args.promote:
        print("Demo complete. Review staged artifacts in:")
        print(f"  {config.output_dir / config.run_name}")
        print("\nTo promote reviewed recipes into the catalog, re-run with --promote")
        return 0

    return _promote(args, config)


def _promote(args: argparse.Namespace, config: object) -> int:
    """Promote staged recipes into the template catalog."""
    from twinklr.core.recipe_builder.promotion import promote_staged_recipes

    promote_from = args.promote_from or (config.output_dir / config.run_name)
    staged_dir = promote_from / "staged_recipes"

    templates_dir = config.templates_dir or (ROOT / "data" / "templates")

    _section("Promoting staged recipes")
    print(f"  Source : {staged_dir}")
    print(f"  Target : {templates_dir}")

    staged_files = list(staged_dir.glob("*.json")) if staged_dir.exists() else []
    if not staged_files:
        print("\n  No staged recipes found — nothing to promote.")
        return 0

    print(f"  Found  : {len(staged_files)} staged recipe(s)")
    print()

    result = promote_staged_recipes(
        staged_dir=staged_dir,
        templates_dir=templates_dir,
    )

    if result.promoted_ids:
        print(f"  Promoted ({result.promoted}):")
        for rid in result.promoted_ids:
            print(f"    + {rid}")
    if result.skipped_ids:
        print(f"  Skipped ({result.skipped}):")
        for rid in result.skipped_ids:
            print(f"    - {rid}")

    print(f"\n  Index updated: {templates_dir / 'index.json'}")
    print("Promotion complete.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
