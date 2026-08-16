"""Offline-first ``twinklr display`` command wiring."""

from __future__ import annotations

import argparse
import asyncio
import logging
import os
from pathlib import Path

from rich.console import Console

from twinklr.core.caching import derive_session_id
from twinklr.core.config.loader import load_app_config, load_job_config
from twinklr.core.feature_engineering.loader import FEArtifactBundle, load_fe_artifacts
from twinklr.core.formats.xlights.sequence.exporter import XSQExporter
from twinklr.core.formats.xlights.sequence.models.xsq import XSequence
from twinklr.core.pipeline import PipelineContext, PipelineExecutor
from twinklr.core.pipeline.display_wiring import (
    default_local_catalog_dir,
    prepare_display_pipeline,
    tracked_catalog_dir,
)
from twinklr.core.sequencer.display.renderer import (
    RenderResult,
    write_display_xsq_trace_sidecar,
)
from twinklr.core.session import TwinklrSession
from twinklr.core.utils.formatting import clean_audio_filename

logger = logging.getLogger(__name__)
console = Console()


def add_display_subparser(subparsers: argparse._SubParsersAction) -> None:
    """Register the display pipeline's user-facing command surface."""
    parser = subparsers.add_parser(
        "display",
        help="Create an xLights display sequence from audio and an xLights layout",
    )
    parser.add_argument("--audio", required=True, help="Path to audio file (mp3/wav)")
    parser.add_argument(
        "--layout",
        required=True,
        help="Path to the user's xlights_rgbeffects.xml layout",
    )
    parser.add_argument("--config", required=True, help="Path to job config JSON")
    parser.add_argument(
        "--app-config",
        default=None,
        help="Optional app config JSON; omitted uses loader defaults",
    )
    parser.add_argument("--out", default=".", help="Output directory (default: current dir)")
    parser.add_argument(
        "--fe-output-dir",
        default=None,
        help="Optional feature-engineering output directory",
    )
    parser.add_argument(
        "--style",
        default=None,
        help="Optional named style fingerprint within --fe-output-dir",
    )
    parser.add_argument(
        "--session-id",
        default=None,
        help="Override the deterministic cache session ID",
    )


def load_display_fe_bundle(
    fe_output_dir: Path | None,
    *,
    style_name: str | None,
) -> FEArtifactBundle | None:
    """Load optional FE context while enforcing the grouped-style contract."""
    if style_name is not None and fe_output_dir is None:
        raise ValueError("--style requires --fe-output-dir")
    if fe_output_dir is None:
        return None
    return load_fe_artifacts(fe_output_dir, style_name=style_name)


async def run_display_pipeline_async(
    *,
    audio_path: Path,
    layout_path: Path,
    output_dir: Path,
    app_config_path: Path | None,
    job_config_path: Path,
    fe_output_dir: Path | None = None,
    style_name: str | None = None,
    session_id: str | None = None,
) -> int:
    """Run the existing display pipeline and export its in-memory sequence."""
    if not os.getenv("OPENAI_API_KEY"):
        console.print("[red]ERROR: OPENAI_API_KEY environment variable not set[/red]")
        return 1
    try:
        app_config = load_app_config(app_config_path)
        job_config = load_job_config(job_config_path)
        fe_bundle = load_display_fe_bundle(fe_output_dir, style_name=style_name)
        song_name = clean_audio_filename(audio_path.stem)
        wiring = prepare_display_pipeline(
            layout_path=layout_path,
            job_config=job_config,
            catalog_dir=tracked_catalog_dir(),
            local_catalog_dir=default_local_catalog_dir(),
            fe_bundle=fe_bundle,
            song_name=song_name,
        )
    except Exception as error:
        console.print(f"[red]ERROR: Could not prepare display pipeline: {error}[/red]")
        return 1

    errors = wiring.pipeline.validate_pipeline()
    if errors:
        console.print(f"[red]Pipeline validation failed: {errors}[/red]")
        return 1

    artifact_dir = output_dir / song_name
    artifact_dir.mkdir(parents=True, exist_ok=True)
    resolved_session_id = session_id or derive_session_id(
        audio_path=audio_path,
        configs=(app_config, job_config),
    )
    session = TwinklrSession(
        app_config=app_config,
        job_config=job_config,
        session_id=resolved_session_id,
        project_root=job_config_path.parent,
    )
    context = PipelineContext(session=session, output_dir=artifact_dir)
    context.set_state("job_config_dir", job_config_path.parent)
    context.set_state("choreo_graph", wiring.choreo_graph)
    context.set_state("xlights_mapping", wiring.xlights_mapping)
    context.set_state("recipe_catalog", wiring.recipe_catalog)

    console.print(
        f"[green]Display layout:[/green] {len(wiring.choreo_graph.groups)} target(s): "
        + ", ".join(group.id for group in wiring.choreo_graph.groups)
    )
    result = await PipelineExecutor().execute(
        pipeline=wiring.pipeline,
        initial_input=str(audio_path),
        context=context,
    )
    if not result.success:
        console.print(f"[red]Display pipeline failed: {result.failed_stages}[/red]")
        return 1

    try:
        xsq_path, trace_path = export_display_artifacts(
            result.outputs.get("display_render"),
            artifact_dir=artifact_dir,
            song_name=song_name,
        )
    except (OSError, TypeError, ValueError) as error:
        console.print(f"[red]Display pipeline returned an invalid render payload: {error}[/red]")
        return 1
    console.print(f"[green]Display sequence:[/green] {xsq_path}")
    console.print(f"[green]Render trace:[/green] {trace_path}")
    return 0


def export_display_artifacts(
    render_output: object,
    *,
    artifact_dir: Path,
    song_name: str,
) -> tuple[Path, Path]:
    """Persist the pipeline's in-memory sequence and deterministic trace sidecar."""
    if not isinstance(render_output, dict):
        raise TypeError("display_render output must be an object")
    sequence = render_output.get("sequence")
    render_result = render_output.get("render_result")
    if not isinstance(sequence, XSequence):
        raise TypeError("display_render.sequence must be an XSequence")
    if not isinstance(render_result, RenderResult):
        raise TypeError("display_render.render_result must be a RenderResult")
    xsq_path = artifact_dir / f"{song_name}_twinklr_display.xsq"
    XSQExporter().export(sequence, xsq_path)
    return xsq_path, write_display_xsq_trace_sidecar(xsq_path, render_result)


def run_display_command(args: argparse.Namespace) -> None:
    """Validate command paths and run the display pipeline."""
    audio_path = Path(args.audio).resolve()
    layout_path = Path(args.layout).resolve()
    app_config_path = Path(args.app_config).resolve() if args.app_config else None
    job_config_path = Path(args.config).resolve()
    for label, path in (
        ("Audio file", audio_path),
        ("xLights layout", layout_path),
        ("Job config", job_config_path),
    ):
        if not path.is_file():
            console.print(f"[red]ERROR: {label} not found: {path}[/red]")
            raise SystemExit(1)
    if app_config_path is not None and not app_config_path.is_file():
        console.print(f"[red]ERROR: App config not found: {app_config_path}[/red]")
        raise SystemExit(1)
    fe_output_dir = Path(args.fe_output_dir).resolve() if args.fe_output_dir else None
    if fe_output_dir is not None and not fe_output_dir.is_dir():
        console.print(f"[red]ERROR: FE output directory not found: {fe_output_dir}[/red]")
        raise SystemExit(1)
    exit_code = asyncio.run(
        run_display_pipeline_async(
            audio_path=audio_path,
            layout_path=layout_path,
            output_dir=Path(args.out).resolve(),
            app_config_path=app_config_path,
            job_config_path=job_config_path,
            fe_output_dir=fe_output_dir,
            style_name=args.style,
            session_id=args.session_id,
        )
    )
    raise SystemExit(exit_code)


__all__ = [
    "add_display_subparser",
    "export_display_artifacts",
    "load_display_fe_bundle",
    "run_display_command",
    "run_display_pipeline_async",
]
