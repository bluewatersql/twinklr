"""CLI commands for moving-head template data documents."""

from __future__ import annotations

import argparse
from pathlib import Path

from rich.console import Console

from twinklr.core.sequencer.moving_heads.templates import load_builtin_templates
from twinklr.core.sequencer.moving_heads.templates.converter import export_registry
from twinklr.core.sequencer.moving_heads.templates.data_loader import (
    load_templates_from_directory,
)
from twinklr.core.sequencer.moving_heads.templates.library import TemplateRegistry

console = Console()


def add_template_subparsers(subparsers: argparse._SubParsersAction) -> None:
    """Register moving-head template conversion and validation commands."""
    export = subparsers.add_parser(
        "template-export",
        help="Export registered Python moving-head templates as strict JSON",
    )
    export.add_argument("--out", type=Path, required=True, help="Output directory")
    export.add_argument(
        "--template-id",
        action="append",
        default=None,
        help="Export only this template id (repeatable; default: all)",
    )
    export.add_argument(
        "--force",
        action="store_true",
        help="Overwrite existing JSON documents",
    )

    validate = subparsers.add_parser(
        "template-validate",
        help="Validate and lint strict JSON moving-head templates",
    )
    validate.add_argument("--template-dir", type=Path, required=True, help="Template directory")


def run_template_export_command(args: argparse.Namespace) -> int:
    """Export selected registered builtins to deterministic JSON files."""
    try:
        load_builtin_templates()
        written = export_registry(
            args.out.resolve(),
            template_ids=args.template_id,
            overwrite=args.force,
        )
    except (OSError, KeyError, ValueError) as error:
        console.print(f"[red]ERROR: {error}[/red]")
        return 1

    console.print(f"[green]Exported {len(written)} template document(s) to {args.out}[/green]")
    return 0


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
