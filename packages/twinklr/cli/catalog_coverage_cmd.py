"""`twinklr catalog-coverage` — report recipe coverage for an xLights layout."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from rich.console import Console

from twinklr.core.recipe_builder.coverage import (
    build_catalog_coverage_report,
    format_coverage_table,
)

console = Console()


def add_catalog_coverage_subparser(
    sub: argparse._SubParsersAction[argparse.ArgumentParser],
) -> None:
    """Register the read-only ``catalog-coverage`` subcommand."""
    cmd = sub.add_parser(
        "catalog-coverage",
        help="Report BASE/RHYTHM/ACCENT catalog coverage for an xLights layout.",
    )
    cmd.add_argument("--layout", type=Path, required=True, help="Path to rgbeffects.xml.")
    cmd.add_argument(
        "--catalog-dir",
        type=Path,
        default=None,
        help="Tracked catalog directory (default: catalog/templates/).",
    )
    cmd.add_argument(
        "--out",
        type=Path,
        default=None,
        help="Write the machine-readable JSON report to this path; table remains on stdout.",
    )


def run_catalog_coverage_command(args: argparse.Namespace) -> int:
    """Run the coverage report without changing the catalog or layout."""
    layout_path = args.layout.resolve()
    if not layout_path.exists():
        console.print(f"[red]ERROR: Layout file not found: {layout_path}[/red]")
        return 1

    catalog_dir = args.catalog_dir.resolve() if args.catalog_dir else None
    if catalog_dir is not None and not catalog_dir.exists():
        console.print(f"[red]ERROR: Catalog directory not found: {catalog_dir}[/red]")
        return 1

    report = build_catalog_coverage_report(layout_path=layout_path, catalog_dir=catalog_dir)
    console.print(format_coverage_table(report))
    if args.out is not None:
        output_path = args.out.resolve()
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(report.to_dict(), indent=2) + "\n", encoding="utf-8")
        console.print(f"[green]JSON report:[/green] {output_path}")
    else:
        console.print_json(json.dumps(report.to_dict()))
    return 0
