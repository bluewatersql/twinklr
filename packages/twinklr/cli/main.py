"""Command-line interface for Twinklr.

Uses the Pipeline Framework for execution.
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import os
from pathlib import Path
import sys

from rich.console import Console

from twinklr.core.agents.audio.lyrics.stage import LyricsStage
from twinklr.core.agents.audio.profile.stage import AudioProfileStage
from twinklr.core.agents.audio.stages.analysis import AudioAnalysisStage
from twinklr.core.agents.logging import create_llm_logger
from twinklr.core.agents.providers.openai import OpenAIProvider
from twinklr.core.agents.sequencer.macro_planner.stage import MacroPlannerStage
from twinklr.core.agents.sequencer.moving_heads.rendering_stage import (
    MovingHeadRenderingStage,
)
from twinklr.core.agents.sequencer.moving_heads.stage import MovingHeadStage
from twinklr.core.caching import FSCache
from twinklr.core.config.loader import load_app_config, load_job_config
from twinklr.core.io import RealFileSystem, absolute_path
from twinklr.core.pipeline import (
    ExecutionPattern,
    PipelineContext,
    PipelineDefinition,
    PipelineExecutor,
    StageDefinition,
)
from twinklr.core.sequencer.moving_heads.templates import load_builtin_templates
from twinklr.core.sequencer.moving_heads.templates.library import list_templates
from twinklr.core.utils.formatting import clean_audio_filename
from twinklr.core.utils.logging import configure_logging

console = Console()
logger = logging.getLogger(__name__)


async def run_pipeline_async(
    audio_path: Path,
    xsq_in: Path,
    output_dir: Path,
    app_config_path: Path,
    job_config_path: Path,
) -> int:
    """Run the pipeline using the Pipeline Framework.

    Args:
        audio_path: Path to audio file
        xsq_in: Path to input .xsq template
        output_dir: Output directory for artifacts
        app_config_path: Path to app config JSON
        job_config_path: Path to job config JSON

    Returns:
        Exit code (0 for success, 1 for failure)
    """
    # Check API key
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        console.print("[red]ERROR: OPENAI_API_KEY environment variable not set[/red]")
        console.print("\nTo run Twinklr:")
        console.print("  export OPENAI_API_KEY='your-key-here'")
        console.print("  twinklr run --audio <file> --xsq <file> --config <config>")
        return 1

    console.print("[green]✅ OpenAI API key found[/green]")

    # Load configuration
    console.print("[bold]Loading configuration...[/bold]")
    try:
        app_config = load_app_config(app_config_path)
        job_config = load_job_config(job_config_path)
        console.print("[green]✅ Configuration loaded[/green]")
        console.print(f"   Model: {job_config.agent.plan_agent.model}")
        console.print(f"   Max iterations: {job_config.agent.max_iterations}")
    except Exception as e:
        console.print(f"[red]ERROR: Could not load config: {e}[/red]")
        return 1

    # Setup paths
    song_name = clean_audio_filename(audio_path.stem)
    artifact_dir = output_dir / song_name
    artifact_dir.mkdir(parents=True, exist_ok=True)
    console.print(f"[green]📁 Output directory:[/green] {artifact_dir}")

    # Load templates
    console.print("[bold]Loading templates...[/bold]")
    load_builtin_templates()
    available_templates = [t.template_id for t in list_templates()]
    console.print(f"[green]📚 Templates loaded:[/green] {len(available_templates)}")

    # Build display groups for MacroPlanner coordination
    display_groups = [
        {"role_key": "MOVING_HEADS", "model_count": 4, "group_type": "moving_head"},
        {"role_key": "OUTLINE", "model_count": 10, "group_type": "string"},
        {"role_key": "MEGA_TREE", "model_count": 1, "group_type": "tree"},
    ]

    # Define pipeline
    console.print("\n[bold]Defining pipeline...[/bold]")
    pipeline = PipelineDefinition(
        name="twinklr_pipeline",
        description="Twinklr choreography pipeline",
        fail_fast=True,
        stages=[
            StageDefinition(
                id="audio",
                stage=AudioAnalysisStage(),
                description="Analyze audio file",
            ),
            StageDefinition(
                id="profile",
                stage=AudioProfileStage(),
                inputs=["audio"],
                description="Generate audio profile",
            ),
            StageDefinition(
                id="lyrics",
                stage=LyricsStage(),
                inputs=["audio"],
                pattern=ExecutionPattern.CONDITIONAL,
                condition=lambda ctx: ctx.get_state("has_lyrics", False),
                critical=False,
                description="Analyze lyrics (if available)",
            ),
            StageDefinition(
                id="macro",
                stage=MacroPlannerStage(display_groups=display_groups),
                inputs=["profile", "lyrics"],
                description="Generate macro choreography strategy",
            ),
            StageDefinition(
                id="moving_heads",
                stage=MovingHeadStage(
                    fixture_count=4,
                    available_templates=available_templates,
                    max_iterations=job_config.agent.max_iterations,
                    min_pass_score=7.0,
                ),
                inputs=["audio", "profile", "lyrics", "macro"],
                description="Generate moving head choreography",
            ),
            StageDefinition(
                id="render",
                stage=MovingHeadRenderingStage(
                    xsq_output_path=artifact_dir / f"{song_name}_twinklr_mh.xsq",
                    xsq_template_path=xsq_in,
                    fixture_config_path=job_config_path.parent / "fixture_config.json",
                ),
                inputs=["moving_heads"],
                description="Render to XSQ",
            ),
        ],
    )

    # Validate pipeline
    errors = pipeline.validate_pipeline()
    if errors:
        console.print(f"[red]Pipeline validation failed: {errors}[/red]")
        return 1

    console.print(f"[green]✅ Pipeline validated[/green] ({len(pipeline.stages)} stages)")

    # Setup caching
    fs = RealFileSystem()
    llm_cache_dir = absolute_path("data/cache/llm")
    llm_cache = FSCache(fs, llm_cache_dir)
    await llm_cache.initialize()

    agent_cache_dir = absolute_path("data/cache/agents")
    agent_cache = FSCache(fs, agent_cache_dir)
    await agent_cache.initialize()

    # Create provider and logger
    provider = OpenAIProvider(api_key=api_key, llm_cache=llm_cache)
    llm_logger = create_llm_logger(
        enabled=job_config.agent.llm_logging.enabled,
        output_dir=artifact_dir / "llm_calls",
        log_level=job_config.agent.llm_logging.log_level,
        format=job_config.agent.llm_logging.format,
    )

    # Create pipeline context
    pipeline_context = PipelineContext(
        provider=provider,
        app_config=app_config,
        job_config=job_config,
        cache=agent_cache,
        llm_logger=llm_logger,
        output_dir=artifact_dir,
    )

    # Execute pipeline
    console.print(f"\n[bold]🎵 Processing:[/bold] {audio_path.name}")
    console.print("[bold]🚀 Starting pipeline execution...[/bold]\n")

    executor = PipelineExecutor()
    result = await executor.execute(
        pipeline=pipeline,
        initial_input=str(audio_path),
        context=pipeline_context,
    )

    # Report results
    console.print("\n" + "=" * 50)
    console.print("[bold]PIPELINE RESULTS[/bold]")
    console.print("=" * 50)

    console.print(f"Overall Success: {'[green]✅[/green]' if result.success else '[red]❌[/red]'}")
    console.print(
        f"Duration: {result.total_duration_ms:.0f}ms ({result.total_duration_ms / 1000:.1f}s)"
    )
    console.print(f"Stages Completed: {len(result.outputs)}/{len(pipeline.stages)}")

    if result.failed_stages:
        console.print(f"\n[red]Failed stages: {result.failed_stages}[/red]")
        for stage_id in result.failed_stages:
            stage_result = result.stage_results.get(stage_id)
            if stage_result:
                console.print(f"   - {stage_id}: {stage_result.error}")
        return 1

    # Success summary
    if result.success:
        console.print("\n[bold green]✅ Pipeline completed successfully![/bold green]")

        if "moving_heads" in result.outputs:
            plan = result.outputs["moving_heads"]
            console.print("\n[bold]🎯 Choreography Plan:[/bold]")
            console.print(f"   Sections: {len(plan.sections)}")
            console.print(f"   Strategy: {plan.overall_strategy[:80]}...")

        if "render" in result.outputs:
            xsq_path = result.outputs["render"]
            segment_count = pipeline_context.metrics.get("mh_render_segments", 0)
            console.print(f"\n[bold]🎄 XSQ Output:[/bold] {xsq_path}")
            console.print(f"   Segments rendered: {segment_count}")

        console.print(f"\n[green]📁 All artifacts saved to:[/green] {artifact_dir}")
        return 0

    return 1


def run_pipeline(args: argparse.Namespace) -> None:
    """Run the full Twinklr pipeline."""
    configure_logging(level="INFO")

    audio_path = Path(args.audio).resolve()
    xsq_path = Path(args.xsq).resolve()
    output_dir = Path(args.out).resolve()
    app_config_path = Path(args.app_config).resolve()
    job_config_path = Path(args.config).resolve()

    # Validate inputs
    if not audio_path.exists():
        console.print(f"[red]ERROR: Audio file not found: {audio_path}[/red]")
        sys.exit(1)

    if not xsq_path.exists():
        console.print(f"[red]ERROR: XSQ file not found: {xsq_path}[/red]")
        sys.exit(1)

    if not job_config_path.exists():
        console.print(f"[red]ERROR: Job config not found: {job_config_path}[/red]")
        sys.exit(1)

    # Run async pipeline
    exit_code = asyncio.run(
        run_pipeline_async(
            audio_path=audio_path,
            xsq_in=xsq_path,
            output_dir=output_dir,
            app_config_path=app_config_path,
            job_config_path=job_config_path,
        )
    )
    sys.exit(exit_code)


def build_arg_parser() -> argparse.ArgumentParser:
    """Build argument parser for CLI."""
    p = argparse.ArgumentParser(
        prog="twinklr",
        description="Twinklr - AI-powered lighting sequencer for xLights",
    )
    sub = p.add_subparsers(dest="cmd", required=True)

    run = sub.add_parser("run", help="Run the full pipeline")
    run.add_argument("--audio", required=True, help="Path to audio file (mp3/wav)")
    run.add_argument("--xsq", required=True, help="Path to input .xsq template")
    run.add_argument("--out", default=".", help="Output directory (default: current dir)")
    run.add_argument(
        "--app-config",
        default="config.json",
        help="Path to app config JSON (default: config.json)",
    )
    run.add_argument(
        "--config",
        required=True,
        help="Path to job config JSON",
    )

    return p


def main() -> None:
    """Main entry point for CLI."""
    p = build_arg_parser()
    args = p.parse_args()

    if args.cmd == "run":
        run_pipeline(args)
