"""Timing resolver: converts categorical planning values to milliseconds.

Translates PlanningTimeRef (bar/beat) and EffectDuration (categorical)
to concrete start_ms/end_ms values using the BeatGrid.
"""

from __future__ import annotations

import logging
import math

from twinklr.core.sequencer.timing.beat_grid import BeatGrid
from twinklr.core.sequencer.vocabulary import EffectDuration, PlanningTimeRef
from twinklr.core.sequencer.vocabulary.duration import DURATION_BEATS

logger = logging.getLogger(__name__)


class TimingResolver:
    """Resolves categorical timing to concrete milliseconds.

    Uses the BeatGrid to convert bar/beat references to exact ms,
    and EffectDuration categories to beat counts.

    Args:
        beat_grid: Musical timing grid for the sequence.
    """

    def __init__(self, beat_grid: BeatGrid) -> None:
        self._beat_grid = beat_grid

    def resolve_start_ms(
        self,
        time_ref: PlanningTimeRef,
        section_start_bar: int = 0,
    ) -> int:
        """Resolve a PlanningTimeRef to start time in milliseconds.

        PlanningTimeRef uses 1-indexed, section-relative bar/beat.
        ``section_start_bar`` anchors the reference to a song position
        so that *bar=1, beat=1* resolves to the section's first beat,
        not the song's first beat.

        Args:
            time_ref: Planning time reference (bar + beat, 1-indexed).
            section_start_bar: 0-indexed bar in the song where this
                section begins (from the section bar map).

        Returns:
            Start time in milliseconds, snapped to 20ms grid.
        """
        return self._snap_to_grid(self.resolve_start_ms_exact(time_ref, section_start_bar))

    def resolve_start_ms_exact(
        self,
        time_ref: PlanningTimeRef,
        section_start_bar: int = 0,
    ) -> float:
        """Resolve a planning reference against the BeatGrid without snapping.

        This is the unsnapped primitive beneath planner-authored
        :meth:`resolve_start_ms`; coordination expansion schedules in beat coordinates
        and calls :meth:`resolve_beat_position_ms` for fractional positions directly.
        """
        beat_position = self.resolve_beat_position(time_ref, section_start_bar)
        return self.resolve_beat_position_ms(beat_position)

    def resolve_beat_position(
        self,
        time_ref: PlanningTimeRef,
        section_start_bar: int = 0,
    ) -> float:
        """Convert a planning reference to a clamped absolute beat coordinate."""
        song_bar_0 = (time_ref.bar - 1) + section_start_bar
        beat_within_bar = time_ref.beat - 1
        absolute_beat = float(song_bar_0 * self._beat_grid.beats_per_bar + beat_within_bar)
        max_beat = max(len(self._beat_grid.beat_boundaries) - 1, 0)
        return min(max(absolute_beat, 0.0), float(max_beat))

    def resolve_beat_position_ms(self, beat_position: float) -> float:
        """Map an absolute fractional beat coordinate through local grid boundaries.

        Coordinates inside the grid interpolate between their adjacent detected beat
        boundaries. Coordinates outside it clamp to the first or last boundary, matching
        the existing planner-authored start-time endpoint policy.
        """
        boundaries = self._beat_grid.beat_boundaries
        if not boundaries:
            logger.warning("BeatGrid has no beat boundaries; falling back to average beat duration")
            return max(beat_position, 0.0) * self._beat_grid.ms_per_beat

        last_index = len(boundaries) - 1
        if beat_position <= 0.0:
            return boundaries[0]
        if beat_position >= last_index:
            return boundaries[last_index]

        lower_index = math.floor(beat_position)
        fraction = beat_position - lower_index
        lower_ms = boundaries[lower_index]
        upper_ms = boundaries[lower_index + 1]
        return lower_ms + fraction * (upper_ms - lower_ms)

    def resolve_end_ms(
        self,
        start_ms: int,
        duration: EffectDuration,
        section_end_ms: int | None = None,
        duration_bias: float = 0.5,
    ) -> int:
        """Resolve an EffectDuration to an end time in milliseconds.

        Duration categories with ranges (like PHRASE = 2-4 bars) are
        interpolated using ``duration_bias``:

        - ``0.0`` → minimum (tighter, shorter effects)
        - ``0.5`` → midpoint (default, balanced)
        - ``1.0`` → maximum (longest allowed for category)

        When ``section_end_ms`` is provided, the result is snapped DOWN
        to the 20ms grid to avoid bleeding past the section boundary.

        Args:
            start_ms: Effect start time in milliseconds.
            duration: Categorical duration.
            section_end_ms: Optional section end time for clamping.
                If provided and duration is SECTION, uses this as end.
            duration_bias: Interpolation between min and max of the
                duration range (0.0-1.0, default 0.5 = midpoint).

        Returns:
            End time in milliseconds, snapped to 20ms grid.
        """
        clamped = False

        if duration == EffectDuration.SECTION:
            if section_end_ms is not None:
                return self._snap_down_to_grid(section_end_ms)
            # Fallback: use sequence duration
            return self._snap_to_grid(self._beat_grid.duration_ms)

        beat_count = self._resolve_beat_count(duration, duration_bias)
        ms_per_beat = 60_000.0 / self._beat_grid.tempo_bpm
        end_ms = start_ms + int(beat_count * ms_per_beat)

        # Clamp to section boundary if provided
        if section_end_ms is not None and end_ms > section_end_ms:
            end_ms = section_end_ms
            clamped = True

        # Clamp to sequence duration
        seq_end = int(self._beat_grid.duration_ms)
        if end_ms > seq_end:
            end_ms = seq_end
            clamped = True

        # Snap down when clamped to avoid overshooting the boundary
        if clamped:
            return self._snap_down_to_grid(end_ms)
        return self._snap_to_grid(end_ms)

    def resolve_native_range(
        self,
        start_ms: float,
        end_ms: float,
        *,
        section_end_ms: int | None = None,
    ) -> tuple[int, int]:
        """Snap and clamp an already-resolved millisecond interval.

        Coordination expansion has already made the timing decision, so this path
        deliberately performs no categorical duration or bar/beat conversion.  It
        shares the existing 20 ms grid policy and floors a clamped end to avoid
        overshooting the section or sequence boundary.
        """
        sequence_end_ms = int(self._beat_grid.duration_ms)
        clamped_start = max(0.0, min(start_ms, float(sequence_end_ms)))
        end_limit_ms = sequence_end_ms
        if section_end_ms is not None:
            end_limit_ms = min(end_limit_ms, section_end_ms)
        clamped_end = max(0.0, min(end_ms, float(end_limit_ms)))

        resolved_start = self._snap_to_grid(clamped_start)
        if clamped_end < end_ms:
            resolved_end = self._snap_down_to_grid(clamped_end)
        else:
            resolved_end = self._snap_to_grid(clamped_end)
        return resolved_start, resolved_end

    @staticmethod
    def _resolve_beat_count(duration: EffectDuration, bias: float = 0.5) -> int:
        """Resolve an EffectDuration to a beat count using the vocabulary range.

        Interpolates between the min and max beats defined in
        ``DURATION_BEATS`` using the ``bias`` parameter.

        Args:
            duration: Categorical duration.
            bias: Interpolation (0.0 = min, 0.5 = mid, 1.0 = max).

        Returns:
            Beat count as integer.
        """
        bounds = DURATION_BEATS.get(duration)
        if bounds is None:
            return 4  # Sensible default

        min_b, max_b = bounds
        if min_b is None or max_b is None:
            return 4  # SECTION or unknown

        bias = max(0.0, min(1.0, bias))
        return min_b + int((max_b - min_b) * bias)

    def snap(self, ms: float) -> int:
        """Snap a time value to the nearest 20ms xLights timing grid.

        Public convenience for callers that need to snap values after
        adding offsets (e.g. section start offsets).

        Args:
            ms: Time in milliseconds.

        Returns:
            Nearest 20ms grid point as integer.
        """
        return self._snap_to_grid(ms)

    def _snap_to_grid(self, ms: float) -> int:
        """Snap a time value to the nearest 20ms xLights timing grid.

        Args:
            ms: Time in milliseconds.

        Returns:
            Nearest 20ms grid point as integer.
        """
        grid = 20  # xLights default timing grid
        return int(round(ms / grid) * grid)

    def _snap_down_to_grid(self, ms: float) -> int:
        """Snap a time value DOWN to the 20ms grid (floor).

        Use this instead of ``_snap_to_grid`` when the value has been
        clamped to a boundary (e.g. section end) so rounding up would
        overshoot that boundary.

        Args:
            ms: Time in milliseconds.

        Returns:
            Floor-snapped 20ms grid point as integer.
        """
        grid = 20
        return int(ms // grid) * grid


__all__ = [
    "TimingResolver",
]
