"""Tests for beat alignment and quantization.

Updated to test beat alignment functions in the new context module.
"""

from __future__ import annotations

from blinkb0t.core.domains.sequencing.moving_heads.context import (
    align_to_nearest_beat,
    get_beat_duration_ms,
    get_beats_in_range,
)


class TestBeatAlignment:
    """Test beat alignment utility functions."""

    def test_get_beats_in_range(self):
        """Test getting beats within a time range."""
        beats_s = [0.0, 0.5, 1.0, 1.5, 2.0, 2.5, 3.0]
        start_ms = 500
        end_ms = 2000

        beats = get_beats_in_range(beats_s, start_ms, end_ms)

        assert len(beats) == 3
        assert beats == [500, 1000, 1500]

    def test_align_to_nearest_beat(self):
        """Test aligning a time to the nearest beat."""
        beats_s = [0.0, 0.5, 1.0, 1.5, 2.0]

        # Time at 750ms is equidistant from 500ms and 1000ms - function returns 500ms
        aligned = align_to_nearest_beat(750, beats_s)
        assert aligned == 500

        # Time at 300ms should align to 500ms (0.5s beat) - closer by 200ms vs 700ms to 1000ms
        aligned = align_to_nearest_beat(300, beats_s)
        assert aligned == 500

        # Time at 900ms should align to 1000ms (1.0s beat) - closer by 100ms vs 400ms to 500ms
        aligned = align_to_nearest_beat(900, beats_s)
        assert aligned == 1000

    def test_get_beat_duration_ms(self):
        """Test calculating beat duration from BPM."""
        # 120 BPM = 0.5s per beat = 500ms
        duration = get_beat_duration_ms(120.0)
        assert duration == 500.0

        # 60 BPM = 1s per beat = 1000ms
        duration = get_beat_duration_ms(60.0)
        assert duration == 1000.0

    def test_align_to_nearest_beat_empty_beats(self):
        """Test alignment with no beats returns original time."""
        aligned = align_to_nearest_beat(1000, [])
        assert aligned == 1000
