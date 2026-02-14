"""Timing resolver: converts categorical planning values to milliseconds.

Translates PlanningTimeRef (bar/beat) and EffectDuration (categorical)
to concrete start_ms/end_ms values using the BeatGrid.
"""

from __future__ import annotations

import logging

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
        # Section-relative bar → song-absolute bar (0-indexed)
        song_bar_0 = (time_ref.bar - 1) + section_start_bar
        beat_within_bar = time_ref.beat - 1

        # Calculate absolute beat index
        beats_per_bar = self._beat_grid.beats_per_bar
        absolute_beat = (song_bar_0 * beats_per_bar) + beat_within_bar

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

    @staticmethod
    def _resolve_beat_count(
        duration: EffectDuration, bias: float = 0.5
    ) -> int:
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
