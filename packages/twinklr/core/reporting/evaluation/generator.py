"""Main report generation orchestrator.

This module coordinates all components to generate complete evaluation reports.
"""

from __future__ import annotations

import logging
from pathlib import Path

from twinklr.core.reporting.evaluation.analyze import analyze_curve, check_loop_continuity
from twinklr.core.reporting.evaluation.collect import (
    build_run_metadata,
    extract_plan,
    load_checkpoint,
)
from twinklr.core.reporting.evaluation.compliance import verify_template_compliance
from twinklr.core.reporting.evaluation.config import EvalConfig
from twinklr.core.reporting.evaluation.continuity import analyze_section_transition
from twinklr.core.reporting.evaluation.extract import extract_curves_from_segments
from twinklr.core.reporting.evaluation.models import (
    CurveAnalysis,
    EvaluationReport,
    ReportFlagLevel,
    ReportSummary,
    SectionReport,
    SongMetadata,
    TargetResolution,
    TemplateSelection,
    ValidationResult,
)
from twinklr.core.reporting.evaluation.physics import check_physics_constraints
from twinklr.core.reporting.evaluation.plot import plot_curve
from twinklr.core.reporting.evaluation.render import write_report_json, write_report_markdown
from twinklr.core.reporting.evaluation.rerender import rerender_plan
from twinklr.core.reporting.evaluation.validate import (
    load_available_templates,
    validate_plan_structure,
    validation_to_flags,
)

logger = logging.getLogger(__name__)


def _expand_plan_sections(plan):
    """Expand plan sections into individual sections per segment.

    This mimics the behavior of RenderingPipeline.iterate_plan_sections().

    Args:
        plan: ChoreographyPlan with potentially segmented sections

    Returns:
        List of PlanSection objects (one per segment)
    """
    from twinklr.core.agents.sequencer.moving_heads.models import PlanSection

    expanded = []
    for section in plan.sections:
        if section.segments:
            # Expand each segment into its own PlanSection
            for seg in section.segments:
                expanded.append(
                    PlanSection(
                        section_name=f"{section.section_name}|{seg.segment_id}",
                        start_bar=seg.start_bar,
                        end_bar=seg.end_bar,
                        section_role=section.section_role,
                        energy_level=section.energy_level,
                        template_id=seg.template_id,
                        preset_id=seg.preset_id,
                        modifiers=seg.modifiers,
                        reasoning=seg.reasoning or section.reasoning,
                        segments=None,  # Don't carry segments forward
                        # Inherit parent section's transition hints (if any)
                        transition_in=section.transition_in,
                        transition_out=section.transition_out,
                    )
                )
        else:
            # No segments, keep as-is
            expanded.append(section)

    return expanded


async def generate_evaluation_report(
    *,
    checkpoint_path: Path,
    audio_path: Path,
    fixture_config_path: Path,
    xsq_path: Path,
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
        xsq_path: Path to xLights sequence
        output_dir: Directory for output artifacts
        config: Optional evaluation configuration

    Returns:
        EvaluationReport object
    """
    if config is None:
        config = EvalConfig()

    logger.info(f"Generating evaluation report from {checkpoint_path.name}")

    # Load checkpoint
    logger.debug("Loading checkpoint...")
    checkpoint_data = load_checkpoint(checkpoint_path)
    plan = extract_plan(checkpoint_data)
    run_metadata = build_run_metadata(checkpoint_path, checkpoint_data)

    logger.debug(f"Loaded plan with {len(plan.sections)} sections")

    # Phase 2: Validate plan structure (if enabled)
    plan_validation: ValidationResult | None = None
    validation_errors_count = 0

    if config.enable_heuristic_validation:
        logger.info("Validating plan structure...")
        available_templates = load_available_templates()
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
            logger.info("Plan validation passed (%d warnings)", len(plan_validation.warnings))

    # Re-render plan (async)
    logger.info("Re-rendering plan through sequencer...")
    render_data = await rerender_plan(
        plan=plan,
        audio_path=audio_path,
        fixture_config_path=fixture_config_path,
        xsq_path=xsq_path,
    )

    logger.info(f"Re-rendered {len(render_data.segments)} segments")

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
    logger.info(
        f"Processing {len(expanded_sections)} sections (expanded from {len(plan.sections)} plan sections)..."
    )
    section_reports = []
    all_templates = set()
    all_roles = set()
    total_warnings = 0
    total_errors = 0
    physics_violations_count = 0
    compliance_issues_count = 0

    for plan_section in expanded_sections:
        section_report = _process_section(
            plan_section=plan_section,
            render_data=render_data,
            song_metadata=song_metadata,
            output_dir=output_dir,
            config=config,
        )
        section_reports.append(section_report)

        # Aggregate stats
        if section_report.selected_template:
            all_templates.add(section_report.selected_template.template_id)
        all_roles.update(section_report.targets.resolved_roles)
        total_warnings += sum(1 for f in section_report.flags if f.level == ReportFlagLevel.WARNING)
        total_errors += sum(1 for f in section_report.flags if f.level == ReportFlagLevel.ERROR)

        # Count physics violations
        for curve in section_report.curves:
            if curve.physics_check and (
                not curve.physics_check.speed_ok or not curve.physics_check.acceleration_ok
            ):
                physics_violations_count += len(curve.physics_check.violations)

        # Count compliance issues
        if (
            section_report.template_compliance
            and not section_report.template_compliance.overall_compliant
        ):
            compliance_issues_count += len(section_report.template_compliance.issues)

    # Phase 2: Analyze transitions between sections (if enabled)
    harsh_transitions_count = 0
    if config.enable_continuity_checks and len(section_reports) > 1:
        logger.info("Analyzing section transitions...")

        updated_sections = []
        for i in range(len(section_reports)):
            current_section = section_reports[i]

            # Check if there's a next section to transition to
            if i < len(section_reports) - 1:
                # Extract boundary curves for transition analysis
                current_end_ms = int(expanded_sections[i].end_bar * song_metadata.bar_duration_ms)
                next_start_ms = int(
                    expanded_sections[i + 1].start_bar * song_metadata.bar_duration_ms
                )

                # Extract last 10% of current section
                current_duration_ms = current_end_ms - int(
                    expanded_sections[i].start_bar * song_metadata.bar_duration_ms
                )
                boundary_window_ms = max(
                    100, int(current_duration_ms * 0.1)
                )  # Last 10% or 100ms min

                current_boundary_start = current_end_ms - boundary_window_ms
                current_boundary_curves = extract_curves_from_segments(
                    segments=render_data.segments,
                    section_window_ms=(current_boundary_start, current_end_ms),
                    samples_per_bar=config.samples_per_bar,
                    bar_duration_ms=song_metadata.bar_duration_ms,
                )

                # Extract first 10% of next section
                next_duration_ms = (
                    int(expanded_sections[i + 1].end_bar * song_metadata.bar_duration_ms)
                    - next_start_ms
                )
                next_boundary_window_ms = max(
                    100, int(next_duration_ms * 0.1)
                )  # First 10% or 100ms min

                next_boundary_end = next_start_ms + next_boundary_window_ms
                next_boundary_curves = extract_curves_from_segments(
                    segments=render_data.segments,
                    section_window_ms=(next_start_ms, next_boundary_end),
                    samples_per_bar=config.samples_per_bar,
                    bar_duration_ms=song_metadata.bar_duration_ms,
                )

                # Organize curves by role and channel for transition analysis
                from_curves_by_role: dict[str, dict[str, list[float]]] = {}
                for fixture_id, channels in current_boundary_curves.items():
                    # Find role for this fixture
                    fixture_ctx = next(
                        (f for f in render_data.fixture_contexts if f.fixture_id == fixture_id),
                        None,
                    )
                    role = fixture_ctx.role if fixture_ctx else fixture_id
                    from_curves_by_role[role] = channels

                to_curves_by_role: dict[str, dict[str, list[float]]] = {}
                for fixture_id, channels in next_boundary_curves.items():
                    fixture_ctx = next(
                        (f for f in render_data.fixture_contexts if f.fixture_id == fixture_id),
                        None,
                    )
                    role = fixture_ctx.role if fixture_ctx else fixture_id
                    to_curves_by_role[role] = channels

                # Analyze transition
                transition = analyze_section_transition(
                    from_section_name=expanded_sections[i].section_name,
                    to_section_name=expanded_sections[i + 1].section_name,
                    from_curves=from_curves_by_role,
                    to_curves=to_curves_by_role,
                    config=config,
                )

                # Count harsh transitions
                if not transition.smooth:
                    harsh_transitions_count += 1

                # Update section with transition
                updated_sections.append(
                    current_section.model_copy(update={"transition_to_next": transition})
                )
            else:
                # Last section - no transition
                updated_sections.append(current_section)

        # Replace section reports with updated versions
        section_reports = updated_sections

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
            # Phase 2 metrics
            validation_errors=validation_errors_count,
            physics_violations=physics_violations_count,
            compliance_issues=compliance_issues_count,
            harsh_transitions=harsh_transitions_count,
        ),
        sections=section_reports,  # Use updated section_reports with transitions
    )

    # Write outputs
    logger.info("Writing report outputs...")
    write_report_json(report, output_dir / "report.json")
    write_report_markdown(report, output_dir / "report.md")

    logger.info(f"✓ Report generated: {output_dir / 'report.md'}")
    return report


def _process_section(
    plan_section,
    render_data,
    song_metadata: SongMetadata,
    output_dir: Path,
    config: EvalConfig,
) -> SectionReport:
    """Process a single section: extract curves, analyze, plot.

    Args:
        plan_section: PlanSection from choreography plan
        render_data: RerenderResult from sequencer
        song_metadata: Song timing information
        output_dir: Output directory for plots
        config: Evaluation configuration

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

    # Calculate time window
    start_ms = int(plan_section.start_bar * song_metadata.bar_duration_ms)
    end_ms = int(plan_section.end_bar * song_metadata.bar_duration_ms)

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

    # Extract curves
    curves_by_fixture = extract_curves_from_segments(
        segments=render_data.segments,
        section_window_ms=(start_ms, end_ms),
        samples_per_bar=config.samples_per_bar,
        bar_duration_ms=song_metadata.bar_duration_ms,
    )

    # Analyze curves and generate plots
    curve_analyses = []
    section_flags = []

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
            # Extract metadata from segments for this fixture/channel
            curve_type = None
            handler = None
            base_position = None
            static_dmx = None

            for seg in render_data.segments:
                # Check if segment overlaps with section time window
                seg_overlaps = (
                    seg.fixture_id == fixture_id
                    and seg.t0_ms < end_ms  # Segment starts before section ends
                    and seg.t1_ms > start_ms  # Segment ends after section starts
                )
                if seg_overlaps:
                    if channel_name in seg.channels:
                        # Extract channel-specific metadata based on channel type
                        # channel_name is lowercase string like "pan", "tilt", "dimmer"
                        if channel_name.lower() == "pan":
                            curve_type = seg.metadata.get("pan_curve_type")
                            handler = seg.metadata.get("movement_handler")
                            base_position = seg.metadata.get("base_pan_norm")
                            static_dmx = seg.metadata.get("pan_static_dmx")
                        elif channel_name.lower() == "tilt":
                            curve_type = seg.metadata.get("tilt_curve_type")
                            handler = seg.metadata.get("movement_handler")
                            base_position = seg.metadata.get("base_tilt_norm")
                            static_dmx = seg.metadata.get("tilt_static_dmx")
                        elif channel_name.lower() == "dimmer":
                            curve_type = seg.metadata.get("dimmer_curve_type")
                            handler = seg.metadata.get("dimmer_handler")
                            static_dmx = seg.metadata.get("dimmer_static_dmx")

                        # Convert string values to proper types
                        if base_position and isinstance(base_position, str):
                            try:
                                base_position = float(base_position)
                            except ValueError:
                                base_position = None
                        if static_dmx and isinstance(static_dmx, str):
                            try:
                                static_dmx = int(static_dmx) if static_dmx != "None" else None
                            except ValueError:
                                static_dmx = None

                        break

            # Analyze
            stats, flags = analyze_curve(samples, config, curve_type=curve_type)
            continuity = check_loop_continuity(
                samples, config.loop_delta_threshold, curve_type=curve_type, channel=channel_name
            )

            # Phase 2: Physics constraints check (if enabled)
            physics_check = None
            if config.enable_physics_checks and channel_name.lower() in ["pan", "tilt"]:
                section_duration_ms = end_ms - start_ms
                physics_check = check_physics_constraints(
                    samples=samples,
                    channel=channel_name.lower(),  # type: ignore[arg-type]
                    duration_ms=section_duration_ms,
                    config=config,
                )

                # Add physics violation flags
                if not physics_check.speed_ok or not physics_check.acceleration_ok:
                    from .models import ReportFlag

                    for violation in physics_check.violations:
                        flags.append(
                            ReportFlag(
                                level=ReportFlagLevel.ERROR,
                                code="PHYSICS_VIOLATION",
                                message=violation,
                                details={
                                    "channel": channel_name,
                                    "max_speed": physics_check.max_speed_deg_per_sec,
                                    "max_accel": physics_check.max_accel_deg_per_sec2,
                                },
                            )
                        )

            # Check continuity flag
            if not continuity.ok:
                from .models import ReportFlag

                flags.append(
                    ReportFlag(
                        level=ReportFlagLevel.WARNING,
                        code="LOOP_DISCONTINUITY",
                        message=f"Loop discontinuity: delta={continuity.loop_delta:.3f}",
                        details={"loop_delta": continuity.loop_delta},
                    )
                )

            # Plot
            # Create filename with section_id and segment_id
            if segment_id:
                plot_filename = f"{section_id}_seg{segment_id}__{role}__{channel_name.lower()}.png"
            else:
                plot_filename = f"{section_id}__{role}__{channel_name.lower()}.png"
            plot_path = output_dir / "plots" / plot_filename

            # Format curve type for display
            display_curve_type = curve_type
            if display_curve_type and display_curve_type.startswith("CurveKind."):
                # Remove enum prefix for cleaner display
                display_curve_type = display_curve_type.replace("CurveKind.", "")

            plot_curve(
                samples=samples,
                title=f"{display_label} • {role} • {channel_name.upper()}",
                output_path=plot_path,
                space="dmx",
                bar_range=(plan_section.start_bar, plan_section.end_bar),
                curve_type=display_curve_type,
                section_bar_range=(plan_section.start_bar, plan_section.end_bar),
            )

            curve_analyses.append(
                CurveAnalysis(
                    role=role,
                    channel=channel_name,
                    space="dmx",  # Changed to DMX
                    plot_path=plot_path,
                    stats=stats,
                    continuity=continuity,
                    curve_type=curve_type,
                    handler=handler,
                    base_position=base_position,
                    static_dmx=static_dmx,
                    physics_check=physics_check,  # Phase 2: Add physics check
                )
            )

            section_flags.extend(flags)

    # Phase 2: Template compliance check (if enabled)
    template_compliance = None
    if config.enable_compliance_checks and plan_section.template_id:
        template_compliance = verify_template_compliance(
            template_id=plan_section.template_id,
            modifiers=plan_section.modifiers or {},
            curves=curve_analyses,
            metadata={},  # Could add more metadata from segments
        )

        # Add compliance issues as flags
        if not template_compliance.overall_compliant:
            from .models import ReportFlag

            for issue in template_compliance.issues:
                section_flags.append(
                    ReportFlag(
                        level=ReportFlagLevel.WARNING,
                        code="COMPLIANCE_ISSUE",
                        message=issue,
                        details={"template_id": plan_section.template_id},
                    )
                )

    # Build template selection
    template_selection = None
    if plan_section.template_id:
        template_selection = TemplateSelection(
            template_id=plan_section.template_id,
            preset_id=plan_section.preset_id,
            modifiers=plan_section.modifiers,
            reasoning=plan_section.reasoning,
            steps=[],
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
        template_compliance=template_compliance,  # Phase 2
    )
