"""Main report generation orchestrator.

This module coordinates all components to generate complete evaluation reports.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Mapping
from fractions import Fraction
import logging
from pathlib import Path
import sys
from typing import Any

from twinklr.core.config.fixtures import AxisCapability, FixtureCapabilities
from twinklr.core.formats.xlights.sequence.fresh import EFFECT_GRID_MS
from twinklr.core.reporting.evaluation.analyze import (
    largest_step,
    lit_motion,
    physical_channel_stats,
)
from twinklr.core.reporting.evaluation.collect import (
    build_run_metadata,
    extract_plan,
    load_checkpoint,
    recorded_render,
)
from twinklr.core.reporting.evaluation.config import EvalConfig
from twinklr.core.reporting.evaluation.extract import physical_channel_values
from twinklr.core.reporting.evaluation.models import (
    CurveAnalysis,
    EvaluationReport,
    LitStep,
    PhysicalRenderSummary,
    ReportFlag,
    ReportFlagLevel,
    ReportSummary,
    SectionRenderFacts,
    SectionReport,
    SongMetadata,
    TargetResolution,
    TemplateSelection,
    ValidationResult,
)
from twinklr.core.reporting.evaluation.plot import plot_curve
from twinklr.core.reporting.evaluation.render import write_report_json, write_report_markdown
from twinklr.core.reporting.evaluation.rerender import (
    PhysicalRerender,
    admit_plan_templates,
    rerender_plan,
)
from twinklr.core.reporting.evaluation.validate import (
    load_available_templates,
    validate_plan_structure,
    validation_to_flags,
)
from twinklr.core.sequencer.models.enum import ChannelName
from twinklr.core.sequencer.models.moving_heads.physical import AXIS_KEYS
from twinklr.core.sequencer.moving_heads.export.frame_encoder import quantize_cue

logger = logging.getLogger(__name__)


def _expand_plan_sections(plan):
    """Expand plan sections into individual sections per segment.

    This mimics the behavior of RenderingPipeline.iterate_plan_sections().

    Args:
        plan: ChoreographyPlan with potentially segmented sections

    Returns:
        List of PlanSection objects (one per segment)
    """
    from twinklr.core.agents.sequencer.moving_heads.models import flatten_plan_segment

    expanded = []
    for section in plan.sections:
        if section.segments:
            # Expand each segment into its own PlanSection
            for seg in section.segments:
                expanded.append(flatten_plan_segment(section, seg))
        else:
            # No segments, keep as-is
            expanded.append(section)

    return expanded


async def generate_evaluation_report(
    *,
    checkpoint_path: Path,
    audio_path: Path,
    fixture_config_path: Path,
    output_dir: Path,
    config: EvalConfig | None = None,
) -> EvaluationReport:
    """Generate complete evaluation report from checkpoint (async).

    This is the main entry point for report generation. It:
    1. Loads checkpoint and extracts plan
    2. Re-renders plan through sequencer (async)
    3. Extracts and analyzes curves
    4. Generates plots
    5. Writes JSON and Markdown reports

    Args:
        checkpoint_path: Path to checkpoint JSON
        audio_path: Path to audio file
        fixture_config_path: Path to fixture config
        output_dir: Directory for output artifacts
        config: Optional evaluation configuration

    Returns:
        EvaluationReport object
    """
    if config is None:
        config = EvalConfig()

    logger.debug(f"Generating evaluation report from {checkpoint_path.name}")

    # Load checkpoint
    logger.debug("Loading checkpoint...")
    checkpoint_data = load_checkpoint(checkpoint_path)
    plan = extract_plan(checkpoint_data)
    run_metadata = build_run_metadata(checkpoint_path, checkpoint_data)
    # A checkpoint without the run's recorded render is refused here, before any audio
    # is analyzed.
    recorded = recorded_render(checkpoint_data)
    # The templates the run could name, loaded before the plan is validated; a plan
    # naming any other is refused here too.
    admit_plan_templates(plan)

    logger.debug(f"Loaded plan with {len(plan.sections)} sections")

    # Phase 2: Validate plan structure (if enabled)
    plan_validation: ValidationResult | None = None
    validation_errors_count = 0

    if config.enable_heuristic_validation:
        logger.debug("Validating plan structure...")
        # The plan could name only what the run's gate admitted (without a gate result:
        # the registry, the family catalog loaded).
        available_templates = (
            list(recorded.admission.admitted)
            if recorded.admission is not None
            else load_available_templates()
        )
        song_structure = {
            "sections": checkpoint_data.get("context", {})
            .get("song_structure", {})
            .get("sections", []),
            "total_bars": checkpoint_data.get("context", {})
            .get("song_structure", {})
            .get("total_bars"),
        }

        plan_validation = validate_plan_structure(
            plan=plan,
            available_templates=available_templates,
            song_structure=song_structure,
        )

        validation_errors_count = len(plan_validation.errors)

        if not plan_validation.valid:
            logger.warning(
                "Plan validation failed: %d errors, %d warnings",
                len(plan_validation.errors),
                len(plan_validation.warnings),
            )
        else:
            logger.debug("Plan validation passed (%d warnings)", len(plan_validation.warnings))

    # Re-render plan (async)
    logger.debug("Re-rendering plan through sequencer...")
    render_data = await rerender_plan(
        plan=plan,
        audio_path=audio_path,
        fixture_config_path=fixture_config_path,
        recorded=recorded,
    )
    physical = render_data.physical
    # Every fixture's values over the whole song, read once (index: frame start / 20 ms).
    song_values = physical_channel_values(physical.frames, physical.profiles, (0, sys.maxsize))

    logger.debug(f"Re-rendered {len(render_data.segments)} segments")

    # Build song metadata
    tempo_info = render_data.song_features.get("tempo", {})
    structure_info = render_data.song_features.get("structure", {})

    song_metadata = SongMetadata(
        bpm=tempo_info.get("bpm", render_data.beat_grid.tempo_bpm),
        time_signature=f"{render_data.beat_grid.beats_per_bar}/4",
        bars_total=int(render_data.beat_grid.total_bars),
        bar_duration_ms=render_data.beat_grid.ms_per_bar,
        song_structure=structure_info,
    )

    # Expand plan sections (segments → individual sections)
    # This matches the rendering pipeline's behavior
    expanded_sections = _expand_plan_sections(plan)

    # Process sections
    logger.debug(
        f"Processing {len(expanded_sections)} sections (expanded from {len(plan.sections)} plan sections)..."
    )
    section_reports = []
    all_templates = set()
    all_roles = set()
    total_warnings = 0
    total_errors = 0

    for plan_section in expanded_sections:
        section_report = _process_section(
            plan_section=plan_section,
            render_data=render_data,
            song_metadata=song_metadata,
            output_dir=output_dir,
            config=config,
            song_values=song_values,
        )
        section_reports.append(section_report)

        # Aggregate stats
        if section_report.selected_template:
            all_templates.add(section_report.selected_template.template_id)
        all_roles.update(section_report.targets.resolved_roles)
        total_warnings += sum(1 for f in section_report.flags if f.level == ReportFlagLevel.WARNING)
        total_errors += sum(1 for f in section_report.flags if f.level == ReportFlagLevel.ERROR)

    # Add global validation flags if present
    if plan_validation and not plan_validation.valid:
        validation_flags = validation_to_flags(plan_validation)
        # Prepend validation flags to first section's flags
        if section_reports:
            first_section = section_reports[0]
            # Create new section with updated flags (since it's frozen)
            updated_flags = validation_flags + list(first_section.flags)
            section_reports[0] = first_section.model_copy(
                update={"flags": updated_flags, "validation_issues": plan_validation.errors}
            )

    physical_summary = _physical_summary(physical)
    if not physical_summary.fingerprint_matches:
        # Reported, not hidden: every metric below describes the re-render.
        total_errors += 1
        mismatch = ReportFlag(
            level=ReportFlagLevel.ERROR,
            code="RENDER_FINGERPRINT_MISMATCH",
            message=mismatch_message(physical_summary),
            details={"mismatched_inputs": physical_summary.mismatched_inputs},
        )
        if section_reports:
            first_section = section_reports[0]
            section_reports[0] = first_section.model_copy(
                update={"flags": [mismatch, *first_section.flags]}
            )

    # Build report
    report = EvaluationReport(
        run=run_metadata,
        song=song_metadata,
        summary=ReportSummary(
            sections=len(section_reports),
            total_warnings=total_warnings,
            total_errors=total_errors,
            max_concurrent_layers=0,  # TODO: compute
            templates_used=sorted(all_templates),
            roles_targeted=sorted(all_roles),
            validation_errors=validation_errors_count,
        ),
        sections=section_reports,
        physical=physical_summary,
    )

    # Write outputs
    logger.debug("Writing report outputs...")
    write_report_json(report, output_dir / "report.json")
    write_report_markdown(report, output_dir / "report.md")

    logger.debug(f"✓ Report generated: {output_dir / 'report.md'}")
    return report


def _process_section(
    plan_section,
    render_data,
    song_metadata: SongMetadata,
    output_dir: Path,
    config: EvalConfig,
    song_values: dict[str, dict[str, list[float]]] | None = None,
) -> SectionReport:
    """Process a single section: extract curves, analyze, plot.

    Args:
        plan_section: PlanSection from choreography plan
        render_data: RerenderResult from sequencer
        song_metadata: Song timing information
        output_dir: Output directory for plots
        config: Evaluation configuration
        song_values: The render's per-frame values over the song
            (`physical_channel_values`)

    Returns:
        SectionReport with analysis and plots
    """
    # Parse section_id and segment_id from section_name
    # Format: "section_name|segment_id" or just "section_name"
    if "|" in plan_section.section_name:
        section_id, segment_id = plan_section.section_name.split("|", 1)
    else:
        section_id = plan_section.section_name
        segment_id = None

    physical = render_data.physical

    # Calculate time window: a section spans its bars on the detected grid, as the
    # renderer places it.
    start_ms = int(render_data.beat_grid.get_bar_start_ms(plan_section.start_bar - 1))
    end_ms = int(render_data.beat_grid.get_bar_start_ms(plan_section.end_bar))

    # Create display label
    if segment_id:
        display_label = f"{section_id.replace('_', ' ').title()} (Segment {segment_id})"
    else:
        display_label = section_id.replace("_", " ").title()

    logger.debug(
        f"Processing {display_label}: "
        f"bars {plan_section.start_bar}-{plan_section.end_bar}, "
        f"time {start_ms}-{end_ms}ms"
    )

    # The frames the section's cues land on: its bounds quantized as cues are.
    frames_ms = (quantize_cue(start_ms).actual_ms, quantize_cue(end_ms).actual_ms)
    curves_by_fixture = _frame_slice(song_values or {}, frames_ms)

    # Analyze curves and generate plots
    curve_analyses = []
    section_flags = []
    render_facts = _section_facts(physical.render_record, plan_section.section_name, frames_ms)
    render_facts = render_facts.model_copy(
        update={
            "lit_steps": _lit_steps(curves_by_fixture, physical.profiles, frames_ms[0]),
            "boundary_steps": _boundary_steps(
                song_values or {}, physical.profiles, render_facts.entry_windows, frames_ms[0]
            ),
        }
    )
    section_flags.extend(_section_fact_flags(render_facts, section_end_ms=end_ms))

    # Get fixture contexts with roles
    fixture_contexts = render_data.fixture_contexts

    if config.plot_all_roles:
        fixtures_to_plot = list(curves_by_fixture.keys())
    elif config.roles_to_plot:
        # Filter by role names
        fixtures_to_plot = [
            f.fixture_id for f in fixture_contexts if f.role in config.roles_to_plot
        ]
    else:
        # Auto-select first fixture
        fixtures_to_plot = list(curves_by_fixture.keys())[:1] if curves_by_fixture else []

    for fixture_id in fixtures_to_plot:
        if fixture_id not in curves_by_fixture:
            continue

        # Get role for this fixture
        fixture_ctx = next(
            (f for f in fixture_contexts if f.fixture_id == fixture_id),
            None,
        )
        role = fixture_ctx.role if fixture_ctx else fixture_id

        fixture_curves = curves_by_fixture[fixture_id]

        for channel_name, samples in fixture_curves.items():
            if segment_id:
                plot_filename = f"{section_id}_seg{segment_id}__{role}__{channel_name.lower()}.png"
            else:
                plot_filename = f"{section_id}__{role}__{channel_name.lower()}.png"
            space = "normalized" if channel_name == ChannelName.DIMMER.value else "degree"
            plot_path = output_dir / "plots" / plot_filename
            plot_curve(
                samples=samples,
                title=f"{display_label} • {role} • {channel_name.upper()}",
                output_path=plot_path,
                space=space,
                bar_range=(plan_section.start_bar, plan_section.end_bar),
                section_bar_range=(plan_section.start_bar, plan_section.end_bar),
            )
            lit = (
                None
                if channel_name == ChannelName.DIMMER.value
                else lit_motion(
                    samples, fixture_curves[ChannelName.DIMMER.value], frame_ms=EFFECT_GRID_MS
                )
            )
            curve_analyses.append(
                CurveAnalysis(
                    role=role,
                    channel=channel_name,
                    space=space,
                    plot_path=plot_path,
                    stats=physical_channel_stats(samples, frame_ms=EFFECT_GRID_MS),
                    lit_range=None if lit is None else lit[0],
                    lit_rate=None if lit is None else lit[1],
                )
            )

    # Build template selection
    template_selection = None
    if plan_section.template_id:
        template_selection = TemplateSelection(
            template_id=plan_section.template_id,
            preset_id=plan_section.preset_id,
            modifiers={modifier.key: modifier.value for modifier in plan_section.modifiers},
            reasoning=plan_section.reasoning,
        )

    return SectionReport(
        section_id=section_id,
        label=display_label,
        bar_range=(plan_section.start_bar, plan_section.end_bar),
        time_range_ms=(start_ms, end_ms),
        selected_template=template_selection,
        segments=None,  # Segments are now processed individually
        targets=TargetResolution(
            bindings={},
            resolved_roles=[f.role for f in render_data.fixture_contexts],
        ),
        curves=curve_analyses,
        flags=section_flags,
        render_facts=render_facts,
    )


def _physical_summary(physical: PhysicalRerender) -> PhysicalRenderSummary:
    """The re-render's identity against the run's, and the gate's facts it traced."""
    record = physical.render_record
    matches = physical.fingerprint == physical.run_fingerprint
    dark_spans = record.get("dark_spans", [])
    return PhysicalRenderSummary(
        run_fingerprint=physical.run_fingerprint,
        rerender_fingerprint=physical.fingerprint,
        fingerprint_matches=matches,
        mismatched_inputs=(
            [] if matches else _mismatched_inputs(physical.run_inputs, physical.rerender_inputs)
        ),
        dark_spans=dark_spans,
        dark_span_ms=sum(end - start for start, end in dark_spans),
        admission_exclusions=record.get("admission_exclusions", []),
        admission_preset_exclusions=record.get("admission_preset_exclusions", []),
        admission_effective_presets=record.get("admission_effective_presets", {}),
        unplayable_totals=record["unplayable_totals"],
    )


def mismatch_message(physical: PhysicalRenderSummary) -> str:
    """What a fingerprint mismatch means, naming the recorded inputs that differ."""
    differs = (
        "it differs in " + "; ".join(physical.mismatched_inputs)
        if physical.mismatched_inputs
        else "no recorded input differs (fixture profiles and model names, the rig, "
        "templates, beat grid, dark spans, revisions), so the checkpoint's plan or "
        "recorded policy, or the recorded identity itself differ"
    )
    return (
        f"the re-render's fingerprint {physical.rerender_fingerprint} does not match the "
        f"run's {physical.run_fingerprint}: this report describes a different render than "
        f"the run delivered; {differs}"
    )


def _mismatched_inputs(run: Mapping[str, Any], rerender: Mapping[str, Any]) -> list[str]:
    """Each input the run recorded that the re-render's does not match, both as
    `RenderingPipeline.checkpoint_record` gives them (`inputs`)."""
    differs = []
    run_fixtures = {f["fixture_id"]: f for f in run.get("fixtures", [])}
    rerender_fixtures = {f["fixture_id"]: f for f in rerender["fixtures"]}
    for fixture_id in sorted(run_fixtures.keys() | rerender_fixtures.keys()):
        before, after = run_fixtures.get(fixture_id), rerender_fixtures.get(fixture_id)
        if before is None or after is None:
            where = "the re-render's rig" if after is None else "the run's rig"
            differs.append(f"fixture {fixture_id!r}: missing from {where}")
            continue
        if before.get("profile_sha256") != after["profile_sha256"]:
            differs.append(f"fixture {fixture_id!r}: physical profile")
        if before.get("xlights_model_name") != after["xlights_model_name"]:
            differs.append(f"fixture {fixture_id!r}: xLights model name")
    run_rig, rerender_rig = run["rig"], rerender["rig"]
    fields = ", ".join(
        sorted(
            name
            for name in run_rig["fields"].keys() | rerender_rig["fields"].keys()
            if run_rig["fields"].get(name) != rerender_rig["fields"].get(name)
        )
    )
    if fields:
        differs.append(
            "rig (fixture group): the run rendered on its rig as reconciled with the live "
            f"xLights layout, which differs from this fixture config in {fields}"
            if run_rig["live_layout"]
            else f"rig (fixture group): {fields}"
        )
    run_templates = run.get("template_sha256", {})
    rerender_templates = rerender["template_sha256"]
    for template_id in sorted(run_templates.keys() | rerender_templates.keys()):
        if run_templates.get(template_id) != rerender_templates.get(template_id):
            differs.append(f"template {template_id!r}")
    if run.get("beat_grid_sha256") != rerender["beat_grid_sha256"]:
        differs.append("beat grid")
    if run.get("dark_spans", []) != rerender.get("dark_spans", []):
        differs.append("dark spans")
    for key, name in (
        ("renderer_revision", "renderer revision"),
        ("encoder_version", "encoder version"),
    ):
        if run.get(key) != rerender[key]:
            differs.append(name)
    return differs


def _frame_slice(
    song_values: dict[str, dict[str, list[float]]], frames_ms: tuple[int, int]
) -> dict[str, dict[str, list[float]]]:
    """Each fixture's values over the frames starting in `[start, end)`."""
    first, stop = (bound // EFFECT_GRID_MS for bound in frames_ms)
    return {
        fixture_id: {channel: values[first:stop] for channel, values in channels.items()}
        for fixture_id, channels in song_values.items()
    }


def _travel_axis(profile: FixtureCapabilities, channel: str) -> AxisCapability | None:
    """The pose axis of `channel` when it has a configured travel speed."""
    if channel == ChannelName.DIMMER.value:
        return None
    axis = profile.axes.get(AXIS_KEYS[ChannelName(channel)])
    return None if axis is None or axis.travel_speed_per_s is None else axis


def _allowed_step(profile: FixtureCapabilities, channel: str, interval_ms: int) -> float | None:
    """The largest change a pose axis' configured travel speed allows over an interval,
    plus one DMX word (the follow model lets a head lag one word); None for the dimmer
    or an axis without a travel speed. For display: `_beyond_travel` decides."""
    axis = _travel_axis(profile, channel)
    if axis is None:
        return None
    assert axis.travel_speed_per_s is not None
    word_min, word_max = axis.word_range
    per_word = (axis.physical_max - axis.physical_min) / (word_max - word_min)
    return axis.travel_speed_per_s * interval_ms / 1000 + per_word


def _beyond_travel(
    profile: FixtureCapabilities, channel: str, change: float, interval_ms: int
) -> bool:
    """Whether a decoded change exceeds the travel speed over the interval plus one DMX
    word, decided exactly in words: the change is a whole number of words (decoded
    values differ by whole words), and the allowance is exact in fractions."""
    axis = _travel_axis(profile, channel)
    if axis is None:
        return False
    assert axis.travel_speed_per_s is not None
    word_min, word_max = axis.word_range
    words_per_unit = (word_max - word_min) / (
        Fraction(axis.physical_max) - Fraction(axis.physical_min)
    )
    words = round(abs(Fraction(change)) * words_per_unit)
    allowed = Fraction(axis.travel_speed_per_s) * interval_ms / 1000 * words_per_unit + 1
    return words > allowed


def _lit_steps(
    values: dict[str, dict[str, list[float]]],
    profiles: dict[str, FixtureCapabilities],
    start_ms: int,
) -> list[LitStep]:
    """Per fixture and channel, the largest step between consecutive frames of the
    section: between two lit frames for pan, tilt and zoom; any two for the dimmer."""
    steps = []
    for fixture_id, channels in values.items():
        intensity = channels[ChannelName.DIMMER.value]
        for channel, samples in channels.items():
            dimmer = channel == ChannelName.DIMMER.value
            found = largest_step(
                samples,
                start_ms=start_ms,
                frame_ms=EFFECT_GRID_MS,
                lit=None if dimmer else intensity,
            )
            if found is None:
                continue
            change, from_ms, to_ms = found
            index = (from_ms - start_ms) // EFFECT_GRID_MS
            steps.append(
                LitStep(
                    fixture_id=fixture_id,
                    channel=channel,
                    from_ms=from_ms,
                    to_ms=to_ms,
                    change=change,
                    lit=intensity[index] > 0 and intensity[index + 1] > 0,
                    allowed=_allowed_step(profiles[fixture_id], channel, to_ms - from_ms),
                    beyond_travel=_beyond_travel(
                        profiles[fixture_id], channel, change, to_ms - from_ms
                    ),
                )
            )
    return steps


def _boundary_steps(
    song_values: dict[str, dict[str, list[float]]],
    profiles: dict[str, FixtureCapabilities],
    entry_windows: list[dict[str, Any]],
    start_ms: int,
) -> list[LitStep]:
    """For each fixture whose entry is `skipped` (it plays through the boundary), the
    change in each channel from its last lit frame before the section to the section's
    first frame."""
    steps = []
    first = start_ms // EFFECT_GRID_MS
    for window in entry_windows:
        if window["action"] != "skipped":
            continue
        fixture_id = window["fixture_id"]
        channels = song_values[fixture_id]
        intensity = channels[ChannelName.DIMMER.value]
        if first >= len(intensity):
            continue
        last_lit = next((i for i in range(first - 1, -1, -1) if intensity[i] > 0), None)
        if last_lit is None:
            continue
        for channel, samples in channels.items():
            interval = (first - last_lit) * EFFECT_GRID_MS
            change = samples[first] - samples[last_lit]
            steps.append(
                LitStep(
                    fixture_id=fixture_id,
                    channel=channel,
                    from_ms=last_lit * EFFECT_GRID_MS,
                    to_ms=start_ms,
                    change=change,
                    lit=intensity[first] > 0,
                    allowed=_allowed_step(profiles[fixture_id], channel, interval),
                    beyond_travel=_beyond_travel(profiles[fixture_id], channel, change, interval),
                )
            )
    return steps


def _section_facts(
    record: dict[str, Any], section_name: str, window_ms: tuple[int, int]
) -> SectionRenderFacts:
    """A section's records from a physical render's trace: its entry windows, dropped
    cues and diagnostics by section id, and the transactions of cues starting in it."""
    start_ms, end_ms = window_ms
    statuses = Counter(
        transaction["status"]
        for transaction in record["transactions"]
        if start_ms <= transaction["cue_ms"] < end_ms
    )
    return SectionRenderFacts(
        entry_windows=[w for w in record["entry_windows"] if w["section_id"] == section_name],
        dropped_cues=[c for c in record["dropped_cues"] if c["section_id"] == section_name],
        transactions=dict(sorted(statuses.items())),
        diagnostics=[d for d in record["diagnostics"] if d["section_id"] == section_name],
    )


def _section_fact_flags(facts: SectionRenderFacts, *, section_end_ms: int) -> list[ReportFlag]:
    """A warning for the cues the render kept dark, for each head whose entry window
    outlasts the section (it renders the section dark), for each lit step beyond the
    head's travel speed, and a flag per render diagnostic."""
    flags = []
    if facts.dropped_cues:
        reasons = Counter(str(cue["reason"]) for cue in facts.dropped_cues)
        flags.append(
            ReportFlag(
                level=ReportFlagLevel.WARNING,
                code="CUES_KEPT_DARK",
                message=f"{len(facts.dropped_cues)} cue(s) kept dark ("
                + ", ".join(f"{reason}: {count}" for reason, count in sorted(reasons.items()))
                + ")",
                details={"reasons": dict(sorted(reasons.items()))},
            )
        )
    for window in facts.entry_windows:
        end = window.get("window_end_ms")
        if end is not None and end >= section_end_ms:
            flags.append(
                ReportFlag(
                    level=ReportFlagLevel.WARNING,
                    code="SECTION_DARK_FOR_ENTRY",
                    message=(
                        f"{window['fixture_id']} stays dark through the section: its entry "
                        f"window ends at {end} ms, at or after the section's end "
                        f"({section_end_ms} ms)"
                    ),
                    details={"fixture_id": window["fixture_id"], "window_end_ms": end},
                )
            )
    for step in (*facts.lit_steps, *facts.boundary_steps):
        if step.lit and step.beyond_travel:
            flags.append(
                ReportFlag(
                    level=ReportFlagLevel.WARNING,
                    code="LIT_STEP_EXCEEDS_TRAVEL",
                    message=(
                        f"{step.fixture_id} {step.channel} moves {step.change:+.3f}° lit "
                        f"from {step.from_ms} ms to {step.to_ms} ms, beyond the "
                        f"{step.allowed:.3f}° its travel speed allows plus one DMX word"
                    ),
                    details=step.model_dump(mode="json"),
                )
            )
    levels = {"error": ReportFlagLevel.ERROR, "warning": ReportFlagLevel.WARNING}
    for diagnostic in facts.diagnostics:
        flags.append(
            ReportFlag(
                level=levels.get(diagnostic["severity"], ReportFlagLevel.INFO),
                code="RENDER_DIAGNOSTIC",
                message=diagnostic["message"],
                details={"code": diagnostic["code"]},
            )
        )
    return flags
