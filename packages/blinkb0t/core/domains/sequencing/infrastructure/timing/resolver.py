"""Time resolver - converts musical time (bars/beats) to absolute time (milliseconds).

The TimeResolver handles:
1. Loading audio-derived beat/bar positions
2. Converting pose IDs to pan/tilt angles
3. Accounting for fixture orientation (upside-down, rotation)
4. Composition with geometry offsets
"""

from __future__ import annotations

import logging
from typing import Any

import numpy as np

from blinkb0t.core.domains.sequencing.models.timing import MusicalTiming, QuantizeMode, TimingMode

logger = logging.getLogger(__name__)


class TimeResolver:
    """Converts musical time (bars/beats) to absolute time (milliseconds).

    Uses audio-derived beat positions for high accuracy. Falls back to
    mathematical estimation if audio data is incomplete.

    This resolver is universal and can be used across all sequencing domains.

    Example:
        resolver = TimeResolver(song_features)

        # Convert bars to milliseconds
        start_ms = resolver.bars_to_ms(2.5)  # Start at bar 2.5

        # Resolve musical timing to absolute timing
        start_ms, end_ms = resolver.resolve_timing(musical_timing)
    """

    def __init__(self, song_features: dict[str, Any]):
        """Initialize TimeResolver with audio analysis results.

        Args:
            song_features: Audio analysis results from AudioAnalyzer
                Required keys:
                - beats_s: List of beat positions in seconds
                - bars_s: List of bar positions in seconds
                - tempo_bpm: Average tempo
                - duration_s: Song duration
                - assumptions.beats_per_bar: Time signature (default 4)
        """
        # Extract timing arrays
        self.beats_s = np.array(song_features.get("beats_s", []), dtype=np.float64)
        self.bars_s = np.array(song_features.get("bars_s", []), dtype=np.float64)
        self.tempo_bpm = song_features.get("tempo_bpm", 120.0)
        self.duration_s = song_features.get("duration_s", 0.0)
        self.beats_per_bar = song_features.get("assumptions", {}).get("beats_per_bar", 4)

        # Validate we have usable data
        if len(self.beats_s) == 0 or len(self.bars_s) == 0:
            logger.warning(
                "TimeResolver initialized with empty beat/bar arrays. "
                "Will fall back to mathematical estimation."
            )

        # Precompute bar boundaries for efficient lookups
        self._bar_count = len(self.bars_s)

        # Log initialization
        logger.debug(
            f"TimeResolver initialized: {self._bar_count} bars, "
            f"{len(self.beats_s)} beats, tempo={self.tempo_bpm:.1f} BPM"
        )

    def bars_to_ms(self, bars: float, quantize: QuantizeMode = QuantizeMode.NONE) -> int:
        """Convert bar position to milliseconds.

        Args:
            bars: Bar position (0.0 = start, 1.0 = bar 1, 2.5 = halfway through bar 2)
            quantize: Quantization mode for alignment

        Returns:
            Time in milliseconds

        Example:
            start_ms = resolver.bars_to_ms(2.5)  # Halfway through bar 2
            bar_start = resolver.bars_to_ms(3.0, quantize=QuantizeMode.DOWNBEAT)
        """
        if quantize != QuantizeMode.NONE:
            bars = self._quantize_bars(bars, quantize)

        # Audio-derived conversion (high accuracy)
        if len(self.bars_s) >= 2:
            return self._bars_to_ms_audio_derived(bars)

        # Mathematical fallback
        logger.warning(f"Using mathematical fallback for bars_to_ms({bars})")
        return self._bars_to_ms_mathematical(bars)

    def beats_to_ms(self, beats: float, quantize: QuantizeMode = QuantizeMode.NONE) -> int:
        """Convert beat position to milliseconds.

        Args:
            beats: Beat position (0.0 = start, 1.0 = beat 1, 4.5 = halfway through beat 4)
            quantize: Quantization mode for alignment

        Returns:
            Time in milliseconds

        Example:
            start_ms = resolver.beats_to_ms(8.0)  # Beat 8
        """
        if quantize != QuantizeMode.NONE:
            beats = self._quantize_beats(beats, quantize)

        # Audio-derived conversion
        if len(self.beats_s) >= 2:
            return self._beats_to_ms_audio_derived(beats)

        # Mathematical fallback
        logger.warning(f"Using mathematical fallback for beats_to_ms({beats})")
        return self._beats_to_ms_mathematical(beats)

    def resolve_timing(self, timing: MusicalTiming) -> tuple[int, int]:
        """Resolve MusicalTiming to absolute start/end milliseconds.

        Args:
            timing: Musical timing specification

        Returns:
            (start_ms, end_ms) tuple

        Example:
            timing = MusicalTiming(
                start_offset_bars=2.0,
                duration_bars=4.0,
                quantize_start=QuantizeMode.DOWNBEAT
            )
            start_ms, end_ms = resolver.resolve_timing(timing)
        """
        if timing.mode == TimingMode.ABSOLUTE_MS:
            # Already in milliseconds
            assert timing.start_offset_ms is not None
            assert timing.duration_ms is not None
            return timing.start_offset_ms, timing.start_offset_ms + timing.duration_ms

        # Musical mode - convert bars to milliseconds
        start_ms = self.bars_to_ms(timing.start_offset_bars, quantize=timing.quantize_start)

        end_bars = timing.start_offset_bars + timing.duration_bars
        end_ms = self.bars_to_ms(end_bars, quantize=timing.quantize_end)

        return start_ms, end_ms

    def get_bar_boundaries_ms(self) -> list[int]:
        """Get all bar boundary positions in milliseconds.

        Returns:
            List of bar start times in milliseconds

        Example:
            bar_boundaries = resolver.get_bar_boundaries_ms()
            # [0, 1875, 3750, 5625, ...]
        """
        return [int(t * 1000) for t in self.bars_s]

    def get_beat_positions_ms(self) -> list[int]:
        """Get all beat positions in milliseconds.

        Returns:
            List of beat times in milliseconds

        Example:
            beats = resolver.get_beat_positions_ms()
            # [0, 468, 937, 1406, ...]
        """
        return [int(t * 1000) for t in self.beats_s]

    def ms_to_bars(self, ms: int) -> float:
        """Convert milliseconds to bar position (inverse operation).

        Args:
            ms: Time in milliseconds

        Returns:
            Bar position (e.g., 2.5 = halfway through bar 2)

        Example:
            bars = resolver.ms_to_bars(5000)  # ~2.67 bars at 120 BPM
        """
        seconds = ms / 1000.0

        # Audio-derived
        if len(self.bars_s) >= 2:
            # Find surrounding bars and interpolate
            if seconds <= self.bars_s[0]:
                return 0.0

            if seconds >= self.bars_s[-1]:
                # Extrapolate beyond last bar
                bar_duration = self.bars_s[-1] - self.bars_s[-2]
                excess = seconds - self.bars_s[-1]
                return float(len(self.bars_s) - 1 + (excess / bar_duration))

            # Interpolate between bars
            for i in range(len(self.bars_s) - 1):
                if self.bars_s[i] <= seconds < self.bars_s[i + 1]:
                    bar_duration = self.bars_s[i + 1] - self.bars_s[i]
                    progress = (seconds - self.bars_s[i]) / bar_duration
                    return float(i + progress)

        # Mathematical fallback
        bar_duration_s = 60.0 / self.tempo_bpm * self.beats_per_bar
        return float(seconds / bar_duration_s)

    # ======================================================================
    # Private methods
    # ======================================================================

    def _bars_to_ms_audio_derived(self, bars: float) -> int:
        """Convert bars to ms using audio-derived bar positions."""
        # Clamp to valid range
        if bars <= 0.0:
            return 0

        # Beyond last bar - extrapolate
        if bars >= len(self.bars_s):
            # Use average bar duration from last few bars for extrapolation
            if len(self.bars_s) >= 3:
                avg_bar_duration = float(np.mean(np.diff(self.bars_s[-3:])))
            else:
                avg_bar_duration = float(np.mean(np.diff(self.bars_s)))

            excess_bars = bars - (len(self.bars_s) - 1)
            seconds = self.bars_s[-1] + (excess_bars * avg_bar_duration)
            return int(seconds * 1000)

        # Interpolate between bars
        bar_idx = int(bars)  # Floor to get bar index
        progress = bars - bar_idx  # Fractional part

        if bar_idx >= len(self.bars_s) - 1:
            # At or past last bar
            seconds = self.bars_s[-1]
        else:
            # Linear interpolation between bar_idx and bar_idx+1
            bar_start_s = self.bars_s[bar_idx]
            bar_end_s = self.bars_s[bar_idx + 1]
            seconds = bar_start_s + (bar_end_s - bar_start_s) * progress

        return int(seconds * 1000)

    def _bars_to_ms_mathematical(self, bars: float) -> int:
        """Fallback: mathematical conversion using average tempo."""
        # Bar duration = (60 / BPM) * beats_per_bar
        bar_duration_s = (60.0 / self.tempo_bpm) * self.beats_per_bar
        seconds = bars * bar_duration_s
        return int(seconds * 1000)

    def _beats_to_ms_audio_derived(self, beats: float) -> int:
        """Convert beats to ms using audio-derived beat positions."""
        if beats <= 0.0:
            return 0

        # Beyond last beat - extrapolate
        if beats >= len(self.beats_s):
            avg_beat_duration = float(np.mean(np.diff(self.beats_s[-4:])))  # Last 4 beats
            excess_beats = beats - (len(self.beats_s) - 1)
            seconds = self.beats_s[-1] + (excess_beats * avg_beat_duration)
            return int(seconds * 1000)

        # Interpolate between beats
        beat_idx = int(beats)
        progress = beats - beat_idx

        if beat_idx >= len(self.beats_s) - 1:
            seconds = self.beats_s[-1]
        else:
            beat_start_s = self.beats_s[beat_idx]
            beat_end_s = self.beats_s[beat_idx + 1]
            seconds = beat_start_s + (beat_end_s - beat_start_s) * progress

        return int(seconds * 1000)

    def _beats_to_ms_mathematical(self, beats: float) -> int:
        """Fallback: mathematical conversion using average tempo."""
        beat_duration_s = 60.0 / self.tempo_bpm
        seconds = beats * beat_duration_s
        return int(seconds * 1000)

    def _quantize_bars(self, bars: float, mode: QuantizeMode) -> float:
        """Quantize bar position to musical boundary."""
        if mode == QuantizeMode.NONE:
            return bars

        if mode == QuantizeMode.DOWNBEAT:
            # Snap to nearest bar boundary (0.0, 1.0, 2.0, etc.)
            return round(bars)

        if mode == QuantizeMode.HALF_BAR:
            # Snap to half-bar positions (0.0, 0.5, 1.0, 1.5, etc.)
            return round(bars * 2) / 2

        if mode == QuantizeMode.QUARTER_BAR:
            # Snap to quarter-bar positions (0.0, 0.25, 0.5, 0.75, 1.0, etc.)
            return round(bars * 4) / 4

        if mode == QuantizeMode.ANY_BEAT:
            # Snap to nearest beat (convert to beats, round, convert back)
            beats = bars * self.beats_per_bar
            beats_rounded = round(beats)
            return float(beats_rounded / self.beats_per_bar)

        return bars

    def _quantize_beats(self, beats: float, mode: QuantizeMode) -> float:
        """Quantize beat position to musical boundary."""
        if mode == QuantizeMode.NONE:
            return beats

        if mode == QuantizeMode.ANY_BEAT:
            # Snap to nearest beat
            return round(beats)

        if mode == QuantizeMode.DOWNBEAT:
            # Snap to bar boundaries (every N beats where N = beats_per_bar)
            bars = beats / self.beats_per_bar
            bars_rounded = round(bars)
            return float(bars_rounded * self.beats_per_bar)

        if mode == QuantizeMode.HALF_BAR:
            # Snap to half-bar positions
            bars = beats / self.beats_per_bar
            bars_quantized = round(bars * 2) / 2
            return float(bars_quantized * self.beats_per_bar)

        if mode == QuantizeMode.QUARTER_BAR:
            # Snap to quarter-bar positions
            bars = beats / self.beats_per_bar
            bars_quantized = round(bars * 4) / 4
            return float(bars_quantized * self.beats_per_bar)

        return beats
