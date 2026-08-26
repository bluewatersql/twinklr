"""Command-line interface for Twinklr.

Uses the Pipeline Framework for execution.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
from pathlib import Path
import sys
from uuid import uuid4

from rich.console import Console

from twinklr.cli.catalog_coverage_cmd import (
    add_catalog_coverage_subparser,
    run_catalog_coverage_command,
)
from twinklr.cli.curation_cmd import (
    add_review_staged_recipes_subparser,
    run_review_staged_recipes_command,
)
from twinklr.cli.display_cmd import add_display_subparser, run_display_command
from twinklr.cli.fseqcmp_cmd import run_fseqcmp_command
from twinklr.cli.recipe_builder_cmd import (
    add_curate_catalog_subparser,
    run_curate_catalog_command,
)
from twinklr.cli.show_cmd import add_show_subparser, run_show_command
from twinklr.cli.template_cmd import (
    add_template_subparsers,
    run_template_export_command,
    run_template_validate_command,
)
from twinklr.core.agents.providers.factory import validate_llm_provider_config
from twinklr.core.api.xlights import (
    GetModelsRequest,
    InjectionPartialError,
    JsonOwnershipStore,
    LiveInjectionWorkflow,
    XLightsAutomationClient,
    live_effects_from_segments,
    reconcile_live_layout,
)
from twinklr.core.caching import derive_session_id
from twinklr.core.config.fixtures import FixtureGroup
from twinklr.core.config.loader import load_app_config, load_fixture_group, load_job_config
from twinklr.core.config.models import JobConfig
from twinklr.core.pipeline import PipelineContext, PipelineExecutor
from twinklr.core.pipeline.definition import PipelineDefinition
from twinklr.core.pipeline.definitions import build_moving_heads_pipeline
from twinklr.core.reporting.evaluation.show_cli import (
    add_show_eval_subparser,
    run_show_eval_command,
)
from twinklr.core.sequencer.display.xlights_mapping import (
    XLightsGroupMapping,
    XLightsMapping,
)
from twinklr.core.sequencer.moving_heads.templates import (
    load_builtin_templates,
    load_templates_from_directory,
)
from twinklr.core.sequencer.moving_heads.templates.library import list_templates
from twinklr.core.sequencer.templates.group.models.choreography import (
    ChoreographyGraph,
    ChoreoGroup,
)
from twinklr.core.sequencer.templates.group.models.display import GroupPosition
from twinklr.core.sequencer.vocabulary.display import (
    DisplayElementKind,
    DisplayProminence,
    GroupArrangement,
)
from twinklr.core.sequencer.vocabulary.spatial import (
    DepthZone,
    DisplayZone,
    HorizontalZone,
    VerticalZone,
)
from twinklr.core.session import TwinklrSession
from twinklr.core.utils.formatting import clean_audio_filename
from twinklr.core.utils.logging import configure_logging

console = Console()


def _print_live_injection_partial(error: InjectionPartialError) -> None:
    """Render every recovery fact retained after a non-transactional failure."""
    result = error.result
    console.print("[red]ERROR: Live injection stopped after a partial failure.[/red]")
    console.print(f"Confirmed injected prefix: {len(result.injected)}")
    for effect in result.injected:
        console.print(
            json.dumps(
                {"section_id": effect.section_id, **effect.request().to_wire()},
                sort_keys=True,
            )
        )
    console.print(f"Confirmed deletions: {len(result.deleted)}")
    for effect in result.deleted:
        console.print(
            json.dumps(
                {"section_id": effect.section_id, **effect.request().to_wire()},
                sort_keys=True,
            )
        )
    console.print(
        "Exact failed payload: "
        + (json.dumps(result.failed_command, sort_keys=True) if result.failed_command else "none")
    )
    console.print(f"Underlying error: {result.error or 'unknown'}")
    console.print(f"Recovery: {result.recovery}")


logger = logging.getLogger(__name__)


def _resolve_fixture_config_path(job_config_path: Path, fixture_config_path: str) -> Path:
    """Resolve fixture config path from job config location.

    Relative paths are interpreted from the job config directory.
    Absolute paths are preserved.
    """
    fixture_path = Path(fixture_config_path)
    if fixture_path.is_absolute():
        return fixture_path
    return job_config_path.parent / fixture_path


def build_moving_head_graph(
    fixture_group: FixtureGroup,
) -> tuple[ChoreographyGraph, XLightsMapping]:
    """Build the ChoreographyGraph and XLightsMapping from the user's rig.

    The graph used to be a hardcoded three-group residential display — moving heads,
    outline, mega tree — with a literal fixture count each, describing the author's own
    yard to the planner of every run (P7-M1). It now describes exactly one group: the
    moving heads in the loaded fixture config, at the count that config declares.

    That is the whole display Twinklr drives today. The outline and mega-tree groups
    were addressable in the planner's prompt but nothing rendered them — the display
    pipeline is deferred (P3-T3 makes it CLI-reachable), so naming them here only told
    the planner about hardware the run would never light.

    Args:
        fixture_group: Loaded moving-head rig.

    Returns:
        Tuple of (ChoreographyGraph, XLightsMapping).
    """
    fixtures = fixture_group.expand_fixtures()
    if not fixtures:
        raise ValueError(
            f"Fixture config for group {fixture_group.group_id!r} declares no fixtures; "
            f"add at least one moving head for the planner to choreograph."
        )
    group = ChoreoGroup(
        id="MOVING_HEADS",
        role="MOVING_HEADS",
        element_kind=DisplayElementKind.MOVING_HEAD,
        arrangement=GroupArrangement.HORIZONTAL_ROW,
        prominence=DisplayProminence.HERO,
        position=GroupPosition(
            horizontal=HorizontalZone.CENTER,
            vertical=VerticalZone.FULL_HEIGHT,
            depth=DepthZone.NEAR,
            zone=DisplayZone.YARD,
        ),
        fixture_count=len(fixtures),
        pixel_fraction=1.0,
    )
    choreo_graph = ChoreographyGraph(graph_id="moving_heads_rig", groups=[group])
    xlights_mapping = XLightsMapping(
        entries=[
            XLightsGroupMapping(
                choreo_id="MOVING_HEADS",
                group_name=fixture_group.xlights_group or "Moving Heads",
            )
        ]
    )
    return choreo_graph, xlights_mapping


def build_run_pipeline(
    *,
    fixture_group: FixtureGroup,
    job_config: JobConfig,
    available_templates: list[str],
    xsq_output_path: Path,
    fixture_config_path: Path,
    section_id: str | None = None,
    regeneration_nonce: str | None = None,
) -> tuple[PipelineDefinition, ChoreographyGraph, XLightsMapping]:
    """Build the pipeline a `twinklr run` executes, from configuration alone.

    Every operative value the CLI used to hardcode is resolved here from the two
    configs the user already passes: the fixture count and the display graph come from
    the fixture config, the approval threshold from `job_config.agent`.

    Args:
        fixture_group: Loaded moving-head rig.
        job_config: Loaded job config.
        available_templates: Template IDs the planner may choose from.
        xsq_output_path: Where the delivered .xsq goes; sidecars land beside it.
        fixture_config_path: Resolved path to the fixture config, for the render stage.

    Returns:
        Tuple of (pipeline, choreography graph, xLights mapping).
    """
    choreo_graph, xlights_mapping = build_moving_head_graph(fixture_group)
    pipeline = build_moving_heads_pipeline(
        display_groups=choreo_graph.to_planner_summary(),
        fixture_count=len(fixture_group.expand_fixtures()),
        available_templates=available_templates,
        max_iterations=job_config.agent.max_iterations,
        min_pass_score=job_config.agent.min_pass_score,
        xsq_output_path=xsq_output_path,
        fixture_config_path=fixture_config_path,
        fixture_groups=[
            {
                "fixture_id": fixture.fixture_id,
                "xlights_model_name": fixture.xlights_model_name,
                "channels": {
                    "pan": fixture.config.dmx_mapping.pan,
                    "tilt": fixture.config.dmx_mapping.tilt,
                    "dimmer": fixture.config.dmx_mapping.dimmer,
                    "color": fixture.config.dmx_mapping.color,
                    "gobo": fixture.config.dmx_mapping.gobo,
                    "shutter": fixture.config.dmx_mapping.shutter,
                },
            }
            for fixture in fixture_group.expand_fixtures()
        ],
        section_id=section_id,
        regeneration_nonce=regeneration_nonce,
    )
    return pipeline, choreo_graph, xlights_mapping


async def run_pipeline_async(
    audio_path: Path,
    output_dir: Path,
    app_config_path: Path,
    job_config_path: Path,
    session_id: str | None = None,
    template_dir: Path | None = None,
    allow_template_overrides: bool = False,
    live_injection: bool = False,
    dry_run: bool = False,
    section_id: str | None = None,
) -> int:
    """Run normally or hold one stateful xLights client across live planning/injection."""
    if live_injection:
        async with XLightsAutomationClient() as live_client:
            return await _run_pipeline_async(
                audio_path,
                output_dir,
                app_config_path,
                job_config_path,
                session_id,
                template_dir,
                allow_template_overrides,
                live_client=live_client,
                dry_run=dry_run,
                section_id=section_id,
            )
    return await _run_pipeline_async(
        audio_path,
        output_dir,
        app_config_path,
        job_config_path,
        session_id,
        template_dir,
        allow_template_overrides,
    )


async def _run_pipeline_async(
    audio_path: Path,
    output_dir: Path,
    app_config_path: Path,
    job_config_path: Path,
    session_id: str | None = None,
    template_dir: Path | None = None,
    allow_template_overrides: bool = False,
    *,
    live_client: XLightsAutomationClient | None = None,
    dry_run: bool = False,
    section_id: str | None = None,
) -> int:
    """Run the pipeline using the Pipeline Framework.

    Args:
        audio_path: Path to audio file
        output_dir: Output directory for artifacts
        app_config_path: Path to app config JSON
        job_config_path: Path to job config JSON
        session_id: Optional session ID override. When omitted, the ID is
            derived from the audio content and configs so an identical re-run
            reuses cached LLM work.
        template_dir: Optional directory of strict JSON moving-head templates.
        allow_template_overrides: Whether data documents may explicitly shadow
            colliding Python builtin IDs.

    Returns:
        Exit code (0 for success, 1 for failure)
    """
    # Load configuration
    console.print("[bold]Loading configuration...[/bold]")
    try:
        app_config = load_app_config(app_config_path)
        validate_llm_provider_config(app_config)
        job_config = load_job_config(job_config_path)
        console.print("[green]✅ Configuration loaded[/green]")
        console.print(f"   Provider: {app_config.llm_provider}")
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
    if template_dir is not None:
        try:
            loaded_ids = load_templates_from_directory(
                template_dir,
                allow_overrides=allow_template_overrides,
            )
        except (OSError, ValueError) as error:
            console.print(f"[red]ERROR: Could not load data templates: {error}[/red]")
            return 1
        console.print(
            f"[green]📄 Data templates loaded:[/green] {len(loaded_ids)} from {template_dir}"
        )
    available_templates = [t.template_id for t in list_templates()]
    console.print(f"[green]📚 Templates loaded:[/green] {len(available_templates)}")

    # Load the rig: the fixture config is the run's real input, so the planner is told
    # what the user actually owns instead of the literal 4 the CLI used to pass.
    fixture_config_path = _resolve_fixture_config_path(
        job_config_path,
        job_config.fixture_config_path,
    )
    try:
        fixture_group = load_fixture_group(fixture_config_path)
    except Exception as e:
        console.print(f"[red]ERROR: Could not load fixture config {fixture_config_path}: {e}[/red]")
        return 1

    console.print(
        f"[green]💡 Rig:[/green] {len(fixture_group.expand_fixtures())} moving head(s) "
        f"from {fixture_config_path.name}"
    )

    if live_client is not None:
        try:
            models = await live_client.get_models(
                GetModelsRequest(include_models=True, include_groups=False)
            )
            groups = await live_client.get_models(
                GetModelsRequest(include_models=False, include_groups=True)
            )
        except Exception as error:
            console.print(f"[red]ERROR: Could not read the live xLights layout: {error}[/red]")
            return 1
        reconciliation = reconcile_live_layout(
            fixture_group,
            model_names=models.models,
            group_names=groups.models,
        )
        fixture_group = reconciliation.rig
        if reconciliation.report.has_divergence:
            console.print(
                "[yellow]Live layout differs from fixture config; live names win:[/yellow] "
                f"configured-only={reconciliation.report.configured_only_models}, "
                f"live-only={reconciliation.report.live_only_models}, "
                f"missing-groups={reconciliation.report.missing_configured_groups}"
            )
        if not fixture_group.expand_fixtures():
            console.print(
                "[red]ERROR: No configured moving-head model names exist in the live layout; "
                "Twinklr will not guess DMX channel mappings.[/red]"
            )
            return 1

    # Define pipeline via pipeline definitions module
    console.print("\n[bold]Defining pipeline...[/bold]")
    try:
        pipeline, choreo_graph, xlights_mapping = build_run_pipeline(
            fixture_group=fixture_group,
            job_config=job_config,
            available_templates=available_templates,
            xsq_output_path=artifact_dir / f"{song_name}_twinklr_mh.xsq",
            fixture_config_path=fixture_config_path,
            section_id=section_id,
            regeneration_nonce=uuid4().hex if section_id is not None else None,
        )
    except ValueError as e:
        console.print(f"[red]ERROR: {e}[/red]")
        return 1
    console.print(
        f"[green]🗺️  Display groups:[/green] {len(choreo_graph.groups)} "
        f"(approval threshold {job_config.agent.success_threshold}/100)"
    )

    # Validate pipeline
    errors = pipeline.validate_pipeline()
    if errors:
        console.print(f"[red]Pipeline validation failed: {errors}[/red]")
        return 1

    console.print(f"[green]✅ Pipeline validated[/green] ({len(pipeline.stages)} stages)")

    # Derive a deterministic session ID so a re-run of the same job addresses
    # the same cache subtree instead of an unreachable random one.
    resolved_session_id = session_id or derive_session_id(
        audio_path=audio_path,
        configs=(app_config, job_config),
    )
    console.print(f"[green]🔑 Session:[/green] {resolved_session_id}")

    # Create session (manages provider, cache, logger lazily)
    session = TwinklrSession(
        app_config=app_config,
        job_config=job_config,
        session_id=resolved_session_id,
        project_root=job_config_path.parent,
    )

    # Create pipeline context
    pipeline_context = PipelineContext(
        session=session,
        output_dir=artifact_dir,
    )
    pipeline_context.set_state("job_config_dir", job_config_path.parent)
    pipeline_context.set_state("choreo_graph", choreo_graph)
    pipeline_context.set_state("xlights_mapping", xlights_mapping)
    if live_client is not None:
        pipeline_context.set_state("live_fixture_group", fixture_group)

    # Execute pipeline
    console.print(f"\n[bold]🎵 Processing:[/bold] {audio_path.name}")
    console.print("[bold]🚀 Starting pipeline execution...[/bold]\n")

    executor = PipelineExecutor()
    result = await executor.execute(
        pipeline=pipeline,
        initial_input=str(audio_path),
        context=pipeline_context,
    )

    if result.success and live_client is not None:
        segments = list(pipeline_context.get_state("rendered_segments", ()))
        try:
            live_effects = live_effects_from_segments(segments, fixture_group)
            workflow = LiveInjectionWorkflow(
                live_client,
                ownership=JsonOwnershipStore(artifact_dir / ".twinklr-live-ownership.json"),
            )
            injection = (
                await workflow.regenerate_section(section_id, live_effects, dry_run=dry_run)
                if section_id is not None
                else await workflow.inject(live_effects, dry_run=dry_run)
            )
        except InjectionPartialError as error:
            _print_live_injection_partial(error)
            return 1
        except Exception as error:
            console.print(f"[red]ERROR: Live injection stopped safely: {error}[/red]")
            return 1
        if injection.dry_run:
            console.print("[yellow]Dry run; exact planned xLights writes:[/yellow]")
            for command in injection.commands:
                console.print(json.dumps(command, sort_keys=True))
        else:
            console.print(
                f"[green]Live injection complete:[/green] {len(injection.injected)} added, "
                f"{len(injection.deleted)} replaced, {len(injection.unchanged)} unchanged. "
                "Twinklr did not save the sequence."
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
            segment_count = pipeline_context.metrics.get("mh_render_segments", 0)
            artifacts = pipeline_context.get_state("delivery_artifacts")
            console.print(f"\n[bold]🎄 Import into xLights:[/bold] ({segment_count} segments)")
            if artifacts is not None:
                console.print(f"   effects  {artifacts.xsq_path.name}")
                for xtiming_path in artifacts.xtiming_paths:
                    console.print(f"   timing   {xtiming_path.name}")
                console.print(f"   mapping  {artifacts.xmap_path.name}")
                console.print(f"   trace    {artifacts.trace_path.name}")
            else:
                console.print(f"   {result.outputs['render']}")

        console.print(f"\n[green]📁 All artifacts saved to:[/green] {artifact_dir}")
        return 0

    return 1


def run_pipeline(args: argparse.Namespace) -> None:
    """Run the full Twinklr pipeline."""
    configure_logging(level="INFO")

    audio_path = Path(args.audio).resolve()
    output_dir = Path(args.out).resolve()
    app_config_path = Path(args.app_config).resolve()
    job_config_path = Path(args.config).resolve()

    # Validate inputs
    if not audio_path.exists():
        console.print(f"[red]ERROR: Audio file not found: {audio_path}[/red]")
        sys.exit(1)

    if not job_config_path.exists():
        console.print(f"[red]ERROR: Job config not found: {job_config_path}[/red]")
        sys.exit(1)

    # Run async pipeline
    exit_code = asyncio.run(
        run_pipeline_async(
            audio_path=audio_path,
            output_dir=output_dir,
            app_config_path=app_config_path,
            job_config_path=job_config_path,
            session_id=args.session_id,
            template_dir=args.template_dir.resolve() if args.template_dir else None,
            allow_template_overrides=args.allow_template_overrides,
            live_injection=args.cmd in {"inject", "regenerate"},
            dry_run=getattr(args, "dry_run", False),
            section_id=getattr(args, "section", None),
        )
    )
    sys.exit(exit_code)


def build_arg_parser() -> argparse.ArgumentParser:
    """Build argument parser for CLI."""
    p = argparse.ArgumentParser(
        prog="twinklr",
        description="Twinklr - AI-powered lighting sequencer for xLights",
    )
    p.add_argument(
        "--fseqcmp",
        nargs=2,
        metavar=("EXPECTED.fseq", "ACTUAL.fseq"),
        help="Compare two rendered FSEQ files deterministically (headless/CI-safe).",
    )
    sub = p.add_subparsers(dest="cmd")

    # `--xsq` is deliberately absent. It used to be required, and every run parsed the
    # user's sequence, regenerated it and handed back a damaged copy. Twinklr now emits
    # its own files for the user to import, so there is no input sequence to take.
    # Removed outright rather than accepted-and-ignored: silently ignoring a flag that
    # used to decide what the output was built from is its own failure class.
    run = sub.add_parser("run", help="Run the full pipeline")
    _add_pipeline_arguments(run)

    inject = sub.add_parser(
        "inject",
        help="Plan against getModels and add effects to the already-open xLights sequence",
        description=(
            "Plan against the running xLights layout and inject into reserved layers "
            "starting at 99. "
            "The local automation port has no documented authentication: any local process "
            "can drive xLights while it is enabled. Twinklr never saves your sequence."
        ),
    )
    _add_pipeline_arguments(inject)
    inject.add_argument("--dry-run", action="store_true", help="Print exact writes only")

    regenerate = sub.add_parser(
        "regenerate",
        help="Re-plan and replace exactly one section in the already-open sequence",
        description=(
            "Re-plan one canonical section ID using cached analysis and replace only that "
            "section on reserved layers starting at 99. The unauthenticated local xLights "
            "port lets any local process drive the app; disable it when finished. Twinklr "
            "never saves."
        ),
    )
    regenerate.add_argument("section", help="Canonical unique section ID, e.g. chorus_2")
    _add_pipeline_arguments(regenerate)
    regenerate.add_argument("--dry-run", action="store_true", help="Print exact writes only")

    add_curate_catalog_subparser(sub)
    add_catalog_coverage_subparser(sub)
    add_review_staged_recipes_subparser(sub)
    add_template_subparsers(sub)
    add_display_subparser(sub)
    add_show_subparser(sub)
    add_show_eval_subparser(sub)

    # Registered only so `twinklr --help` lists it; `main()` dispatches "eval-report"
    # to click before argparse ever parses its arguments (see below — argparse's
    # REMAINDER cannot reliably swallow a leading `--option` token).
    sub.add_parser(
        "eval-report",
        help="Generate an evaluation report from a checkpoint (see `eval-report --help`)",
        add_help=False,
    )

    return p


def _add_pipeline_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--audio", required=True, help="Path to audio file (mp3/wav)")
    parser.add_argument("--out", default=".", help="Output directory (default: current dir)")
    parser.add_argument(
        "--app-config",
        default="config.json",
        help="Path to app config JSON (default: config.json)",
    )
    parser.add_argument(
        "--template-dir",
        type=Path,
        default=None,
        help="Directory of strict JSON moving-head templates loaded after Python builtins",
    )
    parser.add_argument(
        "--allow-template-overrides",
        action="store_true",
        help="Explicitly allow data templates to shadow colliding Python builtin ids",
    )
    parser.add_argument("--config", required=True, help="Path to job config JSON")
    parser.add_argument(
        "--session-id",
        default=None,
        help=(
            "Override the cache session ID (default: derived from audio content and configs, "
            "so identical re-runs reuse cached analysis)"
        ),
    )


def main() -> None:
    """Main entry point for CLI."""
    # Bridges the existing `eval-report` click command (reporting/evaluation/cli.py)
    # onto the twinklr console script by handing it argv directly, before argparse
    # parses anything. Keeps click as the single implementation of `eval-report`
    # instead of duplicating its options in argparse.
    if len(sys.argv) > 1 and sys.argv[1] == "eval-report":
        from twinklr.core.reporting.evaluation.cli import eval_report_cli

        eval_report_cli.main(args=sys.argv[2:], prog_name="twinklr eval-report")
        return

    p = build_arg_parser()
    args = p.parse_args()

    if args.fseqcmp is not None:
        expected_path, actual_path = (Path(path) for path in args.fseqcmp)
        sys.exit(run_fseqcmp_command(expected_path, actual_path))
    if args.cmd is None:
        p.error("a command or --fseqcmp EXPECTED.fseq ACTUAL.fseq is required")
    if args.cmd in {"run", "inject", "regenerate"}:
        run_pipeline(args)
    elif args.cmd == "curate-catalog":
        sys.exit(run_curate_catalog_command(args))
    elif args.cmd == "catalog-coverage":
        sys.exit(run_catalog_coverage_command(args))
    elif args.cmd == "review-staged-recipes":
        sys.exit(run_review_staged_recipes_command(args))
    elif args.cmd == "template-export":
        sys.exit(run_template_export_command(args))
    elif args.cmd == "template-validate":
        sys.exit(run_template_validate_command(args))
    elif args.cmd == "display":
        run_display_command(args)
    elif args.cmd == "show":
        run_show_command(args)
    elif args.cmd == "show-eval":
        sys.exit(run_show_eval_command(args))


if __name__ == "__main__":
    main()
