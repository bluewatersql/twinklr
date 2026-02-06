"""TimingContext for GroupPlanner TimeRef resolution.

Provides bar/beat -> millisecond conversion and section bounds management.
Supports both legacy TimeRef and new PlanningTimeRef.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from twinklr.core.sequencer.templates.group.models import TimeRef, TimeRefKind
from twinklr.core.sequencer.vocabulary import (
    DURATION_BEATS,
    EffectDuration,
    PlanningTimeRef,
    TimingHint,
)


class BarInfo(BaseModel):
    """Information about a single bar."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    bar: int = Field(ge=1)
    start_ms: int = Field(ge=0)
    duration_ms: int = Field(ge=1)


class SectionBounds(BaseModel):
    """Bounds for a section, defined with TimeRefs."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    section_id: str
    start: TimeRef
    end: TimeRef


class TimingContext(BaseModel):
    """Timing context for resolving TimeRefs to milliseconds.

    Provides:
    - bar_map: mapping from bar number -> BarInfo
    - section_bounds: mapping from section_id -> SectionBounds
    - Resolution of TimeRef (BAR_BEAT or MS) to milliseconds
    """

    model_config = ConfigDict(extra="forbid")

    song_duration_ms: int = Field(ge=1)
    beats_per_bar: int = Field(default=4, ge=1)
    bar_map: dict[int, BarInfo] = Field(default_factory=dict)
    section_bounds: dict[str, SectionBounds] = Field(default_factory=dict)

    def resolve_to_ms(self, ref: TimeRef) -> int:
        """Resolve a TimeRef to milliseconds.

        Args:
            ref: TimeRef to resolve

        Returns:
            Absolute milliseconds from song start

        Raises:
            ValueError: If bar not found in bar_map
        """
        if ref.kind == TimeRefKind.MS:
            # MS kind: offset_ms is the absolute time
            return ref.offset_ms or 0

        # BAR_BEAT kind: resolve bar/beat/beat_frac + optional offset
        if ref.bar is None or ref.beat is None:
            raise ValueError("BAR_BEAT TimeRef must have bar and beat")

        bar_info = self.bar_map.get(ref.bar)
        if bar_info is None:
            raise ValueError(f"Bar {ref.bar} not found in bar_map")

        # Calculate beat duration within this bar
        beat_duration_ms = bar_info.duration_ms / self.beats_per_bar

        # Beat offset within bar (beat is 1-indexed)
        beat_offset_ms = (ref.beat - 1) * beat_duration_ms

        # Sub-beat fraction
        frac_offset_ms = ref.beat_frac * beat_duration_ms

        # Fine nudge from offset_ms
        nudge_ms = ref.offset_ms or 0

        return int(bar_info.start_ms + beat_offset_ms + frac_offset_ms + nudge_ms)

    def get_section_bounds(self, section_id: str) -> SectionBounds | None:
        """Get section bounds by section_id.

        Args:
            section_id: Section identifier

        Returns:
            SectionBounds or None if not found
        """
        return self.section_bounds.get(section_id)

    def resolve_section_bounds_ms(self, section_id: str) -> tuple[int, int]:
        """Resolve section bounds to (start_ms, end_ms).

        Args:
            section_id: Section identifier

        Returns:
            Tuple of (start_ms, end_ms)

        Raises:
            ValueError: If section not found
        """
        bounds = self.get_section_bounds(section_id)
        if bounds is None:
            raise ValueError(f"Section {section_id} not found in section_bounds")

        start_ms = self.resolve_to_ms(bounds.start)
        end_ms = self.resolve_to_ms(bounds.end)
        return (start_ms, end_ms)

    def beat_duration_ms(self, bar: int) -> float:
        """Get beat duration in milliseconds for a given bar.

        Args:
            bar: Bar number (1-indexed)

        Returns:
            Beat duration in milliseconds

        Raises:
            ValueError: If bar not found
        """
        bar_info = self.bar_map.get(bar)
        if bar_info is None:
            raise ValueError(f"Bar {bar} not found in bar_map")
        return bar_info.duration_ms / self.beats_per_bar

    def resolve_planning_time_ref(self, ref: PlanningTimeRef) -> int:
        """Resolve a PlanningTimeRef to milliseconds.

        Args:
            ref: PlanningTimeRef (bar + beat + optional timing_hint)

        Returns:
            Absolute milliseconds from song start

        Raises:
            ValueError: If bar not found in bar_map
        """
        bar_info = self.bar_map.get(ref.bar)
        if bar_info is None:
            raise ValueError(f"Bar {ref.bar} not found in bar_map")

        # Calculate beat duration within this bar
        beat_duration_ms = bar_info.duration_ms / self.beats_per_bar

        # Beat offset within bar (beat is 1-indexed)
        beat_offset_ms = (ref.beat - 1) * beat_duration_ms

        # Apply timing hint
        hint_offset_ms = 0.0
        if ref.timing_hint == TimingHint.AND:
            # Half-beat offset
            hint_offset_ms = beat_duration_ms / 2
        elif ref.timing_hint == TimingHint.ANTICIPATE:
            # Slight early (1/8 beat)
            hint_offset_ms = -beat_duration_ms / 8

        return int(bar_info.start_ms + beat_offset_ms + hint_offset_ms)

    def resolve_duration_to_end_ms(
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
            # Use section bounds
            end_ref = PlanningTimeRef(bar=section_end_bar, beat=section_end_beat)
            return self.resolve_planning_time_ref(end_ref)

        # Get minimum beats for duration
        min_beats, _ = DURATION_BEATS[duration]
        if min_beats is None:
            # Fallback to section end
            end_ref = PlanningTimeRef(bar=section_end_bar, beat=section_end_beat)
            return self.resolve_planning_time_ref(end_ref)

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
        return self.resolve_planning_time_ref(end_ref)
