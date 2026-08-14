"""`twinklr curate-catalog` — CLI wrapper around the recipe_builder pipeline.

Promotes recipe_builder's curation workflow (analysis -> generation ->
enrichment -> validation -> admission, then an explicit ``--promote`` step)
from the standalone ``scripts/demo_recipe_builder.py`` script to a
first-class ``twinklr`` subcommand. Behavior is unchanged from the script —
same pipeline, same staged-only default, same explicit promotion gate —
only the entry point moved.
"""

from __future__ import annotations

import argparse
import logging
import os
from pathlib import Path
from typing import TYPE_CHECKING

from rich.console import Console

if TYPE_CHECKING:
    from twinklr.core.recipe_builder.pipeline import PipelineConfig

console = Console()
logger = logging.getLogger(__name__)


def add_curate_catalog_subparser(
    sub: argparse._SubParsersAction[argparse.ArgumentParser],
) -> None:
    """Register the ``curate-catalog`` subcommand on ``sub``."""
    from twinklr.core.config.models import AgentOrchestrationConfig

    generation_defaults = AgentOrchestrationConfig().recipe_generation_agent
    cmd = sub.add_parser(
        "curate-catalog",
        help=(
            "Run the recipe_builder catalog-curation pipeline (analysis -> generation -> "
            "enrichment -> validation -> admission). Outputs are staged only; pass "
            "--promote to merge reviewed staged recipes into the template catalog."
        ),
    )
    cmd.add_argument("--run-name", default="curate_run", help="Name for this run.")
    cmd.add_argument(
        "--output-dir",
        type=Path,
        default=Path("data/recipe_builder"),
        help="Root output directory for run artifacts (default: data/recipe_builder).",
    )
    cmd.add_argument(
        "--templates-dir",
        type=Path,
        default=None,
        help="Template catalog directory (default: catalog/templates/).",
    )
    cmd.add_argument(
        "--fe-dir",
        type=Path,
        default=None,
        help="Feature-engineering artifact directory (default: data/features/feature_engineering/).",
    )
    cmd.add_argument(
        "--coverage-report",
        type=Path,
        default=None,
        help=(
            "P2K-T1 catalog-coverage JSON report. Its gap cells are added to the "
            "generation opportunities."
        ),
    )
    cmd.add_argument(
        "--dry-run",
        action="store_true",
        help="Skip LLM calls; use deterministic fallback generation.",
    )
    cmd.add_argument(
        "--synthetic-fallback",
        action="store_true",
        help="Allow synthetic inputs when FE artifacts are missing.",
    )

    boot_group = cmd.add_mutually_exclusive_group()
    boot_group.add_argument(
        "--bootstrap",
        dest="enable_bootstrap",
        action="store_true",
        default=True,
        help="Enable new recipe generation (default).",
    )
    boot_group.add_argument(
        "--no-bootstrap",
        dest="enable_bootstrap",
        action="store_false",
        help="Disable new recipe generation.",
    )

    enrich_group = cmd.add_mutually_exclusive_group()
    enrich_group.add_argument(
        "--enrich",
        dest="enable_enrich",
        action="store_true",
        default=True,
        help="Enable metadata-only enrichment (default).",
    )
    enrich_group.add_argument(
        "--no-enrich",
        dest="enable_enrich",
        action="store_false",
        help="Disable metadata-only enrichment.",
    )

    cmd.add_argument(
        "--phase",
        default="all",
        choices=["all", "analysis", "generation", "enrichment", "validation", "admission"],
        help="Run a specific pipeline phase, or 'all' (default: all).",
    )
    cmd.add_argument(
        "--max-opportunities",
        type=int,
        default=10,
        help="Maximum number of creative opportunities to generate for (default: 10).",
    )
    cmd.add_argument(
        "--model",
        default=generation_defaults.model,
        help=f"LLM model for recipe generation (default: {generation_defaults.model}).",
    )
    cmd.add_argument(
        "--temperature",
        type=float,
        default=generation_defaults.temperature,
        help=(
            "LLM sampling temperature; higher is more creative "
            f"(default: {generation_defaults.temperature})."
        ),
    )
    cmd.add_argument(
        "--reasoning-effort",
        choices=["low", "medium", "high"],
        default=generation_defaults.reasoning_effort,
        help=(
            "Explicit reasoning effort for recipe generation "
            f"(default: {generation_defaults.reasoning_effort})."
        ),
    )
    cmd.add_argument(
        "--promote",
        action="store_true",
        help="Promote staged recipes from this run (or --promote-from) into the template catalog.",
    )
    cmd.add_argument(
        "--promote-from",
        type=Path,
        default=None,
        help=(
            "Run directory to promote from, skipping the pipeline entirely "
            "(default: <output-dir>/<run-name>)."
        ),
    )


def run_curate_catalog_command(args: argparse.Namespace) -> int:
    """Execute the ``curate-catalog`` subcommand. Returns a process exit code."""
    from twinklr.core.recipe_builder.pipeline import PipelineConfig

    output_dir = args.output_dir.resolve()
    templates_dir = args.templates_dir.resolve() if args.templates_dir else None

    # Promote-only mode: skip the pipeline, just promote from a previous run.
    if args.promote and args.promote_from:
        config = PipelineConfig(
            run_name=args.run_name,
            output_dir=output_dir,
            templates_dir=templates_dir,
        )
        return _promote(args, config)

    llm_provider = None
    if not args.dry_run:
        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key:
            console.print(
                "[yellow]WARNING: OPENAI_API_KEY not set — falling back to deterministic "
                "mode. Set OPENAI_API_KEY or pass --dry-run for deterministic generation.[/yellow]"
            )
        else:
            from pydantic import SecretStr

            from twinklr.core.agents.providers.factory import create_llm_provider
            from twinklr.core.config.models import AppConfig

            app_config = AppConfig(llm_api_key=SecretStr(api_key))
            llm_provider = create_llm_provider(app_config, session_id=args.run_name)

    from twinklr.core.config.models import AgentConfig, AgentOrchestrationConfig
    from twinklr.core.recipe_builder.pipeline import ALL_PHASES, run_pipeline

    phases: tuple[str, ...] = ALL_PHASES if args.phase == "all" else (args.phase,)
    generation_defaults = AgentOrchestrationConfig().recipe_generation_agent

    config = PipelineConfig(
        run_name=args.run_name,
        output_dir=output_dir,
        templates_dir=templates_dir,
        fe_dir=args.fe_dir.resolve() if args.fe_dir else None,
        coverage_report_path=(
            args.coverage_report.resolve() if args.coverage_report is not None else None
        ),
        enable_bootstrap=args.enable_bootstrap,
        enable_enrich=args.enable_enrich,
        synthetic_fallback=args.synthetic_fallback,
        dry_run=args.dry_run,
        llm_provider=llm_provider,
        generation_agent=AgentConfig(
            model=args.model,
            temperature=args.temperature,
            reasoning_effort=getattr(
                args, "reasoning_effort", generation_defaults.reasoning_effort
            ),
            max_tokens=generation_defaults.max_tokens,
            timeout_seconds=generation_defaults.timeout_seconds,
        ),
        max_opportunities=args.max_opportunities,
        phases=phases,
    )

    manifest = run_pipeline(config)

    failed = [ps for ps in manifest.phase_status if ps.status == "failed"]
    if failed:
        console.print(f"[red]{len(failed)} phase(s) failed: {[ps.phase for ps in failed]}[/red]")
        return 1

    if not args.promote:
        console.print(
            "[green]Run complete.[/green] Review staged artifacts in "
            f"{config.output_dir / config.run_name}, then re-run with --promote to merge "
            "reviewed recipes into the template catalog."
        )
        return 0

    return _promote(args, config)


def _promote(args: argparse.Namespace, config: PipelineConfig) -> int:
    """Promote staged recipes from a completed run into the template catalog."""
    from twinklr.core.recipe_builder.evidence import DEFAULT_TEMPLATES_DIR
    from twinklr.core.recipe_builder.promotion import promote_staged_recipes

    promote_from = args.promote_from or (config.output_dir / config.run_name)
    staged_dir = promote_from / "staged_recipes"
    templates_dir = config.templates_dir or DEFAULT_TEMPLATES_DIR

    staged_files = list(staged_dir.glob("*.json")) if staged_dir.exists() else []
    if not staged_files:
        console.print("[yellow]No staged recipes found — nothing to promote.[/yellow]")
        return 0

    result = promote_staged_recipes(staged_dir=staged_dir, templates_dir=templates_dir)

    if result.promoted_ids:
        console.print(f"[green]Promoted ({result.promoted}):[/green] {result.promoted_ids}")
    if result.skipped_ids:
        console.print(f"[yellow]Skipped ({result.skipped}):[/yellow] {result.skipped_ids}")
    console.print(f"Index updated: {templates_dir / 'index.json'}")
    return 0
