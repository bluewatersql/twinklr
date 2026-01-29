"""Command-line interface for evaluation report generation."""

from __future__ import annotations

import asyncio
import json
import logging
from pathlib import Path

import click

from blinkb0t.core.reporting.evaluation.config import EvalConfig
from blinkb0t.core.reporting.evaluation.generator import generate_evaluation_report

logger = logging.getLogger(__name__)


@click.command("eval-report")
@click.option(
    "--checkpoint",
    type=click.Path(exists=True, path_type=Path),
    required=True,
    help="Path to checkpoint JSON file",
)
@click.option(
    "--audio",
    type=click.Path(exists=True, path_type=Path),
    required=True,
    help="Path to audio file (MP3)",
)
@click.option(
    "--fixture",
    type=click.Path(exists=True, path_type=Path),
    required=True,
    help="Path to fixture configuration JSON",
)
@click.option(
    "--xsq",
    type=click.Path(exists=True, path_type=Path),
    required=True,
    help="Path to xLights sequence file",
)
@click.option(
    "--out",
    type=click.Path(path_type=Path),
    required=True,
    help="Output directory for report artifacts",
)
@click.option(
    "--config",
    type=click.Path(exists=True, path_type=Path),
    help="Optional evaluation config JSON",
)
@click.option(
    "--log-level",
    type=click.Choice(["DEBUG", "INFO", "WARNING", "ERROR"]),
    default="INFO",
    help="Logging level",
)
def eval_report_cli(  # type: ignore[misc]
    checkpoint: Path,
    audio: Path,
    fixture: Path,
    xsq: Path,
    out: Path,
    config: Path | None,
    log_level: str,
) -> None:
    """Generate evaluation report from checkpoint.

    This command re-renders a choreography plan through the sequencing pipeline,
    analyzes the resulting curves, and generates a comprehensive evaluation report
    with plots.

    Example:
        blinkb0t eval-report \\
            --checkpoint artifacts/my_song/checkpoints/plans/final.json \\
            --audio data/music/my_song.mp3 \\
            --fixture fixture_config.json \\
            --xsq data/sequences/my_song.xsq \\
            --out artifacts/my_song/eval_reports/run_001
    """
    # Configure logging
    logging.basicConfig(
        level=getattr(logging, log_level),
        format="%(asctime)s - %(levelname)s - %(message)s",
    )

    # Load config if provided
    eval_config = EvalConfig()
    if config and config.exists():
        try:
            config_data = json.loads(config.read_text())
            eval_config = EvalConfig.model_validate(config_data)
            click.echo(f"Loaded config from {config}")
        except Exception as e:
            click.echo(f"Warning: Failed to load config: {e}", err=True)
            click.echo("Using default configuration")

    # Generate report (async)
    try:
        click.echo("Generating evaluation report...")
        click.echo(f"  Checkpoint: {checkpoint}")
        click.echo(f"  Audio: {audio}")
        click.echo(f"  Output: {out}")

        # Run async function with asyncio.run()
        report_path = asyncio.run(
            generate_evaluation_report(
                checkpoint_path=checkpoint,
                audio_path=audio,
                fixture_config_path=fixture,
                xsq_path=xsq,
                output_dir=out,
                config=eval_config,
            )
        )

        click.echo("")
        click.echo("✓ Report generated successfully!")
        click.echo(f"  Report: {report_path}")
        click.echo(f"  JSON: {out / 'report.json'}")
        click.echo(f"  Plots: {out / 'plots/'}")

    except Exception as e:
        click.echo(f"✗ Failed to generate report: {e}", err=True)
        logger.exception("Report generation failed")
        raise click.Abort() from e


if __name__ == "__main__":
    eval_report_cli()  # pyright: ignore[reportCallIssue]
