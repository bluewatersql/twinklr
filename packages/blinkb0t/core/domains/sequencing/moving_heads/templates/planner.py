"""
Template time planning and budget allocation.

This module provides the TemplateTimePlanner class which handles Phase 1
(Spatial Planning) of the transitions and gap filling system:

1. Calculate transition budget (total time needed for all transitions)
2. Scale effect durations to fit available time
3. Create timeline with explicit gaps for transitions
4. Collapse adjacent gaps (exit + entry transitions)

The planner creates a Timeline (list of TimelineEffect | TimelineGap) that
represents the complete time allocation for a template section, with gaps
allocated but not yet rendered.

Example:
    >>> planner = TemplateTimePlanner(song_features)
    >>> timeline = planner.plan_template(
    ...     template=template,
    ...     section_start_ms=1000.0,
    ...     section_duration_ms=8000.0,
    ...     fixture_id="MH1"
    ... )
    >>> # Timeline contains effects and gaps, ready for Phase 2 rendering
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from blinkb0t.core.domains.sequencing.infrastructure.xsq.effect_placement import EffectPlacement
from blinkb0t.core.domains.sequencing.models.transitions import (
    GapType,
    Timeline,
    TimelineEffect,
    TimelineGap,
)

if TYPE_CHECKING:
    from blinkb0t.core.domains.sequencing.models.templates import Template

logger = logging.getLogger(__name__)


class TemplateTimePlanner:
    """
    Phase 1 component: Time budgeting for templates.

    Responsibilities:
    - Calculate total transition time needed
    - Scale effect durations to fit available time
    - Create timeline with explicit gaps for transitions
    - Collapse adjacent gaps (exit + entry)

    The planner allocates time but does not render effects. Actual DMX
    effect generation is delegated to existing processors.

    Attributes:
        tempo_bpm: Song tempo in beats per minute
        ms_per_bar: Milliseconds per bar (calculated from tempo)

    Methods:
        plan_template: Create timeline with gaps and effects

    Example:
        >>> song_features = {"tempo_bpm": 120.0}
        >>> planner = TemplateTimePlanner(song_features)
        >>> timeline = planner.plan_template(template, 1000.0, 8000.0, "MH1")
        >>> # Timeline: [Gap?, Effect, Gap?, Effect, Gap?]
    """

    def __init__(self, song_features: dict):
        """
        Initialize time planner with song tempo.

        Args:
            song_features: Dictionary containing tempo_bpm
        """
        self.tempo_bpm = song_features["tempo_bpm"]
        # Calculate milliseconds per bar (4/4 time signature)
        # ms_per_bar = (60 / BPM) * 4 beats * 1000 ms/s
        self.ms_per_bar = (60 / self.tempo_bpm) * 4 * 1000

    def plan_template(
        self,
        template: Template,
        section_start_ms: float,
        section_duration_ms: float,
        fixture_id: str,
    ) -> Timeline:
        """
        Create timeline with gaps and effects.

        Algorithm:
        1. Calculate total transition time (sum of all entry/exit durations)
        2. Calculate available time for effects (section - transitions)
        3. Scale effect durations proportionally
        4. Build timeline: [Gap?, Effect, Gap?, Effect, Gap?]
        5. Collapse adjacent gaps

        Args:
            template: Template to plan
            section_start_ms: Section start time in milliseconds
            section_duration_ms: Total time available for section
            fixture_id: Fixture ID for this timeline

        Returns:
            Timeline with TimelineEffect and TimelineGap objects

        Example:
            >>> timeline = planner.plan_template(
            ...     template,
            ...     section_start_ms=1000.0,
            ...     section_duration_ms=8000.0,
            ...     fixture_id="MH1"
            ... )
            >>> # Returns: [Gap(entry), Effect, Gap(exit+entry), Effect, Gap(exit)]
        """
        timeline: Timeline = []

        # Step 1: Calculate transition budget
        transition_budget_ms = 0.0
        for step in template.steps:
            if step.entry_transition and step.entry_transition.duration_bars > 0:
                transition_budget_ms += step.entry_transition.duration_bars * self.ms_per_bar
            if step.exit_transition and step.exit_transition.duration_bars > 0:
                transition_budget_ms += step.exit_transition.duration_bars * self.ms_per_bar

        # Step 2: Calculate available time for effects
        total_effect_bars = sum(step.timing.base_timing.duration_bars for step in template.steps)
        available_effect_time_ms = section_duration_ms - transition_budget_ms

        # Handle budget overruns
        if available_effect_time_ms < 0 or transition_budget_ms > section_duration_ms * 0.8:
            logger.warning(
                f"Transition budget ({transition_budget_ms:.0f}ms) exceeds or nearly "
                f"exceeds section duration ({section_duration_ms:.0f}ms). Scaling down."
            )
            # Reserve 20% for effects minimum
            scale_factor = (section_duration_ms * 0.8) / transition_budget_ms
            transition_budget_ms = section_duration_ms * 0.8
            available_effect_time_ms = section_duration_ms * 0.2
        else:
            scale_factor = 1.0

        # Step 3: Build timeline
        current_ms = section_start_ms

        for step_idx, step in enumerate(template.steps):
            # Entry transition gap
            if step.entry_transition and step.entry_transition.duration_bars > 0:
                gap_duration = step.entry_transition.duration_bars * self.ms_per_bar * scale_factor

                # Extract anchor from previous effect (if any)
                from_position = None
                if timeline and isinstance(timeline[-1], TimelineEffect):
                    prev = timeline[-1]
                    from_position = (prev.pan_end, prev.tilt_end)

                timeline.append(
                    TimelineGap(
                        start_ms=current_ms,
                        end_ms=current_ms + gap_duration,
                        gap_type=GapType.MID_SEQUENCE,
                        transition_in_config=step.entry_transition,
                        from_position=from_position,
                        fixture_id=fixture_id,
                    )
                )
                current_ms += gap_duration

            # Main effect
            effect_duration_ms = (
                step.timing.base_timing.duration_bars / total_effect_bars
            ) * available_effect_time_ms

            # Create placeholder effect (will be replaced with actual DMX rendering)
            placeholder_effect = EffectPlacement(
                element_name=f"Dmx {fixture_id}",
                effect_name="DMX",
                start_ms=int(current_ms),
                end_ms=int(current_ms + effect_duration_ms),
                effect_label=f"{template.template_id}_{step.step_id}",
            )

            # Use placeholder anchors (will be calculated during actual rendering)
            pan_start = 0.0
            tilt_start = 45.0
            pan_end = 0.0
            tilt_end = 45.0

            timeline.append(
                TimelineEffect(
                    start_ms=current_ms,
                    end_ms=current_ms + effect_duration_ms,
                    fixture_id=fixture_id,
                    effect=placeholder_effect,
                    pan_start=pan_start,
                    pan_end=pan_end,
                    tilt_start=tilt_start,
                    tilt_end=tilt_end,
                    step_index=step_idx,
                    template_id=template.template_id,
                    template_metadata=template.metadata.model_dump() if template.metadata else {},
                    pattern_step=step,
                )
            )
            current_ms += effect_duration_ms

            # Exit transition gap
            if step.exit_transition and step.exit_transition.duration_bars > 0:
                gap_duration = step.exit_transition.duration_bars * self.ms_per_bar * scale_factor

                timeline.append(
                    TimelineGap(
                        start_ms=current_ms,
                        end_ms=current_ms + gap_duration,
                        gap_type=GapType.MID_SEQUENCE,
                        transition_out_config=step.exit_transition,
                        from_position=(pan_end, tilt_end),
                        fixture_id=fixture_id,
                    )
                )
                current_ms += gap_duration

        # Step 4: Collapse adjacent gaps
        return self._collapse_adjacent_gaps(timeline)

    def _collapse_adjacent_gaps(self, timeline: Timeline) -> Timeline:
        """
        Merge adjacent transition gaps.

        Pattern to detect:
            [..., Effect, Gap(exit), Gap(entry), Effect, ...]

        Becomes:
            [..., Effect, Gap(exit+entry), Effect, ...]

        Args:
            timeline: Timeline with potential adjacent gaps

        Returns:
            Timeline with adjacent gaps merged
        """
        collapsed: list[TimelineEffect | TimelineGap] = []
        i = 0

        while i < len(timeline):
            item = timeline[i]

            # Check if current and next items are both gaps
            if isinstance(item, TimelineGap) and i + 1 < len(timeline):
                next_item = timeline[i + 1]

                if isinstance(next_item, TimelineGap):
                    # Adjacent gaps detected
                    if abs(item.end_ms - next_item.start_ms) < 1.0:  # Float tolerance
                        # Merge into single gap
                        collapsed.append(
                            TimelineGap(
                                start_ms=item.start_ms,
                                end_ms=next_item.end_ms,
                                gap_type=GapType.MID_SEQUENCE,
                                transition_out_config=item.transition_out_config,
                                transition_in_config=next_item.transition_in_config,
                                from_position=item.from_position,
                                to_position=next_item.to_position,
                                fixture_id=item.fixture_id,
                            )
                        )
                        i += 2  # Skip both gaps
                        continue

            collapsed.append(item)
            i += 1

        return collapsed

    def _process_step(
        self,
        step,
        start_ms: float,
        duration_ms: float,
        fixture_id: str,
    ) -> EffectPlacement:
        """
        Process a template step into an effect placement.

        This is a placeholder that will be overridden or mocked in tests.
        In actual integration, this will delegate to PatternStepProcessor.

        Args:
            step: Pattern step to process
            start_ms: Start time
            duration_ms: Duration
            fixture_id: Fixture ID

        Returns:
            EffectPlacement for the step
        """
        raise NotImplementedError("_process_step must be overridden or mocked")

    def _calculate_end_position(
        self,
        effect_placement: EffectPlacement,
        duration_ms: float,
    ) -> tuple[float, float]:
        """
        Calculate end position for an effect.

        This is a placeholder that will be overridden or mocked in tests.

        Args:
            effect_placement: Effect to calculate end position for
            duration_ms: Effect duration

        Returns:
            (pan_end, tilt_end) in degrees
        """
        raise NotImplementedError("_calculate_end_position must be overridden or mocked")
