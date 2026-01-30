"""Tests for BeatGrid.snap_to_grid() quantization method.

Tests the comprehensive snap_to_grid() method with support for:
- 4 quantization levels: bar, beat, eighth, sixteenth
- 3 directions: nearest, floor, ceil
"""

import pytest

from twinklr.core.sequencer.timing.beat_grid import BeatGrid

# ============================================================================
# Fixture Setup
# ============================================================================


@pytest.fixture
def standard_grid():
    """Standard 120 BPM grid for testing (500ms per beat)."""
    song_features = {
        "tempo_bpm": 120.0,
        "beats_s": [0.0, 0.5, 1.0, 1.5, 2.0, 2.5, 3.0, 3.5, 4.0],  # 9 beats
        "bars_s": [0.0, 2.0, 4.0],  # 3 bars (4 beats each)
        "duration_s": 4.5,
        "assumptions": {"beats_per_bar": 4},
    }
    return BeatGrid.from_song_features(song_features)


# ============================================================================
# Bar-Level Quantization Tests
# ============================================================================


def test_snap_to_grid_bar_nearest(standard_grid):
    """Test snapping to nearest bar boundary."""
    # Exactly on bar
    assert standard_grid.snap_to_grid(0.0, quantize_to="bar", direction="nearest") == 0.0
    assert standard_grid.snap_to_grid(2000.0, quantize_to="bar", direction="nearest") == 2000.0

    # Closer to first bar
    assert standard_grid.snap_to_grid(900.0, quantize_to="bar", direction="nearest") == 0.0

    # Closer to second bar
    assert standard_grid.snap_to_grid(1100.0, quantize_to="bar", direction="nearest") == 2000.0

    # Exactly at midpoint - should round to nearest (implementation choice)
    result = standard_grid.snap_to_grid(1000.0, quantize_to="bar", direction="nearest")
    assert result in [0.0, 2000.0]


def test_snap_to_grid_bar_floor(standard_grid):
    """Test snapping down to previous bar boundary."""
    # On boundary
    assert standard_grid.snap_to_grid(0.0, quantize_to="bar", direction="floor") == 0.0
    assert standard_grid.snap_to_grid(2000.0, quantize_to="bar", direction="floor") == 2000.0

    # Between bars - always round down
    assert standard_grid.snap_to_grid(100.0, quantize_to="bar", direction="floor") == 0.0
    assert standard_grid.snap_to_grid(1900.0, quantize_to="bar", direction="floor") == 0.0
    assert standard_grid.snap_to_grid(2100.0, quantize_to="bar", direction="floor") == 2000.0
    assert standard_grid.snap_to_grid(3999.0, quantize_to="bar", direction="floor") == 2000.0


def test_snap_to_grid_bar_ceil(standard_grid):
    """Test snapping up to next bar boundary."""
    # On boundary
    assert standard_grid.snap_to_grid(0.0, quantize_to="bar", direction="ceil") == 0.0
    assert standard_grid.snap_to_grid(2000.0, quantize_to="bar", direction="ceil") == 2000.0

    # Between bars - always round up
    assert standard_grid.snap_to_grid(100.0, quantize_to="bar", direction="ceil") == 2000.0
    assert standard_grid.snap_to_grid(1900.0, quantize_to="bar", direction="ceil") == 2000.0
    assert standard_grid.snap_to_grid(2100.0, quantize_to="bar", direction="ceil") == 4000.0
    assert standard_grid.snap_to_grid(3999.0, quantize_to="bar", direction="ceil") == 4000.0


# ============================================================================
# Beat-Level Quantization Tests
# ============================================================================


def test_snap_to_grid_beat_nearest(standard_grid):
    """Test snapping to nearest beat boundary."""
    # Exactly on beat
    assert standard_grid.snap_to_grid(500.0, quantize_to="beat", direction="nearest") == 500.0
    assert standard_grid.snap_to_grid(1500.0, quantize_to="beat", direction="nearest") == 1500.0

    # Closer to beat 1
    assert standard_grid.snap_to_grid(480.0, quantize_to="beat", direction="nearest") == 500.0

    # Closer to beat 2
    assert standard_grid.snap_to_grid(520.0, quantize_to="beat", direction="nearest") == 500.0

    # Between beats
    assert standard_grid.snap_to_grid(750.0, quantize_to="beat", direction="nearest") == 1000.0


def test_snap_to_grid_beat_floor(standard_grid):
    """Test snapping down to previous beat boundary."""
    # On beat
    assert standard_grid.snap_to_grid(500.0, quantize_to="beat", direction="floor") == 500.0

    # Between beats - always round down
    assert standard_grid.snap_to_grid(520.0, quantize_to="beat", direction="floor") == 500.0
    assert standard_grid.snap_to_grid(999.0, quantize_to="beat", direction="floor") == 500.0
    assert standard_grid.snap_to_grid(1450.0, quantize_to="beat", direction="floor") == 1000.0


def test_snap_to_grid_beat_ceil(standard_grid):
    """Test snapping up to next beat boundary."""
    # On beat
    assert standard_grid.snap_to_grid(500.0, quantize_to="beat", direction="ceil") == 500.0

    # Between beats - always round up
    assert standard_grid.snap_to_grid(480.0, quantize_to="beat", direction="ceil") == 500.0
    assert standard_grid.snap_to_grid(501.0, quantize_to="beat", direction="ceil") == 1000.0
    assert standard_grid.snap_to_grid(1450.0, quantize_to="beat", direction="ceil") == 1500.0


# ============================================================================
# Eighth-Level Quantization Tests
# ============================================================================


def test_snap_to_grid_eighth_nearest(standard_grid):
    """Test snapping to nearest eighth note boundary."""
    # Eighth notes are at: 0, 250, 500, 750, 1000, 1250, 1500, ...
    # (midpoint between each beat)

    # Exactly on eighth
    assert standard_grid.snap_to_grid(250.0, quantize_to="eighth", direction="nearest") == 250.0
    assert standard_grid.snap_to_grid(750.0, quantize_to="eighth", direction="nearest") == 750.0

    # Closer to eighth at 250
    assert standard_grid.snap_to_grid(230.0, quantize_to="eighth", direction="nearest") == 250.0

    # Closer to eighth at 500
    assert standard_grid.snap_to_grid(270.0, quantize_to="eighth", direction="nearest") == 250.0

    # Between eighths (375 is equidistant from 250 and 500, rounds up on ties)
    assert standard_grid.snap_to_grid(375.0, quantize_to="eighth", direction="nearest") == 500.0


def test_snap_to_grid_eighth_floor(standard_grid):
    """Test snapping down to previous eighth note boundary."""
    # Eighths at: 0, 250, 500, 750, 1000, ...

    # On eighth
    assert standard_grid.snap_to_grid(250.0, quantize_to="eighth", direction="floor") == 250.0

    # Between eighths - round down
    assert standard_grid.snap_to_grid(260.0, quantize_to="eighth", direction="floor") == 250.0
    assert standard_grid.snap_to_grid(499.0, quantize_to="eighth", direction="floor") == 250.0
    assert standard_grid.snap_to_grid(625.0, quantize_to="eighth", direction="floor") == 500.0


def test_snap_to_grid_eighth_ceil(standard_grid):
    """Test snapping up to next eighth note boundary."""
    # On eighth
    assert standard_grid.snap_to_grid(250.0, quantize_to="eighth", direction="ceil") == 250.0

    # Between eighths - round up
    assert standard_grid.snap_to_grid(240.0, quantize_to="eighth", direction="ceil") == 250.0
    assert standard_grid.snap_to_grid(251.0, quantize_to="eighth", direction="ceil") == 500.0
    assert standard_grid.snap_to_grid(625.0, quantize_to="eighth", direction="ceil") == 750.0


# ============================================================================
# Sixteenth-Level Quantization Tests
# ============================================================================


def test_snap_to_grid_sixteenth_nearest(standard_grid):
    """Test snapping to nearest sixteenth note boundary."""
    # Sixteenths at: 0, 125, 250, 375, 500, 625, 750, 875, 1000, ...
    # (each beat divided into 4)

    # Exactly on sixteenth
    assert standard_grid.snap_to_grid(125.0, quantize_to="sixteenth", direction="nearest") == 125.0
    assert standard_grid.snap_to_grid(375.0, quantize_to="sixteenth", direction="nearest") == 375.0

    # Closer to sixteenth at 125
    assert standard_grid.snap_to_grid(120.0, quantize_to="sixteenth", direction="nearest") == 125.0

    # Between sixteenths (190 is 65ms from 125, 60ms from 250, so snaps to 250)
    assert standard_grid.snap_to_grid(190.0, quantize_to="sixteenth", direction="nearest") == 250.0


def test_snap_to_grid_sixteenth_floor(standard_grid):
    """Test snapping down to previous sixteenth note boundary."""
    # Sixteenths at: 0, 125, 250, 375, 500, ...

    # On sixteenth
    assert standard_grid.snap_to_grid(125.0, quantize_to="sixteenth", direction="floor") == 125.0

    # Between sixteenths - round down
    assert standard_grid.snap_to_grid(130.0, quantize_to="sixteenth", direction="floor") == 125.0
    assert standard_grid.snap_to_grid(249.0, quantize_to="sixteenth", direction="floor") == 125.0
    assert standard_grid.snap_to_grid(400.0, quantize_to="sixteenth", direction="floor") == 375.0


def test_snap_to_grid_sixteenth_ceil(standard_grid):
    """Test snapping up to next sixteenth note boundary."""
    # On sixteenth
    assert standard_grid.snap_to_grid(125.0, quantize_to="sixteenth", direction="ceil") == 125.0

    # Between sixteenths - round up
    assert standard_grid.snap_to_grid(120.0, quantize_to="sixteenth", direction="ceil") == 125.0
    assert standard_grid.snap_to_grid(126.0, quantize_to="sixteenth", direction="ceil") == 250.0
    assert standard_grid.snap_to_grid(400.0, quantize_to="sixteenth", direction="ceil") == 500.0


# ============================================================================
# Edge Cases
# ============================================================================


def test_snap_to_grid_at_start(standard_grid):
    """Test quantization at the very start (time 0)."""
    assert standard_grid.snap_to_grid(0.0, quantize_to="bar", direction="nearest") == 0.0
    assert standard_grid.snap_to_grid(0.0, quantize_to="beat", direction="floor") == 0.0
    assert standard_grid.snap_to_grid(0.0, quantize_to="eighth", direction="ceil") == 0.0
    assert standard_grid.snap_to_grid(0.0, quantize_to="sixteenth", direction="nearest") == 0.0


def test_snap_to_grid_past_end(standard_grid):
    """Test quantization past the last boundary."""
    # Past last bar (at 4000ms)
    assert standard_grid.snap_to_grid(5000.0, quantize_to="bar", direction="floor") == 4000.0
    assert standard_grid.snap_to_grid(5000.0, quantize_to="bar", direction="nearest") == 4000.0

    # Past last beat (at 4000ms)
    assert standard_grid.snap_to_grid(5000.0, quantize_to="beat", direction="floor") == 4000.0


def test_snap_to_grid_tolerance(standard_grid):
    """Test that quantization handles floating-point precision (0.01ms tolerance)."""
    # Values within 0.01ms of boundary should snap to boundary
    assert standard_grid.snap_to_grid(499.99, quantize_to="beat", direction="nearest") == 500.0
    assert standard_grid.snap_to_grid(500.01, quantize_to="beat", direction="nearest") == 500.0
    assert standard_grid.snap_to_grid(1999.99, quantize_to="bar", direction="nearest") == 2000.0


# ============================================================================
# Invalid Input Tests
# ============================================================================


def test_snap_to_grid_invalid_quantize_level():
    """Test that invalid quantize_to values raise ValueError."""
    song_features = {
        "tempo_bpm": 120.0,
        "beats_s": [0.0, 0.5],
        "bars_s": [0.0],
        "duration_s": 1.0,
        "assumptions": {"beats_per_bar": 4},
    }
    grid = BeatGrid.from_song_features(song_features)

    with pytest.raises(ValueError, match="Invalid quantize_to"):
        grid.snap_to_grid(500.0, quantize_to="invalid", direction="nearest")


def test_snap_to_grid_invalid_direction():
    """Test that invalid direction values raise ValueError."""
    song_features = {
        "tempo_bpm": 120.0,
        "beats_s": [0.0, 0.5],
        "bars_s": [0.0],
        "duration_s": 1.0,
        "assumptions": {"beats_per_bar": 4},
    }
    grid = BeatGrid.from_song_features(song_features)

    with pytest.raises(ValueError, match="Invalid direction"):
        grid.snap_to_grid(500.0, quantize_to="beat", direction="invalid")


# ============================================================================
# Default Parameter Tests
# ============================================================================


def test_snap_to_grid_default_direction(standard_grid):
    """Test that direction defaults to 'nearest' if not specified."""
    # Should behave like nearest
    result = standard_grid.snap_to_grid(480.0, quantize_to="beat")
    expected = standard_grid.snap_to_grid(480.0, quantize_to="beat", direction="nearest")
    assert result == expected
