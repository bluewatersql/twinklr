"""Headless CLI entry point for deterministic FSEQ comparisons."""

from __future__ import annotations

from pathlib import Path

from rich.console import Console

from twinklr.core.api.xlights import compare_fseqs

console = Console()


def run_fseqcmp_command(expected_path: Path, actual_path: Path) -> int:
    """Compare two FSEQ files and return a CI-standard success/failure exit code."""
    for label, path in (("Expected", expected_path), ("Actual", actual_path)):
        if not path.is_file():
            console.print(f"[red]ERROR:[/red] {label} FSEQ file not found: {path}")
            return 2
    comparison = compare_fseqs(expected_path, actual_path)
    style = "green" if comparison.equal else "red"
    console.print(f"[{style}]{comparison.summary}[/{style}]")
    return 0 if comparison.equal else 1
