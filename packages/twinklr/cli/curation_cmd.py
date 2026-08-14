"""`twinklr review-staged-recipes` — interactive human admission sessions."""

from __future__ import annotations

import argparse
from datetime import UTC, datetime
from pathlib import Path

from rich.console import Console

from twinklr.core.recipe_builder.curation import (
    ReviewCandidate,
    format_review_candidate,
    run_curation_session,
)
from twinklr.core.recipe_builder.evidence import DEFAULT_TEMPLATES_DIR

console = Console()


def add_review_staged_recipes_subparser(
    sub: argparse._SubParsersAction[argparse.ArgumentParser],
) -> None:
    """Register the explicit human-admission session command."""
    command = sub.add_parser(
        "review-staged-recipes",
        help=(
            "Interactively admit or reject every staged recipe with a required reason; "
            "only admitted recipe IDs are promoted."
        ),
    )
    command.add_argument(
        "--run-dir",
        required=True,
        type=Path,
        help="Recipe-builder run directory containing generated candidates and admission artifacts.",
    )
    command.add_argument(
        "--staged-dir",
        type=Path,
        default=None,
        help="Staged recipe directory (default: <run-dir>/staged_recipes).",
    )
    command.add_argument(
        "--templates-dir",
        type=Path,
        default=None,
        help="Catalog templates directory (default: catalog/templates/).",
    )
    command.add_argument(
        "--session-id",
        default=None,
        help="Unique audit-log name (default: current UTC timestamp).",
    )


def _prompt_for_human_decision(candidate: ReviewCandidate) -> tuple[str, str]:
    console.print()
    console.print(format_review_candidate(candidate))
    decision = input("Human decision [admit/reject]: ")
    reason = input("Reason (required): ")
    return decision, reason


def run_review_staged_recipes_command(args: argparse.Namespace) -> int:
    """Run a human-only curation session and selectively promote its admitted recipes."""
    run_dir = args.run_dir.resolve()
    staged_dir = args.staged_dir.resolve() if args.staged_dir else run_dir / "staged_recipes"
    templates_dir = args.templates_dir.resolve() if args.templates_dir else DEFAULT_TEMPLATES_DIR
    session_id = args.session_id or datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    try:
        log, result, log_path = run_curation_session(
            run_dir=run_dir,
            staged_dir=staged_dir,
            templates_dir=templates_dir,
            decide=_prompt_for_human_decision,
            session_id=session_id,
        )
    except (EOFError, KeyboardInterrupt):
        console.print(
            "[yellow]Curation aborted: no session log was written and no recipes were "
            "promoted. Re-run the command to start a new session.[/yellow]"
        )
        return 130
    except (FileNotFoundError, FileExistsError, ValueError) as exc:
        console.print(f"[red]ERROR: {exc}[/red]")
        return 1

    console.print(f"[green]Session log:[/green] {log_path}")
    console.print(f"[green]Reviewed:[/green] {len(log.records)}")
    console.print(f"[green]Promoted ({result.promoted}):[/green] {result.promoted_ids}")
    if result.skipped_ids:
        console.print(f"[yellow]Not promoted ({result.skipped}):[/yellow] {result.skipped_ids}")
    return 0
