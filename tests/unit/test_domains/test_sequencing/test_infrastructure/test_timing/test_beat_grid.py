"""Tests for BeatGrid.

Tests the BeatGrid model which provides pre-calculated bar and beat boundaries.
"""

import pytest

from blinkb0t.core.domains.sequencing.infrastructure.timing.beat_grid import BeatGrid
from blinkb0t.core.domains.sequencing.infrastructure.timing.resolver import TimeResolver

# ============================================================================
# BeatGrid Creation Tests
# ============================================================================


def test_beatgrid_from_resolver():
    """Test BeatGrid creation from TimeResolver."""
    # Create a simple song features dict
    song_features = {
        "tempo_bpm": 120.0,
        "beats_s": [0.0, 0.5, 1.0, 1.5, 2.0, 2.5, 3.0, 3.5],  # 8 beats
        "bars_s": [0.0, 2.0],  # 2 bars
        "duration_s": 4.0,
        "assumptions": {"beats_per_bar": 4},
    }

    resolver = TimeResolver(song_features)
    beat_grid = BeatGrid.from_resolver(resolver, duration_ms=4000.0)

    assert beat_grid.tempo_bpm == 120.0
    assert beat_grid.beats_per_bar == 4
    assert beat_grid.duration_ms == 4000.0
    assert len(beat_grid.bar_boundaries) == 2
    assert len(beat_grid.beat_boundaries) == 8


def test_beatgrid_from_song_features():
    """Test BeatGrid creation directly from song features."""
    song_features = {
        "tempo_bpm": 120.0,
        "beats_s": [0.0, 0.5, 1.0, 1.5],  # 4 beats
        "bars_s": [0.0, 2.0],  # 2 bars (first bar only has 2 beats due to simplified test)
        "duration_s": 2.0,
        "assumptions": {"beats_per_bar": 4},
    }

    beat_grid = BeatGrid.from_song_features(song_features)

    assert beat_grid.tempo_bpm == 120.0
    assert beat_grid.duration_ms == 2000.0


def test_beatgrid_from_song_features_explicit_duration():
    """Test BeatGrid creation with explicit duration override."""
    song_features = {
        "tempo_bpm": 120.0,
        "beats_s": [0.0, 0.5, 1.0, 1.5],
        "bars_s": [0.0, 2.0],
        "duration_s": 2.0,
        "assumptions": {"beats_per_bar": 4},
    }

    beat_grid = BeatGrid.from_song_features(song_features, duration_ms=5000.0)

    assert beat_grid.duration_ms == 5000.0  # Override worked


# ============================================================================
# BeatGrid Properties Tests
# ============================================================================


def test_beatgrid_total_bars():
    """Test total_bars property."""
    song_features = {
        "tempo_bpm": 120.0,
        "beats_s": [0.0, 0.5, 1.0, 1.5, 2.0, 2.5, 3.0, 3.5],
        "bars_s": [0.0, 2.0, 4.0],  # 3 bars
        "duration_s": 6.0,
        "assumptions": {"beats_per_bar": 4},
    }

    beat_grid = BeatGrid.from_song_features(song_features)

    assert beat_grid.total_bars == 3


def test_beatgrid_total_beats():
    """Test total_beats property."""
    song_features = {
        "tempo_bpm": 120.0,
        "beats_s": [0.0, 0.5, 1.0, 1.5, 2.0, 2.5, 3.0, 3.5],  # 8 beats
        "bars_s": [0.0, 2.0],
        "duration_s": 4.0,
        "assumptions": {"beats_per_bar": 4},
    }

    beat_grid = BeatGrid.from_song_features(song_features)

    assert beat_grid.total_beats == 8


def test_beatgrid_ms_per_bar():
    """Test ms_per_bar property calculates correctly."""
    song_features = {
        "tempo_bpm": 120.0,
        "beats_s": [0.0, 0.5, 1.0, 1.5, 2.0, 2.5, 3.0, 3.5],
        "bars_s": [0.0, 2.0, 4.0],  # 2 second bars
        "duration_s": 6.0,
        "assumptions": {"beats_per_bar": 4},
    }

    beat_grid = BeatGrid.from_song_features(song_features)

    # Average bar duration: (4000 - 0) / (3 - 1) = 2000ms
    assert beat_grid.ms_per_bar == 2000.0


def test_beatgrid_ms_per_beat():
    """Test ms_per_beat property calculates correctly."""
    song_features = {
        "tempo_bpm": 120.0,
        "beats_s": [0.0, 0.5, 1.0, 1.5, 2.0],  # 0.5 second beats
        "bars_s": [0.0, 2.0],
        "duration_s": 2.5,
        "assumptions": {"beats_per_bar": 4},
    }

    beat_grid = BeatGrid.from_song_features(song_features)

    # Average beat duration: (2000 - 0) / (5 - 1) = 500ms
    assert beat_grid.ms_per_beat == 500.0


# ============================================================================
# BeatGrid Access Methods Tests
# ============================================================================


def test_get_bar_start_ms():
    """Test get_bar_start_ms method."""
    song_features = {
        "tempo_bpm": 120.0,
        "beats_s": [0.0, 0.5, 1.0, 1.5, 2.0, 2.5, 3.0, 3.5],
        "bars_s": [0.0, 2.0, 4.0],  # Bars at 0ms, 2000ms, 4000ms
        "duration_s": 6.0,
        "assumptions": {"beats_per_bar": 4},
    }

    beat_grid = BeatGrid.from_song_features(song_features)

    assert beat_grid.get_bar_start_ms(0) == 0.0
    assert beat_grid.get_bar_start_ms(1) == 2000.0
    assert beat_grid.get_bar_start_ms(2) == 4000.0


def test_get_bar_start_ms_out_of_range():
    """Test get_bar_start_ms raises IndexError for invalid index."""
    song_features = {
        "tempo_bpm": 120.0,
        "beats_s": [0.0, 0.5],
        "bars_s": [0.0],
        "duration_s": 1.0,
        "assumptions": {"beats_per_bar": 4},
    }

    beat_grid = BeatGrid.from_song_features(song_features)

    with pytest.raises(IndexError):
        beat_grid.get_bar_start_ms(5)  # Only 1 bar exists


def test_get_beat_time_ms():
    """Test get_beat_time_ms method."""
    song_features = {
        "tempo_bpm": 120.0,
        "beats_s": [0.0, 0.5, 1.0, 1.5, 2.0],  # Beats at 0, 500, 1000, 1500, 2000ms
        "bars_s": [0.0, 2.0],
        "duration_s": 2.5,
        "assumptions": {"beats_per_bar": 4},
    }

    beat_grid = BeatGrid.from_song_features(song_features)

    assert beat_grid.get_beat_time_ms(0) == 0.0
    assert beat_grid.get_beat_time_ms(1) == 500.0
    assert beat_grid.get_beat_time_ms(2) == 1000.0
    assert beat_grid.get_beat_time_ms(4) == 2000.0


def test_get_beat_time_ms_out_of_range():
    """Test get_beat_time_ms raises IndexError for invalid index."""
    song_features = {
        "tempo_bpm": 120.0,
        "beats_s": [0.0, 0.5],
        "bars_s": [0.0],
        "duration_s": 1.0,
        "assumptions": {"beats_per_bar": 4},
    }

    beat_grid = BeatGrid.from_song_features(song_features)

    with pytest.raises(IndexError):
        beat_grid.get_beat_time_ms(10)  # Only 2 beats exist


# ============================================================================
# BeatGrid Boundary Access Tests
# ============================================================================


def test_bar_boundaries_direct_access():
    """Test direct access to bar_boundaries list."""
    song_features = {
        "tempo_bpm": 120.0,
        "beats_s": [0.0, 0.5, 1.0, 1.5],
        "bars_s": [0.0, 2.0],
        "duration_s": 2.0,
        "assumptions": {"beats_per_bar": 4},
    }

    beat_grid = BeatGrid.from_song_features(song_features)

    assert len(beat_grid.bar_boundaries) == 2
    assert beat_grid.bar_boundaries[0] == 0.0
    assert beat_grid.bar_boundaries[-1] == 2000.0


def test_beat_boundaries_direct_access():
    """Test direct access to beat_boundaries list."""
    song_features = {
        "tempo_bpm": 120.0,
        "beats_s": [0.0, 0.5, 1.0, 1.5],
        "bars_s": [0.0, 2.0],
        "duration_s": 2.0,
        "assumptions": {"beats_per_bar": 4},
    }

    beat_grid = BeatGrid.from_song_features(song_features)

    assert len(beat_grid.beat_boundaries) == 4
    assert beat_grid.beat_boundaries[0] == 0.0
    assert beat_grid.beat_boundaries[-1] == 1500.0


# ============================================================================
# BeatGrid Quantization Tests (Critical for Beat Sync)
# ============================================================================


def test_snap_to_nearest_bar():
    """Test snapping arbitrary time to nearest bar boundary."""
    song_features = {
        "tempo_bpm": 120.0,
        "beats_s": [0.0, 0.5, 1.0, 1.5, 2.0, 2.5, 3.0, 3.5],
        "bars_s": [0.0, 2.0, 4.0],  # Bars at 0ms, 2000ms, 4000ms
        "duration_s": 6.0,
        "assumptions": {"beats_per_bar": 4},
    }

    beat_grid = BeatGrid.from_song_features(song_features)

    # Test snapping to exact boundaries
    assert beat_grid.snap_to_nearest_bar(0.0) == 0.0
    assert beat_grid.snap_to_nearest_bar(2000.0) == 2000.0

    # Test snapping slightly off times
    assert beat_grid.snap_to_nearest_bar(1950.0) == 2000.0  # 50ms before bar 2
    assert beat_grid.snap_to_nearest_bar(2050.0) == 2000.0  # 50ms after bar 2
    assert beat_grid.snap_to_nearest_bar(3900.0) == 4000.0  # Near bar 3

    # Test edge cases
    assert beat_grid.snap_to_nearest_bar(100.0) == 0.0  # Near start
    assert beat_grid.snap_to_nearest_bar(5000.0) == 4000.0  # Past last bar


def test_snap_to_nearest_beat():
    """Test snapping arbitrary time to nearest beat boundary."""
    song_features = {
        "tempo_bpm": 120.0,
        "beats_s": [0.0, 0.5, 1.0, 1.5, 2.0],  # Beats at 0, 500, 1000, 1500, 2000ms
        "bars_s": [0.0, 2.0],
        "duration_s": 2.5,
        "assumptions": {"beats_per_bar": 4},
    }

    beat_grid = BeatGrid.from_song_features(song_features)

    # Test snapping to exact boundaries
    assert beat_grid.snap_to_nearest_beat(500.0) == 500.0
    assert beat_grid.snap_to_nearest_beat(1000.0) == 1000.0

    # Test snapping slightly off times
    assert beat_grid.snap_to_nearest_beat(480.0) == 500.0  # 20ms before beat
    assert beat_grid.snap_to_nearest_beat(520.0) == 500.0  # 20ms after beat
    assert beat_grid.snap_to_nearest_beat(750.0) == 500.0  # Closer to beat 2 than beat 3
    assert beat_grid.snap_to_nearest_beat(850.0) == 1000.0  # Closer to beat 3

    # Test edge cases
    assert beat_grid.snap_to_nearest_beat(50.0) == 0.0  # Near start
    assert beat_grid.snap_to_nearest_beat(2500.0) == 2000.0  # Past last beat


def test_snap_to_beat_or_bar():
    """Test snapping with boundary type detection."""
    song_features = {
        "tempo_bpm": 120.0,
        "beats_s": [0.0, 0.5, 1.0, 1.5, 2.0],  # Beat 3 (at 1.0s) is also bar 1
        "bars_s": [0.0, 2.0],
        "duration_s": 2.5,
        "assumptions": {"beats_per_bar": 4},
    }

    beat_grid = BeatGrid.from_song_features(song_features)

    # Snap to bar boundary (downbeat)
    time, boundary_type = beat_grid.snap_to_beat_or_bar(1950.0)
    assert time == 2000.0
    assert boundary_type == "bar"

    # Snap to beat boundary (not a bar)
    time, boundary_type = beat_grid.snap_to_beat_or_bar(480.0)
    assert time == 500.0
    assert boundary_type == "beat"

    # Bar boundary should be detected as "bar" not "beat"
    time, boundary_type = beat_grid.snap_to_beat_or_bar(10.0)
    assert time == 0.0
    assert boundary_type == "bar"


def test_snap_to_beat_precise_sync():
    """Test that quantization ensures precise beat synchronization.

    This is the critical test for ensuring lights sync exactly to beats
    even when LLM-generated times are slightly off.
    """
    # Realistic scenario: 120 BPM (exactly 500ms per beat for clean test)
    song_features = {
        "tempo_bpm": 120.0,
        "beats_s": [0.0, 0.5, 1.0, 1.5, 2.0, 2.5, 3.0, 3.5, 4.0],  # Every 500ms
        "bars_s": [0.0, 2.0, 4.0],  # Every 2 seconds
        "duration_s": 4.5,
        "assumptions": {"beats_per_bar": 4},
    }

    beat_grid = BeatGrid.from_song_features(song_features)

    # Simulate LLM generating slightly off times (common with float arithmetic)
    llm_time_1 = 480.0  # Trying to hit beat 2 (at 500ms)
    llm_time_2 = 520.0  # Also trying to hit beat 2
    llm_time_3 = 990.0  # Trying to hit beat 3 (at 1000ms)
    llm_time_4 = 1510.0  # Trying to hit beat 4 (at 1500ms)

    # All should snap to exact beat boundaries
    assert beat_grid.snap_to_nearest_beat(llm_time_1) == 500.0
    assert beat_grid.snap_to_nearest_beat(llm_time_2) == 500.0
    assert beat_grid.snap_to_nearest_beat(llm_time_3) == 1000.0
    assert beat_grid.snap_to_nearest_beat(llm_time_4) == 1500.0

    # Verify precision: no drift, exact musical sync
    beat_2_time = beat_grid.snap_to_nearest_beat(llm_time_1)
    assert beat_2_time in beat_grid.beat_boundaries  # Guaranteed exact match

    # Test that even large offsets snap correctly
    assert beat_grid.snap_to_nearest_beat(2100.0) == 2000.0  # 100ms off → snaps to bar 2
    assert beat_grid.snap_to_nearest_beat(2900.0) == 3000.0  # 100ms off → snaps to beat


# ============================================================================
# Immutability Tests
# ============================================================================


def test_beatgrid_is_frozen():
    """Test that BeatGrid is immutable (frozen) to prevent accidental modification."""
    song_features = {
        "tempo_bpm": 120.0,
        "beats_s": [0.0, 0.5, 1.0],
        "bars_s": [0.0, 2.0],
        "duration_s": 1.5,
        "assumptions": {"beats_per_bar": 4},
    }

    beat_grid = BeatGrid.from_song_features(song_features)

    # Attempt to modify should raise ValidationError (Pydantic frozen model)
    with pytest.raises(Exception):  # Pydantic ValidationError  # noqa: B017
        beat_grid.tempo_bpm = 140.0

    with pytest.raises(Exception):  # noqa: B017
        beat_grid.duration_ms = 5000.0
