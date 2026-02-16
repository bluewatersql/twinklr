from __future__ import annotations

import logging
from collections.abc import Iterator
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from twinklr.core.sequencer.models.context import FixtureContext

from twinklr.core.agents.sequencer.moving_heads import ChoreographyPlan
from twinklr.core.agents.sequencer.moving_heads.models import PlanSection
from twinklr.core.config.fixtures import FixtureGroup
from twinklr.core.config.models import JobConfig
from twinklr.core.curves.generator import CurveGenerator
from twinklr.core.curves.registry import CurveRegistry
from twinklr.core.formats.xlights.sequence.models.xsq import (
    TimeMarker,
    TimingTrack,
)
from twinklr.core.sequencer.models.context import TemplateCompileContext
from twinklr.core.sequencer.models.enum import Intensity
from twinklr.core.sequencer.models.moving_heads.rig import rig_profile_from_fixture_group
from twinklr.core.sequencer.models.transition import TransitionRegistry
from twinklr.core.sequencer.moving_heads.channels.state import FixtureSegment
from twinklr.core.sequencer.moving_heads.compile.channel_blender import ChannelBlender
from twinklr.core.sequencer.moving_heads.compile.template_compiler import (
    compile_template,
)
from twinklr.core.sequencer.moving_heads.compile.transition_detector import TransitionDetector
from twinklr.core.sequencer.moving_heads.compile.transition_planner import TransitionPlanner
from twinklr.core.sequencer.moving_heads.compile.transition_segment_compiler import (
    TransitionSegmentCompiler,
)
from twinklr.core.sequencer.moving_heads.fixture_builder import build_fixture_contexts
from twinklr.core.sequencer.moving_heads.handlers.defaults import create_default_registries
from twinklr.core.sequencer.moving_heads.templates import (
    get_template,
    load_builtin_templates,
)
from twinklr.core.sequencer.moving_heads.xsq_export import export_to_xsq
from twinklr.core.sequencer.timing.beat_grid import BeatGrid

logger = logging.getLogger(__name__)

# --- Module-level constants and helpers ---

ENERGY_TO_INTENSITY: dict[str, Intensity] = {
    "CHILL": Intensity.SLOW,
    "MODERATE": Intensity.SMOOTH,
    "ENERGETIC": Intensity.DRAMATIC,
    "INTENSE": Intensity.FAST,
}
"""Maps energy-level keywords (from preset IDs) to movement Intensity enums."""


def _compute_section_duration_ms(
    start_bar: int, end_bar: int, ms_per_bar: float
) -> int:
    """Compute the duration of a section in milliseconds.

    Args:
        start_bar: First bar of the section (1-indexed).
        end_bar: Last bar of the section (1-indexed, inclusive).
        ms_per_bar: Milliseconds per bar from the beat grid.

    Returns:
        Duration in milliseconds (rounded to int).
    """
    return int((end_bar - start_bar + 1) * ms_per_bar)


class RenderingPipeline:
    """Rendering pipeline for moving heads."""

    def __init__(
        self,
        *,
        choreography_plan: ChoreographyPlan,
        beat_grid: BeatGrid,
        fixture_group: FixtureGroup,
        job_config: JobConfig,
        output_path: Path | None = None,
        template_xsq: Path | None = None,
        timeline_tracks: list[TimingTrack] | None = None,
    ):
        """Initialize rendering pipeline.

        Args:
            choreography_plan: Choreography plan from agent orchestrator
            beat_grid: Beat grid for musical timing
            fixture_group: Fixture configuration
            job_config: Job configuration
            output_path: Optional output path for XSQ file
            template_xsq: Optional template XSQ path
            timeline_tracks: Optional pre-built timeline tracks (beats, bars, lyrics, etc.)
        """
        self.choreography_plan = choreography_plan
        self.fixture_group = fixture_group
        self.job_config = job_config
        self.beat_grid = beat_grid
        self.output_path = output_path
        self.template_xsq = template_xsq
        self.timeline_tracks = timeline_tracks or []

        # Create shared infrastructure
        self.curve_generator = CurveGenerator()
        self.curve_registry = CurveRegistry()

        # Create rig profile from fixture group
        self.rig_profile = rig_profile_from_fixture_group(fixture_group)

        # Load builtin templates
        load_builtin_templates()

        # Create handler registries
        registries = create_default_registries()
        self.geometry_registry = registries["geometry"]
        self.movement_registry = registries["movement"]
        self.dimmer_registry = registries["dimmer"]

        # Create transition components
        self.transition_detector = TransitionDetector()
        self.transition_planner = TransitionPlanner(
            config=job_config.transitions, beat_grid=beat_grid
        )
        blender = ChannelBlender(self.curve_generator)
        self.transition_compiler = TransitionSegmentCompiler(blender)

        logger.debug(
            f"Initialized RenderingPipeline with {len(self.rig_profile.fixtures)} fixtures "
            f"and {len(self.choreography_plan.sections)} sections "
            f"(transitions enabled: {job_config.transitions.enabled})"
        )

    def render(self) -> list[FixtureSegment]:
        """Render the choreography plan to fixture segments.

        Processes each section in the choreography plan:
        1. Detect and plan transitions (if enabled)
        2. For each sequence in section, build template ID from components
        3. Load template and apply energy-based preset
        4. Build compile context aligned to beat grid
        5. Compile template to IR segments
        6. Generate transition segments (if enabled)
        7. Merge and aggregate all segments

        Returns:
            List of all compiled fixture segments across all sections.

        Raises:
            ValueError: If template not found or compilation fails.
        """
        logger.debug("Starting plan rendering...")

        # Step 1: Detect and plan transitions (if enabled)
        transition_registry = TransitionRegistry()
        if self.job_config.transitions.enabled:
            transition_registry = self._detect_and_plan_transitions()
            logger.debug(f"Detected and planned {len(transition_registry.transitions)} transitions")

        # Step 2: Compile sections
        section_segments: dict[str, list[FixtureSegment]] = {}
        time_markers: list[TimeMarker] = []

        for section in self.iterate_plan_sections(self.choreography_plan):
            if not section.template_id:
                raise ValueError(f"Section '{section.section_name}' has no template_id")

            logger.debug(
                f"Rendering section '{section.section_name}' "
                f"(bars {section.start_bar}-{section.end_bar}, "
                f"template: {section.template_id}, preset: {section.preset_id})"
            )

            # Load template
            try:
                template_doc = get_template(section.template_id)
                template = template_doc.template
                logger.debug(f"Loaded template: {template.name} (v{template.version})")
            except Exception as e:
                logger.error(f"Failed to load template '{section.template_id}': {e}")
                raise ValueError(f"Template not found: {section.template_id}") from e

            # Apply preset if available
            preset = None
            if section.preset_id:
                try:
                    preset = next(
                        p for p in template_doc.presets if p.preset_id == section.preset_id
                    )
                    logger.debug(f"Applying preset: {preset.name}")
                except StopIteration:
                    # Preset not found - try to infer intensity from preset_id
                    from twinklr.core.sequencer.models.template import StepPatch, TemplatePreset

                    preset_id_upper = section.preset_id.upper()
                    if preset_id_upper in ENERGY_TO_INTENSITY:
                        # Auto-create preset with inferred intensity
                        intensity = ENERGY_TO_INTENSITY[preset_id_upper]
                        step_patches = {
                            step.step_id: StepPatch(
                                movement={"intensity": intensity.value},
                                dimmer={"intensity": intensity.value},
                            )
                            for step in template.steps
                        }
                        preset = TemplatePreset(
                            preset_id=section.preset_id,
                            name=section.preset_id.title(),
                            defaults={},
                            step_patches=step_patches,
                        )
                        logger.debug(
                            f"Auto-generated preset '{section.preset_id}' "
                            f"with intensity {intensity.value} for template '{section.template_id}'"
                        )
                    else:
                        logger.warning(
                            f"Preset '{section.preset_id}' not found for template "
                            f"'{section.template_id}' and couldn't infer intensity, using base template"
                        )

            # Build fixture contexts
            fixture_contexts = self._build_fixture_contexts()

            # Build compile context aligned to beat grid
            context = TemplateCompileContext(
                section_id=section.section_name,
                template_id=template.template_id,
                preset_id=preset.preset_id if preset else None,
                fixtures=fixture_contexts,
                beat_grid=self.beat_grid,
                start_bar=section.start_bar,
                duration_bars=section.end_bar - section.start_bar + 1,
                curve_registry=self.curve_registry,
                geometry_registry=self.geometry_registry,
                movement_registry=self.movement_registry,
                dimmer_registry=self.dimmer_registry,
            )

            time_markers.append(
                TimeMarker(
                    name=section.section_name, time_ms=context.start_ms, end_time_ms=context.end_ms
                )
            )

            logger.debug(
                f"Compile context: start={context.start_ms}ms, "
                f"duration={context.duration_ms}ms, "
                f"bpm={context.bpm}"
            )

            # Compile template
            try:
                result = compile_template(template, context, preset)
                logger.debug(
                    f"Compiled {len(result.segments)} segments "
                    f"({result.num_complete_cycles} complete cycles)"
                )
                section_segments[section.section_name] = result.segments
            except Exception as e:
                logger.error(f"Compilation failed for section '{section.section_name}': {e}")
                raise

        # Step 3: Aggregate section segments
        all_segments: list[FixtureSegment] = []
        for segments in section_segments.values():
            all_segments.extend(segments)

        logger.debug(f"Compiled {len(section_segments)} sections into {len(all_segments)} segments")

        # Step 4: Generate transition segments (if enabled)
        if self.job_config.transitions.enabled and len(transition_registry.transitions) > 0:
            transition_segments = self._generate_transition_segments(
                transition_registry, section_segments
            )
            logger.debug(f"Generated {len(transition_segments)} transition segments")
            all_segments.extend(transition_segments)

        logger.debug(f"Render complete: {len(all_segments)} total segments")

        # Step 5: Export to XSQ
        if self.output_path:
            self._export_to_xsq(all_segments, time_markers)

        return all_segments

    def iterate_plan_sections(self, plan: ChoreographyPlan) -> Iterator[PlanSection]:
        """Iterate over the plan sections and yield each section.

        Args:
            plan: The choreography plan to iterate over.

        Returns:
            An iterator over the plan sections.
        """
        for section in plan.sections:
            if section.segments:
                for seg in section.segments:
                    yield PlanSection(
                        section_name=f"{section.section_name}|{seg.segment_id}",
                        start_bar=seg.start_bar,
                        end_bar=seg.end_bar,
                        section_role=section.section_role,
                        energy_level=section.energy_level,
                        template_id=seg.template_id,
                        preset_id=seg.preset_id,
                        modifiers=seg.modifiers,
                        reasoning=seg.reasoning or section.reasoning,
                        # IMPORTANT: do not carry segments forward once flattened
                        segments=None,
                        # Inherit parent section's transition hints (if any)
                        transition_in=section.transition_in,
                        transition_out=section.transition_out,
                    )
            else:
                yield section

    def _detect_and_plan_transitions(self) -> TransitionRegistry:
        """Detect boundaries and plan transitions.

        Returns:
            TransitionRegistry containing all planned transitions.
        """
        logger.debug("Detecting transition boundaries...")

        # Detect section boundaries
        boundaries = self.transition_detector.detect_section_boundaries(
            self.choreography_plan, self.beat_grid
        )

        logger.debug(f"Detected {len(boundaries)} section boundaries")

        # Build section lookup for duration computation
        section_lookup: dict[str, PlanSection] = {
            s.section_name: s for s in self.choreography_plan.sections
        }
        ms_per_bar = self.beat_grid.ms_per_bar

        # Plan transitions for each boundary
        registry = TransitionRegistry()
        fixture_ids = [fx.fixture_id for fx in self.rig_profile.fixtures]

        for boundary in boundaries:
            # Get transition hint and section durations from the plan
            hint = None
            source_section = section_lookup.get(boundary.source_id)
            target_section = section_lookup.get(boundary.target_id)

            if target_section is not None:
                hint = target_section.transition_in

            source_duration_ms = (
                _compute_section_duration_ms(
                    source_section.start_bar, source_section.end_bar, ms_per_bar
                )
                if source_section is not None
                else 0
            )
            target_duration_ms = (
                _compute_section_duration_ms(
                    target_section.start_bar, target_section.end_bar, ms_per_bar
                )
                if target_section is not None
                else 0
            )

            # Plan transition
            transition_id = f"trans_{boundary.source_id}_to_{boundary.target_id}"
            transition_plan = self.transition_planner.plan_transition(
                boundary=boundary,
                hint=hint,
                fixtures=fixture_ids,
                transition_id=transition_id,
            )

            # Validate feasibility using actual section durations
            is_feasible, warnings = self.transition_planner.validate_transition_feasibility(
                transition_plan, source_duration_ms, target_duration_ms
            )

            if not is_feasible:
                logger.warning(
                    f"Transition {transition_id} may not be feasible: {', '.join(warnings)}"
                )

            registry.add_transition(transition_plan)

        logger.debug(f"Planned {len(registry.transitions)} transitions")
        return registry

    def _generate_transition_segments(
        self,
        transition_registry: TransitionRegistry,
        section_segments: dict[str, list[FixtureSegment]],
    ) -> list[FixtureSegment]:
        """Generate transition segments for all planned transitions.

        Args:
            transition_registry: Registry of planned transitions.
            section_segments: Compiled segments organized by section name.

        Returns:
            List of transition FixtureSegments.
        """
        logger.debug("Generating transition segments...")
        all_transition_segments: list[FixtureSegment] = []

        for transition_plan in transition_registry.transitions:
            # Get source and target segments near the boundary
            source_segs = self._get_segments_at_boundary(
                section_segments,
                transition_plan.boundary.source_id,
                transition_plan.boundary.time_ms,
                is_source=True,
            )

            target_segs = self._get_segments_at_boundary(
                section_segments,
                transition_plan.boundary.target_id,
                transition_plan.boundary.time_ms,
                is_source=False,
            )

            logger.debug(
                f"Compiling transition {transition_plan.transition_id}: "
                f"{len(source_segs)} source segs, {len(target_segs)} target segs"
            )

            # Compile transition
            try:
                transition_segs = self.transition_compiler.compile_transition(
                    transition_plan, source_segs, target_segs
                )
                all_transition_segments.extend(transition_segs)
            except Exception as e:
                logger.error(f"Failed to compile transition {transition_plan.transition_id}: {e}")
                # Continue with other transitions

        return all_transition_segments

    def _get_segments_at_boundary(
        self,
        section_segments: dict[str, list[FixtureSegment]],
        section_name: str,
        boundary_time_ms: int,
        is_source: bool,
    ) -> list[FixtureSegment]:
        """Get segments at a boundary time.

        Args:
            section_segments: Segments organized by section name.
            section_name: Name of the section.
            boundary_time_ms: Boundary time in milliseconds.
            is_source: True if getting source segments, False for target.

        Returns:
            List of segments at or near the boundary time.
        """
        # Get segments for this section
        segments = section_segments.get(section_name, [])

        if not segments:
            return []

        # For source: get segments that end near or at the boundary
        # For target: get segments that start near or at the boundary
        boundary_segments = []

        for segment in segments:
            if is_source:
                # Source: segment should end at or near boundary
                # Allow some tolerance (e.g., within 100ms)
                if abs(segment.t1_ms - boundary_time_ms) <= 100:
                    boundary_segments.append(segment)
            # Target: segment should start at or near boundary
            elif abs(segment.t0_ms - boundary_time_ms) <= 100:
                boundary_segments.append(segment)

        # If no exact matches, get the closest segments
        if not boundary_segments and segments:
            if is_source:
                # Get segments ending closest to boundary
                boundary_segments = [max(segments, key=lambda s: s.t1_ms)]
            else:
                # Get segments starting closest to boundary
                boundary_segments = [min(segments, key=lambda s: s.t0_ms)]

        return boundary_segments

    def _build_fixture_contexts(self) -> list[FixtureContext]:
        """Build fixture contexts from rig profile.

        Delegates to :func:`build_fixture_contexts` in ``fixture_builder``.

        Returns:
            List of FixtureContext objects for all fixtures in the rig.
        """
        return build_fixture_contexts(self.rig_profile, self.fixture_group)

    def _export_to_xsq(
        self, segments: list[FixtureSegment], time_markers: list[TimeMarker]
    ) -> None:
        """Export segments to XSQ file.

        Delegates to :func:`export_to_xsq` in ``xsq_export``.

        Args:
            segments: List of fixture segments to export.
            time_markers: List of time markers to export.
        """
        if not self.output_path:
            logger.warning("No output_path specified, skipping XSQ export")
            return

        export_to_xsq(
            segments,
            time_markers,
            fixture_group=self.fixture_group,
            output_path=self.output_path,
            template_xsq=self.template_xsq,
            timeline_tracks=self.timeline_tracks,
        )
