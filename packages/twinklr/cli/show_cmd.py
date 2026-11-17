"""User-facing one-plan coordinated ``twinklr show`` command."""

from __future__ import annotations

import argparse
import asyncio
from pathlib import Path
import shutil
import tempfile
import time

from rich.console import Console

from twinklr.cli.display_cmd import load_display_fe_bundle
from twinklr.core.agents.providers.factory import validate_llm_provider_config
from twinklr.core.agents.sequencer.moving_heads.rendering_stage import record_render
from twinklr.core.caching import derive_session_id
from twinklr.core.caching.identity import hash_file_content
from twinklr.core.config.loader import load_app_config, load_fixture_group, load_job_config
from twinklr.core.config.models import MHRenderPolicy
from twinklr.core.config.render_policy import preflight_render_policy
from twinklr.core.formats.xlights.sequence.exporter import XSQExporter
from twinklr.core.formats.xlights.sequence.models.xsq import XSequence
from twinklr.core.formats.xlights.sequence.trace import write_xsq_trace_sidecar
from twinklr.core.pipeline import PipelineContext, PipelineExecutor
from twinklr.core.pipeline.display_wiring import (
    default_local_catalog_dir,
    tracked_catalog_dir,
)
from twinklr.core.pipeline.show_wiring import prepare_combined_show_pipeline
from twinklr.core.reporting.evaluation.show_manifest import write_show_evaluation_manifest
from twinklr.core.sequencer.display.renderer import RenderResult
from twinklr.core.sequencer.display.xlights_mapping import XLightsMapping
from twinklr.core.sequencer.moving_heads.delivery import DeliveryRollbackError, publish_files
from twinklr.core.sequencer.moving_heads.export.frame_encoder import (
    PhysicalOutputError,
    check_output_budget,
    measure_output,
)
from twinklr.core.sequencer.moving_heads.pipeline import offered_template_ids
from twinklr.core.sequencer.moving_heads.templates import load_builtin_templates
from twinklr.core.sequencer.moving_heads.templates.data_loader import admit_physical_catalog
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
        # As `twinklr run`: the rig's render prerequisites are checked when it loads,
        # and the planner is offered only templates the render mode can render; the
        # render preflight gate repeats both after audio analysis, before any planner.
        preflight_render_policy(job_config, fixture_group)
        fe_bundle = load_display_fe_bundle(fe_output_dir, style_name=style_name)
        load_builtin_templates()
        admit_physical_catalog(job_config)
        available_templates = offered_template_ids(
            job_config, [template.template_id for template in list_templates()]
        )
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
            fixture_config_path=fixture_config_path,
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
    # The layout's models, for the moving-head model check the gate and render make.
    context.set_state("layout_models", wiring.layout_models)
    context.set_state("layout_sha256", hash_file_content(layout_path))
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
        xsq_path, trace_path = export_show_artifacts(
            render_output,
            artifact_dir=artifact_dir,
            song_name=song_name,
            policy=job_config.moving_heads,
        )
        if not isinstance(render_output, dict):
            raise TypeError("show_render output must be an object")
        checkpoint_record = render_output.get("checkpoint_record")
        if checkpoint_record is not None:
            # The show is delivered: record its moving-head render as `twinklr run` does.
            record_render(checkpoint_record, context)
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
    except PhysicalOutputError as error:
        console.print(f"[red]ERROR: {error}[/red]")
        return 1
    except (OSError, TypeError, ValueError) as error:
        console.print(f"[red]Combined show returned an invalid render payload: {error}[/red]")
        return 1
    console.print(f"[green]Coordinated sequence:[/green] {xsq_path}")
    console.print(f"[green]Render trace:[/green] {trace_path}")
    console.print(f"[green]Evaluation manifest:[/green] {manifest_path}")
    return 0


def export_show_artifacts(
    render_output: object,
    *,
    artifact_dir: Path,
    song_name: str,
    policy: MHRenderPolicy,
) -> tuple[Path, Path]:
    """Write the combined sequence and its trace-v2 sidecar.

    A physical render's output (`render_record`, `moving_head_runs`) is measured as
    `twinklr run` measures its delivery: the serialized `.xsq` and the moving heads'
    effect count must fit `policy`'s budgets before anything is written, and the trace
    carries the render record with that measure under `output`. A legacy render's
    output carries neither, and its files are written as before. Both files are
    staged beside the destination and published together, the `.xsq` last, as
    `twinklr run` publishes its delivery (`publish_files`): a failure leaves any
    earlier show in place.

    Raises:
        TypeError: If the output is not the combined render stage's.
        PhysicalOutputError: If the physical output exceeds the budgets; nothing is
            written.
        DeliveryRollbackError: If publishing failed and an earlier file could not be
            put back; the staging directory is then kept and named.
    """
    if not isinstance(render_output, dict):
        raise TypeError("show_render output must be an object")
    sequence = render_output.get("sequence")
    render_result = render_output.get("render_result")
    if not isinstance(sequence, XSequence):
        raise TypeError("show_render.sequence must be an XSequence")
    if not isinstance(render_result, RenderResult):
        raise TypeError("show_render.render_result must be a RenderResult")
    record = render_output.get("render_record")
    xsq_name = f"{song_name}_twinklr_show.xsq"
    artifact_dir.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=f".{xsq_name}.", dir=artifact_dir))
    try:
        staged_xsq = staging / xsq_name
        started = time.perf_counter()
        XSQExporter().export(sequence, staged_xsq)
        serialization_ms = (time.perf_counter() - started) * 1000
        render = None
        if record is not None:
            measure = measure_output(render_output["moving_head_runs"], staged_xsq.read_bytes())
            check_output_budget(measure, policy)
            render = {
                **record,
                "output": {
                    "effect_count": measure.effect_count,
                    "xsq_bytes": measure.xsq_bytes,
                    "serialization_ms": round(serialization_ms, 3),
                },
            }
        staged_trace = write_xsq_trace_sidecar(
            staged_xsq,
            render_result.xsq_trace_entries,
            fallback_substitutions=render_result.fallback_substitutions,
            render=render,
        )
        publish_files((staged_trace, staged_xsq), artifact_dir, backup_dir=staging / ".replaced")
    except DeliveryRollbackError:
        raise  # the staging directory holds files that could not be put back
    except BaseException:
        shutil.rmtree(staging, ignore_errors=True)
        raise
    shutil.rmtree(staging, ignore_errors=True)
    return artifact_dir / xsq_name, artifact_dir / staged_trace.name


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


__all__ = [
    "add_show_subparser",
    "export_show_artifacts",
    "run_show_command",
    "run_show_pipeline_async",
]
