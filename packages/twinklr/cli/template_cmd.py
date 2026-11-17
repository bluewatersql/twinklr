"""CLI commands for moving-head template data documents."""

from __future__ import annotations

import argparse
from pathlib import Path

from rich.console import Console

from twinklr.core.sequencer.moving_heads.templates.data_loader import (
    load_templates_from_directory,
)
from twinklr.core.sequencer.moving_heads.templates.library import TemplateRegistry

console = Console()


def add_template_subparsers(subparsers: argparse._SubParsersAction) -> None:
    """Register the moving-head template validation command."""
    validate = subparsers.add_parser(
        "template-validate",
        help="Validate and lint strict JSON moving-head templates",
    )
    validate.add_argument("--template-dir", type=Path, required=True, help="Template directory")


def run_template_validate_command(args: argparse.Namespace) -> int:
    """Validate every data template in an isolated registry."""
    try:
        registered = load_templates_from_directory(
            args.template_dir.resolve(),
            registry=TemplateRegistry(),
        )
    except (OSError, ValueError) as error:
        console.print(f"[red]ERROR: {error}[/red]")
        return 1

    console.print(
        f"[green]Validated {len(registered)} template document(s) from {args.template_dir}[/green]"
    )
    return 0
