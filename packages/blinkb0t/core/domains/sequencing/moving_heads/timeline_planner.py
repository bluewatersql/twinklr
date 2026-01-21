"""Timeline planner for converting AgentImplementation to ExplodedTimeline.

Converts high-level choreography plans into a flat timeline of template steps
and gaps, ready for rendering.
"""

from __future__ import annotations

import logging

from blinkb0t.core.agents.moving_heads.models_agent_plan import (
    AgentImplementation,
    ImplementationSection,
    TransitionSpec,
)
from blinkb0t.core.domains.sequencing.infrastructure.timing.beat_grid import BeatGrid
from blinkb0t.core.domains.sequencing.models.templates import PatternStep, Template
from blinkb0t.core.domains.sequencing.models.timeline import (
    ExplodedTimeline,
    GapSegment,
    TemplateStepSegment,
)

logger = logging.getLogger(__name__)


class TemplateTimelinePlanner:
    """Plans complete timeline from agent implementation.

    Converts AgentImplementation (high-level choreography) into an
    ExplodedTimeline (flat list of template steps and gaps).

    Key Responsibilities:
    - Convert agent's bar-level timing to milliseconds (single source of truth)
    - Expand sections to individual template steps
    - Detect and fill gaps in timeline
    - Ensure no overlaps or timeline holes

    Usage:
        planner = TemplateTimelinePlanner()
        timeline = planner.plan(
            choreography_plan=implementation,
            beat_grid=beat_grid,
            template_library=templates,
            total_duration_ms=song_duration
        )
    """

    def plan(
        self,
        choreography_plan: AgentImplementation,
        beat_grid: BeatGrid,
        template_library: dict[str, Template],
        total_duration_ms: float,
    ) -> ExplodedTimeline:
        """Create exploded timeline from agent implementation.

        Args:
            choreography_plan: Agent-generated implementation with sections
            beat_grid: Musical timing grid for bar/beat alignment
            template_library: Available template definitions
            total_duration_ms: Total song duration in milliseconds

        Returns:
            ExplodedTimeline with all segments (template steps + gaps) ordered

        Example:
            >>> timeline = planner.plan(impl, beat_grid, templates, 180000.0)
            >>> print(f"Timeline has {len(timeline.segments)} segments")
        """
        logger.info(
            f"Planning timeline from {len(choreography_plan.sections)} sections, "
            f"total duration {total_duration_ms}ms"
        )

        # Handle empty implementation
        if not choreography_plan.sections:
            logger.info("Empty implementation, returning empty timeline")
            return ExplodedTimeline(segments=[], total_duration_ms=total_duration_ms)

        # Sort sections by start bar (agent works in bars, we convert to ms)
        sorted_sections = sorted(choreography_plan.sections, key=lambda s: s.start_bar)

        # Expand sections to template step segments
        template_segments = []
        for section in sorted_sections:
            # Convert bars→ms (single source of truth for timing conversion)
            # start_bar: beginning of bar (e.g., bar 1 starts at 0ms)
            # end_bar: INCLUSIVE end bar (e.g., bars 1-8 means content through end of bar 8)
            section_start_ms = self._bar_to_ms(section.start_bar, beat_grid)
            # Duration = end_bar - start_bar + 1 (inclusive)
            # End time = start_time + duration * ms_per_bar
            duration_bars = section.end_bar - section.start_bar + 1
            section_end_ms = section_start_ms + (duration_bars * beat_grid.ms_per_bar)

            segments = self._expand_section(
                section, template_library, beat_grid, section_start_ms, section_end_ms
            )
            template_segments.extend(segments)

        # Sort all segments by start time
        template_segments.sort(key=lambda s: s.start_ms)

        # Detect and fill gaps
        all_segments = self._fill_gaps(template_segments, total_duration_ms)

        logger.info(
            f"Timeline planning complete: {len(all_segments)} segments "
            f"({len(template_segments)} template steps, {len(all_segments) - len(template_segments)} gaps)"
        )

        return ExplodedTimeline(segments=all_segments, total_duration_ms=total_duration_ms)

    def _bar_to_ms(self, bar: int, beat_grid: BeatGrid) -> float:
        """Convert bar number to milliseconds.

        Single source of truth for bar→ms conversion.
        Bars are 1-indexed and inclusive (bar 1 = 0-2000ms, bar 2 = 2000-4000ms).

        Args:
            bar: Bar number (1-indexed, inclusive for end_bar)
            beat_grid: Musical timing grid

        Returns:
            Time in milliseconds at the START of the bar
        """
        # Bar 1 starts at 0ms, bar 2 starts at ms_per_bar, bar 3 at 2*ms_per_bar, etc.
        # For end_bar: bar 4 ends at 4*ms_per_bar = 8000ms
        return (bar - 1) * beat_grid.ms_per_bar

    def _expand_section(
        self,
        section: ImplementationSection,
        template_library: dict[str, Template],
        beat_grid: BeatGrid,
        section_start_ms: float,
        section_end_ms: float,
    ) -> list[TemplateStepSegment]:
        """Expand a section into template step segments.

        Args:
            section: Implementation section to expand (with bar-level timing)
            template_library: Available templates
            beat_grid: Musical timing grid
            section_start_ms: Converted start time in milliseconds
            section_end_ms: Converted end time in milliseconds

        Returns:
            List of TemplateStepSegment objects for this section
        """
        # Get template
        template = template_library.get(section.template_id)
        if not template:
            logger.warning(
                f"Template '{section.template_id}' not found in library, skipping section '{section.name}'"
            )
            return []

        # For each target, expand all template steps
        segments = []

        for target in section.targets:
            target_segments = self._expand_template_steps_for_target(
                section, template, target, beat_grid, section_start_ms, section_end_ms
            )
            segments.extend(target_segments)

        logger.debug(
            f"Expanded section '{section.name}' (bars {section.start_bar}-{section.end_bar}, "
            f"{section_start_ms:.0f}-{section_end_ms:.0f}ms) to {len(segments)} segments "
            f"({len(template.steps)} steps × {len(section.targets)} targets)"
        )

        return segments

    def _expand_template_steps_for_target(
        self,
        section: ImplementationSection,
        template: Template,
        target: str,
        beat_grid: BeatGrid,
        section_start_ms: float,
        section_end_ms: float,
    ) -> list[TemplateStepSegment]:
        """Expand all template steps for a specific target, repeating until section is filled.

        Args:
            section: Implementation section (with bar-level timing)
            template: Template definition
            target: Target fixture group or ID
            beat_grid: Musical timing grid for converting bars to ms
            section_start_ms: Section start time in milliseconds
            section_end_ms: Section end time in milliseconds

        Returns:
            List of TemplateStepSegment objects (repeating template steps to fill section)
        """
        segments = []
        current_start_ms = section_start_ms
        iteration = 0

        # Repeat template steps until section is filled
        while current_start_ms < section_end_ms:
            for step_idx, step in enumerate(template.steps):
                # Calculate step duration in milliseconds
                step_duration_bars = step.timing.base_timing.duration_bars
                step_duration_ms = step_duration_bars * beat_grid.ms_per_bar

                # Calculate step timing
                step_start_ms = current_start_ms
                step_end_ms = step_start_ms + step_duration_ms

                # Clamp to section boundaries
                step_end_ms = min(step_end_ms, section_end_ms)

                # Skip if step would be zero duration
                if step_end_ms <= step_start_ms:
                    logger.debug(
                        f"Skipping step {step_idx} iteration {iteration} in section '{section.name}' - "
                        f"would exceed section end"
                    )
                    break

                # Create segment for this step
                segment = self._create_segment_for_step(
                    section, template, step, step_idx, target, step_start_ms, step_end_ms, beat_grid
                )
                segments.append(segment)

                # Move to next step start time
                current_start_ms = step_end_ms

                # Break inner loop if we've reached section end
                if current_start_ms >= section_end_ms:
                    break

            iteration += 1

            # Safety check: prevent infinite loops
            if iteration > 1000:
                logger.error(
                    f"Template iteration limit exceeded for section '{section.name}' - "
                    f"possible infinite loop"
                )
                break

        logger.debug(
            f"Expanded template '{template.template_id}' to {len(segments)} segments "
            f"over {iteration} iterations for section '{section.name}'"
        )

        return segments

    def _create_segment_for_step(
        self,
        section: ImplementationSection,
        template: Template,
        step: PatternStep,
        step_idx: int,
        target: str,
        start_ms: float,
        end_ms: float,
        beat_grid: BeatGrid,
    ) -> TemplateStepSegment:
        """Create a template step segment for a specific step and target.

        Args:
            section: Implementation section
            template: Template definition
            step: Pattern step definition
            step_idx: Step index in template
            target: Target fixture group or ID
            start_ms: Step start time in milliseconds
            end_ms: Step end time in milliseconds
            beat_grid: Musical timing grid for transition duration conversion

        Returns:
            TemplateStepSegment for this step and target
        """
        # Merge section params with step params (section params override)
        merged_movement_params = {**step.movement_params, **section.params}
        merged_dimmer_params = {**step.dimmer_params}

        # Convert step transitions from TransitionConfig to TransitionSpec
        # (Agent no longer specifies transitions, so we use template defaults)
        entry_transition = TransitionSpec(
            mode=step.entry_transition.mode.value,
            duration_ms=step.entry_transition.duration_bars * beat_grid.ms_per_bar,
        )

        exit_transition = TransitionSpec(
            mode=step.exit_transition.mode.value,
            duration_ms=step.exit_transition.duration_bars * beat_grid.ms_per_bar,
        )

        # Create segment
        segment = TemplateStepSegment(
            step_id=f"{section.name}_{target}_step_{step_idx}",
            section_id=section.name,
            start_ms=start_ms,
            end_ms=end_ms,
            template_id=section.template_id,
            movement_id=step.movement_id,
            movement_params=merged_movement_params,
            geometry_id=step.geometry_id,
            geometry_params=step.geometry_params if step.geometry_id else None,
            dimmer_id=step.dimmer_id,
            dimmer_params=merged_dimmer_params,
            base_pose=section.base_pose,
            target=target,
            entry_transition=entry_transition,
            exit_transition=exit_transition,
        )

        return segment

    def _fill_gaps(
        self,
        template_segments: list[TemplateStepSegment],
        total_duration_ms: float,
    ) -> list[TemplateStepSegment | GapSegment]:
        """Detect and fill gaps in the timeline.

        Args:
            template_segments: Template step segments (sorted by start time)
            total_duration_ms: Total song duration

        Returns:
            List of all segments (template steps + gaps) in chronological order
        """
        if not template_segments:
            # Entire timeline is a gap
            if total_duration_ms > 0:
                logger.info("No template segments, creating end-of-song gap for entire duration")
                return [
                    GapSegment(
                        start_ms=0.0,
                        end_ms=total_duration_ms,
                        gap_type="end_of_song",
                    )
                ]
            return []

        all_segments: list[TemplateStepSegment | GapSegment] = []
        current_time = 0.0

        for segment in template_segments:
            # Check for gap before this segment
            if segment.start_ms > current_time:
                gap_duration = segment.start_ms - current_time

                # Skip zero-duration gaps (timing precision artifacts)
                if gap_duration < 1.0:  # Less than 1ms
                    logger.debug(
                        f"Skipping zero-duration gap: {current_time}ms - {segment.start_ms}ms ({gap_duration}ms)"
                    )
                else:
                    logger.debug(
                        f"Detected gap: {current_time}ms - {segment.start_ms}ms ({gap_duration}ms)"
                    )

                    gap = GapSegment(
                        start_ms=current_time,
                        end_ms=segment.start_ms,
                        section_id=segment.section_id if current_time > 0 else None,
                        gap_type="inter_section" if current_time > 0 else "intro",
                    )
                    all_segments.append(gap)

            # Add the template segment
            all_segments.append(segment)
            current_time = segment.end_ms

        # Check for gap at end of song
        if current_time < total_duration_ms:
            gap_duration = total_duration_ms - current_time
            logger.debug(
                f"Detected end-of-song gap: {current_time}ms - {total_duration_ms}ms ({gap_duration}ms)"
            )

            gap = GapSegment(
                start_ms=current_time,
                end_ms=total_duration_ms,
                gap_type="end_of_song",
            )
            all_segments.append(gap)

        return all_segments
