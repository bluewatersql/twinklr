"""User-facing one-plan coordinated ``twinklr show`` command."""

from __future__ import annotations

import argparse
import asyncio
from pathlib import Path

from rich.console import Console

from twinklr.cli.display_cmd import export_display_artifacts, load_display_fe_bundle
from twinklr.core.agents.providers.factory import validate_llm_provider_config
from twinklr.core.caching import derive_session_id
from twinklr.core.config.loader import load_app_config, load_fixture_group, load_job_config
from twinklr.core.pipeline import PipelineContext, PipelineExecutor
from twinklr.core.pipeline.display_wiring import (
    default_local_catalog_dir,
    tracked_catalog_dir,
)
from twinklr.core.pipeline.show_wiring import prepare_combined_show_pipeline
from twinklr.core.reporting.evaluation.show_manifest import write_show_evaluation_manifest
from twinklr.core.sequencer.display.xlights_mapping import XLightsMapping
from twinklr.core.sequencer.moving_heads.templates import load_builtin_templates
from twinklr.core.sequencer.moving_heads.templates.library import list_templates
from twinklr.core.sequencer.planning import MacroPlan
from twinklr.core.sequencer.templates.group.models.choreography import ChoreographyGraph
from twinklr.core.session import TwinklrSession
from twinklr.core.utils.formatting import clean_audio_filename

console = Console()


def add_show_subparser(subparsers: argparse._SubParsersAction) -> None:
    """Register the additive combined-show CLI without changing branch commands."""

    parser = subparsers.add_parser(
        "show", help="Create one coordinated MH + display xLights sequence"
    )
    parser.add_argument("--audio", required=True, help="Path to audio file (mp3/wav)")
    parser.add_argument("--layout", required=True, help="Path to xlights_rgbeffects.xml")
    parser.add_argument("--fixture-config", required=True, help="Path to fixture config JSON")
    parser.add_argument("--config", required=True, help="Path to job config JSON")
    parser.add_argument("--app-config", default=None, help="Optional app config JSON")
    parser.add_argument("--out", default=".", help="Output directory")
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
    parser.add_argument("--session-id", default=None, help="Override deterministic cache ID")


async def run_show_pipeline_async(
    *,
    audio_path: Path,
    layout_path: Path,
    fixture_config_path: Path,
    output_dir: Path,
    app_config_path: Path | None,
    job_config_path: Path,
    fe_output_dir: Path | None = None,
    style_name: str | None = None,
    session_id: str | None = None,
) -> int:
    """Run the shared-prefix DAG and export its one in-memory sequence."""

    try:
        app_config = load_app_config(app_config_path)
        validate_llm_provider_config(app_config)
        job_config = load_job_config(job_config_path)
        fixture_group = load_fixture_group(fixture_config_path)
        fe_bundle = load_display_fe_bundle(fe_output_dir, style_name=style_name)
        load_builtin_templates()
        available_templates = [template.template_id for template in list_templates()]
        song_name = clean_audio_filename(audio_path.stem)
        wiring = prepare_combined_show_pipeline(
            layout_path=layout_path,
            fixture_group=fixture_group,
            job_config=job_config,
            available_templates=available_templates,
            song_name=song_name,
            catalog_dir=tracked_catalog_dir(),
            local_catalog_dir=default_local_catalog_dir(),
            fe_bundle=fe_bundle,
        )
    except Exception as error:
        console.print(f"[red]ERROR: Could not prepare combined show: {error}[/red]")
        return 1
    errors = wiring.pipeline.validate_pipeline()
    if errors:
        console.print(f"[red]Pipeline validation failed: {errors}[/red]")
        return 1

    artifact_dir = output_dir / song_name
    artifact_dir.mkdir(parents=True, exist_ok=True)
    resolved_session_id = session_id or derive_session_id(
        audio_path=audio_path,
        configs=(app_config, job_config, fixture_group),
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
    result = await PipelineExecutor().execute(
        pipeline=wiring.pipeline,
        initial_input=str(audio_path),
        context=context,
    )
    if not result.success:
        console.print(f"[red]Combined show pipeline failed: {result.failed_stages}[/red]")
        return 1
    try:
        render_output = result.outputs.get("show_render")
        xsq_path, trace_path = export_display_artifacts(
            render_output,
            artifact_dir=artifact_dir,
            song_name=song_name,
            artifact_kind="show",
        )
        if not isinstance(render_output, dict):
            raise TypeError("show_render output must be an object")
        evaluation_contract = render_output.get("evaluation_contract")
        if not isinstance(evaluation_contract, dict):
            raise TypeError("show_render evaluation_contract must be an object")
        manifest_path = Path(f"{xsq_path}.evaluation.json")
        write_show_evaluation_manifest(
            path=manifest_path,
            xsq_path=xsq_path,
            trace_path=trace_path,
            macro_plan=MacroPlan.model_validate(evaluation_contract.get("macro_plan")),
            choreography_graph=ChoreographyGraph.model_validate(
                evaluation_contract.get("choreography_graph")
            ),
            xlights_mapping=XLightsMapping.model_validate(
                evaluation_contract.get("xlights_mapping")
            ),
            moving_head_target_ids=set(evaluation_contract.get("moving_head_target_ids", [])),
        )
    except (OSError, TypeError, ValueError) as error:
        console.print(f"[red]Combined show returned an invalid render payload: {error}[/red]")
        return 1
    console.print(f"[green]Coordinated sequence:[/green] {xsq_path}")
    console.print(f"[green]Render trace:[/green] {trace_path}")
    console.print(f"[green]Evaluation manifest:[/green] {manifest_path}")
    return 0


def run_show_command(args: argparse.Namespace) -> None:
    """Validate local paths and execute the combined command."""

    paths = {
        "audio_path": Path(args.audio).resolve(),
        "layout_path": Path(args.layout).resolve(),
        "fixture_config_path": Path(args.fixture_config).resolve(),
        "job_config_path": Path(args.config).resolve(),
    }
    app_config_path = Path(args.app_config).resolve() if args.app_config else None
    for label, path in paths.items():
        if not path.is_file():
            console.print(f"[red]ERROR: {label} not found: {path}[/red]")
            raise SystemExit(1)
    if app_config_path is not None and not app_config_path.is_file():
        console.print(f"[red]ERROR: app_config not found: {app_config_path}[/red]")
        raise SystemExit(1)
    fe_output_dir = Path(args.fe_output_dir).resolve() if args.fe_output_dir else None
    if fe_output_dir is not None and not fe_output_dir.is_dir():
        console.print(f"[red]ERROR: FE output directory not found: {fe_output_dir}[/red]")
        raise SystemExit(1)
    raise SystemExit(
        asyncio.run(
            run_show_pipeline_async(
                **paths,
                output_dir=Path(args.out).resolve(),
                app_config_path=app_config_path,
                fe_output_dir=fe_output_dir,
                style_name=args.style,
                session_id=args.session_id,
            )
        )
    )


__all__ = ["add_show_subparser", "run_show_command", "run_show_pipeline_async"]
