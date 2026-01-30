"""Command-line interface for Twinklr.

Note:
    This CLI uses synchronous wrappers around the async core.
    For async usage, see the async examples in the documentation.
    The underlying pipeline (v4.0) is fully async for better performance.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from rich.console import Console

from twinklr.core.config import configure_logging
from twinklr.core.sequencer.moving_heads.manager import MovingHeadManager
from twinklr.core.session import TwinklrSession

console = Console()


def run_pipeline(args: argparse.Namespace) -> None:
    """Run the full Twinklr pipeline.

    Note:
        This function uses synchronous wrappers. The underlying pipeline
        (audio analysis, metadata, lyrics) runs async internally.
    """
    audio_path = Path(args.audio).resolve()
    sequence_path = Path(args.xsq).resolve()

    # Create session from configs
    console.print("[bold]Initializing Twinklr session...[/bold]")
    session = TwinklrSession(
        app_config=Path(args.app_config),
        job_config=Path(args.config),
    )

    # Set project name if not configured
    if not session.job_config.project_name:
        session.job_config.project_name = (
            (sequence_path.stem or audio_path.stem or "TwinklrAI_Sequence")
            .lower()
            .replace(" ", "_")
        )

    # Update artifact directory
    artifact_dir = (
        Path(args.out).resolve() / session.app_config.output_dir / session.job_config.project_name
    )
    artifact_dir.mkdir(parents=True, exist_ok=True)
    console.print(f"[green]Artifact directory:[/green] {artifact_dir}")
    session.job_config.output_dir = str(artifact_dir)
    session.artifact_dir = artifact_dir

    # Determine output path
    xsq_out = artifact_dir / f"{session.job_config.project_name}_twinklr_mh.xsq"

    # Create domain manager and run pipeline
    console.print("[bold]Creating moving head manager...[/bold]")
    mh = MovingHeadManager(session)

    console.print("\n[bold cyan]Running Twinklr Pipeline[/bold cyan]")
    mh.run_pipeline(
        audio_path=str(audio_path),
        xsq_in=str(sequence_path),
        xsq_out=str(xsq_out),
    )

    console.print(f"\n[green]✓ Complete! Wrote:[/green] {xsq_out}")


def build_arg_parser() -> argparse.ArgumentParser:
    """Build argument parser for CLI."""
    p = argparse.ArgumentParser(
        prog="twinklr", description="Twinklr - AI-powered lighting sequencer for xLights"
    )
    sub = p.add_subparsers(dest="cmd", required=True)

    run = sub.add_parser("run", help="Run the full pipeline")
    run.add_argument("--audio", required=True, help="Path to audio file (mp3/wav)")
    run.add_argument("--xsq", required=True, help="Path to input .xsq")
    run.add_argument("--out", default=".", help="Output directory (default: current dir)")
    run.add_argument(
        "--app-config",
        default="config.json",
        help="Path to app config JSON (default: config.json)",
    )
    run.add_argument(
        "--config",
        required=True,
        help="Path to job config JSON settings",
    )
    run.add_argument(
        "--bin-s",
        type=float,
        default=1.0,
        help="Fingerprint bin size in seconds (default 1.0)",
    )

    generate = sub.add_parser(
        "generate", help="Generate sequence from existing plan (sequencer only)"
    )
    generate.add_argument("--plan", required=True, help="Path to plan JSON")
    generate.add_argument("--xsq-in", required=True, help="Path to input .xsq")
    generate.add_argument("--xsq-out", required=True, help="Path to output .xsq")
    generate.add_argument("--config", required=True, help="Path to job config JSON")

    return p


def main() -> None:
    """Main entry point for CLI."""
    # Configure logging from app config
    configure_logging()

    p = build_arg_parser()
    args = p.parse_args()

    run_pipeline(args)
