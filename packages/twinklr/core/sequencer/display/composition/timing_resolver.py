"""Timing resolver: converts categorical planning values to milliseconds.

Translates PlanningTimeRef (bar/beat) and EffectDuration (categorical)
to concrete start_ms/end_ms values using the BeatGrid.
"""

from __future__ import annotations

import logging

from twinklr.core.sequencer.timing.beat_grid import BeatGrid
from twinklr.core.sequencer.vocabulary import EffectDuration, PlanningTimeRef

logger = logging.getLogger(__name__)

# Duration → beat count mapping
# These are approximate; the resolver clamps to section boundaries.
_DURATION_BEATS: dict[EffectDuration, int] = {
    EffectDuration.HIT: 1,       # 1 beat
    EffectDuration.BURST: 4,     # 1 bar (4 beats)
    EffectDuration.PHRASE: 16,   # 4 bars (16 beats)
    EffectDuration.EXTENDED: 32,  # 8 bars (32 beats)
    EffectDuration.SECTION: -1,  # Special: full section
}


class TimingResolver:
    """Resolves categorical timing to concrete milliseconds.

    Uses the BeatGrid to convert bar/beat references to exact ms,
    and EffectDuration categories to beat counts.

    Args:
        beat_grid: Musical timing grid for the sequence.
    """

    def __init__(self, beat_grid: BeatGrid) -> None:
        self._beat_grid = beat_grid

    def resolve_start_ms(self, time_ref: PlanningTimeRef) -> int:
        """Resolve a PlanningTimeRef to start time in milliseconds.

        PlanningTimeRef uses 1-indexed bar/beat. BeatGrid uses 0-indexed.
        bar=1, beat=1 → first beat of first bar.

        Args:
            time_ref: Planning time reference (bar + beat).

        Returns:
            Start time in milliseconds, snapped to 20ms grid.
        """
        # Convert 1-indexed to 0-indexed
        bar_0 = time_ref.bar - 1
        beat_within_bar = time_ref.beat - 1

        # Calculate absolute beat index
        beats_per_bar = self._beat_grid.beats_per_bar
        absolute_beat = (bar_0 * beats_per_bar) + beat_within_bar

        # Clamp to available beats
        max_beat = len(self._beat_grid.beat_boundaries) - 1
        absolute_beat = min(absolute_beat, max_beat)
        absolute_beat = max(absolute_beat, 0)

        ms = self._beat_grid.get_beat_time_ms(absolute_beat)
        return self._snap_to_grid(ms)

    def resolve_end_ms(
        self,
        start_ms: int,
        duration: EffectDuration,
        section_end_ms: int | None = None,
    ) -> int:
        """Resolve an EffectDuration to an end time in milliseconds.

        When ``section_end_ms`` is provided, the result is snapped DOWN
        to the 20ms grid to avoid bleeding past the section boundary.

        Args:
            start_ms: Effect start time in milliseconds.
            duration: Categorical duration.
            section_end_ms: Optional section end time for clamping.
                If provided and duration is SECTION, uses this as end.

        Returns:
            End time in milliseconds, snapped to 20ms grid.
        """
        clamped = False

        if duration == EffectDuration.SECTION:
            if section_end_ms is not None:
                return self._snap_down_to_grid(section_end_ms)
            # Fallback: use sequence duration
            return self._snap_to_grid(self._beat_grid.duration_ms)

        beat_count = _DURATION_BEATS.get(duration, 4)
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
