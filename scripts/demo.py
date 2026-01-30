"""Demo script for Twinklr pipeline.

Note:
    This demo uses synchronous wrappers around the async core (v4.0).
    The underlying audio analysis, metadata extraction, and lyrics resolution
    all run async internally for better performance.
"""

from __future__ import annotations

import logging
from pathlib import Path
import shutil

from rich.console import Console

from twinklr.core.sequencer.moving_heads.manager import MovingHeadManager
from twinklr.core.session import TwinklrSession
from twinklr.core.utils.logging import configure_logging

configure_logging(level="DEBUG")
logger = logging.getLogger(__name__)

console = Console()

mp3_path = "data/music/Need A Favor.mp3"
xsq_path = "data/sequences/Need A Favor.xsq"


def _default_repo_root() -> Path:
    # This file is scripts/demo.py -> repo root is one level up
    return Path(__file__).resolve().parents[1]


def _cleanup_artifacts(repo_root: Path) -> None:
    """Cleanup artifacts directory."""
    artifact_dir = repo_root / "artifacts"
    if artifact_dir.exists():
        shutil.rmtree(str(artifact_dir))

    audio_cache_dir = repo_root / "data/audio_cache"
    if audio_cache_dir.exists():
        shutil.rmtree(str(audio_cache_dir))


def run_pipeline() -> None:
    repo_root = _default_repo_root()

    _cleanup_artifacts(repo_root)
    audio_path = Path(repo_root / mp3_path).resolve()
    sequence_path = Path(repo_root / xsq_path).resolve()

    # Initialize session from project directory
    console.print("[bold]Initializing Twinklr session...[/bold]")
    session = TwinklrSession.from_directory(repo_root)

    # Set project name
    if not session.job_config.project_name:
        session.job_config.project_name = (
            (sequence_path.stem or audio_path.stem or "TwinklrAI Sequence")
            .lower()
            .replace(" ", "_")
        )

    # Set up artifacts
    artifact_dir = (
        repo_root / session.app_config.output_dir / session.job_config.project_name
    ).resolve()
    console.print(f"[green]Artifact directory:[/green] {artifact_dir}")
    artifact_dir.mkdir(parents=True, exist_ok=True)
    session.job_config.output_dir = str(artifact_dir)
    session.artifact_dir = artifact_dir

    xsq_out = artifact_dir / f"{session.job_config.project_name}_twinklr_mh.xsq"

    # Create moving head manager and run pipeline
    console.print("[bold]Creating moving head manager...[/bold]")
    mh = MovingHeadManager(session)

    console.print("\n[bold cyan]Running Twinklr Pipeline[/bold cyan]")
    mh.run_pipeline(
        audio_path=str(audio_path),
        xsq_in=str(sequence_path),
        xsq_out=str(xsq_out),
    )

    console.print(f"\n[green]✓ Complete! Wrote:[/green] {xsq_out}")


def main() -> None:
    run_pipeline()


if __name__ == "__main__":
    main()
