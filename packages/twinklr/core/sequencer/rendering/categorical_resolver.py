"""Categorical Resolver for rendering pipeline.

Resolves categorical planning values (IntensityLevel, EffectDuration, PlanningTimeRef)
to numeric rendering values.

This module bridges the gap between LLM planning (categorical) and template compilation (numeric).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from twinklr.core.sequencer.vocabulary import (
    DURATION_BEATS,
    INTENSITY_MAP,
    EffectDuration,
    IntensityLevel,
    LaneKind,
    PlanningTimeRef,
    TimingHint,
)


@dataclass(frozen=True)
class ResolvedPlacement:
    """Resolved placement with numeric values for rendering.

    This is the output of the CategoricalResolver, ready for template compilation.
    """

    placement_id: str
    template_id: str
    group_id: str
    start_ms: int
    end_ms: int
    intensity: float
    param_overrides: dict[str, Any]


class CategoricalResolver:
    """Resolves categorical planning values to numeric rendering values.

    The resolver takes categorical values from the planning phase and converts them
    to precise numeric values suitable for template compilation:

    - IntensityLevel -> float (lane-aware mapping)
    - EffectDuration -> end_ms (calculated from start + beat grid)
    - PlanningTimeRef -> ms (using beat grid)
    """

    def __init__(
        self,
        bar_map: dict[int, tuple[int, int]],  # bar -> (start_ms, duration_ms)
        beats_per_bar: int = 4,
        intensity_map: dict[IntensityLevel, dict[str, float]] | None = None,
    ) -> None:
        """Initialize the resolver.

        Args:
            bar_map: Mapping from bar number to (start_ms, duration_ms)
            beats_per_bar: Beats per bar (typically 4)
            intensity_map: Optional custom intensity mapping (defaults to INTENSITY_MAP)
        """
        self.bar_map = bar_map
        self.beats_per_bar = beats_per_bar
        self.intensity_map = intensity_map or INTENSITY_MAP

    def resolve_time_ref(self, ref: PlanningTimeRef) -> int:
        """Resolve a PlanningTimeRef to milliseconds.

        Args:
            ref: Planning time reference (bar + beat + optional hint)

        Returns:
            Absolute milliseconds

        Raises:
            ValueError: If bar not found in bar_map
        """
        bar_info = self.bar_map.get(ref.bar)
        if bar_info is None:
            raise ValueError(f"Bar {ref.bar} not found in bar_map")

        bar_start_ms, bar_duration_ms = bar_info
        beat_duration_ms = bar_duration_ms / self.beats_per_bar

        # Beat offset within bar (beat is 1-indexed)
        beat_offset_ms = (ref.beat - 1) * beat_duration_ms

        # Apply timing hint
        hint_offset_ms = 0.0
        if ref.timing_hint == TimingHint.AND:
            hint_offset_ms = beat_duration_ms / 2
        elif ref.timing_hint == TimingHint.ANTICIPATE:
            hint_offset_ms = -beat_duration_ms / 8

        return int(bar_start_ms + beat_offset_ms + hint_offset_ms)

    def resolve_duration(
        self,
        start_ref: PlanningTimeRef,
        duration: EffectDuration,
        section_end_bar: int,
        section_end_beat: int,
    ) -> int:
        """Resolve a categorical duration to end milliseconds.

        Args:
            start_ref: Starting position
            duration: Categorical duration
            section_end_bar: Section end bar (for SECTION duration)
            section_end_beat: Section end beat

        Returns:
            End time in milliseconds
        """
        if duration == EffectDuration.SECTION:
            end_ref = PlanningTimeRef(bar=section_end_bar, beat=section_end_beat)
            return self.resolve_time_ref(end_ref)

        min_beats, _ = DURATION_BEATS[duration]
        if min_beats is None:
            end_ref = PlanningTimeRef(bar=section_end_bar, beat=section_end_beat)
            return self.resolve_time_ref(end_ref)

        # Calculate end bar/beat
        total_beats = start_ref.beat - 1 + min_beats
        end_bar = start_ref.bar + total_beats // self.beats_per_bar
        end_beat = (total_beats % self.beats_per_bar) + 1

        # Clamp to section bounds
        if end_bar > section_end_bar or (
            end_bar == section_end_bar and end_beat > section_end_beat
        ):
            end_bar = section_end_bar
            end_beat = section_end_beat

        end_ref = PlanningTimeRef(bar=end_bar, beat=end_beat)
        return self.resolve_time_ref(end_ref)

    def resolve_intensity(self, level: IntensityLevel, lane: LaneKind) -> float:
        """Resolve a categorical intensity level to numeric value.

        The resolution is lane-aware:
        - At every intensity level, BASE < RHYTHM < ACCENT
        - This eliminates layering issues automatically

        Args:
            level: Categorical intensity level
            lane: Lane for this placement

        Returns:
            Numeric intensity value
        """
        lane_key = lane.value if isinstance(lane, LaneKind) else str(lane)
        return self.intensity_map[level][lane_key]

    def resolve_placement(
        self,
        placement_id: str,
        template_id: str,
        group_id: str,
        start: PlanningTimeRef,
        duration: EffectDuration,
        intensity: IntensityLevel,
        lane: LaneKind,
        section_end_bar: int,
        section_end_beat: int,
        param_overrides: dict[str, Any] | None = None,
    ) -> ResolvedPlacement:
        """Resolve a complete placement to numeric values.

        Args:
            placement_id: Unique placement identifier
            template_id: Template to use
            group_id: Target group
            start: Start time (bar + beat)
            duration: Categorical duration
            intensity: Categorical intensity level
            lane: Lane for intensity mapping
            section_end_bar: Section end bar
            section_end_beat: Section end beat
            param_overrides: Optional template parameter overrides

        Returns:
            ResolvedPlacement with all numeric values
        """
        return ResolvedPlacement(
            placement_id=placement_id,
            template_id=template_id,
            group_id=group_id,
            start_ms=self.resolve_time_ref(start),
            end_ms=self.resolve_duration(start, duration, section_end_bar, section_end_beat),
            intensity=self.resolve_intensity(intensity, lane),
            param_overrides=param_overrides or {},
        )


__all__ = [
    "CategoricalResolver",
    "ResolvedPlacement",
]
