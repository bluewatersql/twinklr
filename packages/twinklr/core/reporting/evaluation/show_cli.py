"""Offline-only show-evaluation command."""

from __future__ import annotations

import argparse
from pathlib import Path

from twinklr.core.reporting.evaluation.show_record import (
    build_deterministic_report,
    write_deterministic_report,
)


def add_show_eval_subparser(subparsers: argparse._SubParsersAction) -> None:
    """Register the provider-free deterministic show evaluator."""
    parser = subparsers.add_parser(
        "show-eval",
        help="Compute deterministic metrics from a show evaluation manifest",
    )
    parser.add_argument("manifest", help="Path to a strict show evaluation manifest")
    parser.add_argument("--out", required=True, help="Output JSON report path")


def run_show_eval_command(args: argparse.Namespace) -> int:
    """Run with file parsing and deterministic math only."""
    manifest_path = Path(args.manifest).resolve()
    if not manifest_path.is_file():
        raise ValueError(f"show evaluation manifest not found: {manifest_path}")
    report = build_deterministic_report(manifest_path)
    write_deterministic_report(report, Path(args.out).resolve())
    return 0


__all__ = ["add_show_eval_subparser", "run_show_eval_command"]
