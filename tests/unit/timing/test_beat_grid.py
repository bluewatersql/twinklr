"""Tests for BeatGrid - adapted from .dev/tests.

Tests the BeatGrid model which provides pre-calculated bar and beat boundaries.
Imports updated for new architecture: core.sequencer.timing
"""

import pytest

from blinkb0t.core.sequencer.timing.beat_grid import BeatGrid
from blinkb0t.core.sequencer.timing.resolver import TimeResolver

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
        "bars_s": [0.0, 2.0],  # 2 bars
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
        "beats_s": [0.0, 0.5, 1.0, 1.5, 2.0, 2.5],  # 6 beats
        "bars_s": [0.0, 2.0],
        "duration_s": 3.0,
        "assumptions": {"beats_per_bar": 4},
    }

    beat_grid = BeatGrid.from_song_features(song_features)

    assert beat_grid.total_beats == 6


# ============================================================================
# Bar/Beat Conversion Tests
# ============================================================================


def test_bars_to_ms():
    """Test converting bars to milliseconds."""
    song_features = {
        "tempo_bpm": 120.0,  # 2 seconds per bar at 4/4
        "beats_s": [0.0, 0.5, 1.0, 1.5, 2.0, 2.5, 3.0, 3.5],
        "bars_s": [0.0, 2.0, 4.0],
        "duration_s": 6.0,
        "assumptions": {"beats_per_bar": 4},
    }

    beat_grid = BeatGrid.from_song_features(song_features)

    # API changed: now use bar_boundaries attribute (list) instead of bars_to_ms method
    # Test basic property access
    assert beat_grid.ms_per_bar == pytest.approx(2000.0, abs=1.0)


def test_ms_to_bars():
    """Test converting milliseconds to bars using properties."""
    song_features = {
        "tempo_bpm": 120.0,
        "beats_s": [0.0, 0.5, 1.0, 1.5, 2.0, 2.5, 3.0, 3.5],
        "bars_s": [0.0, 2.0, 4.0],
        "duration_s": 6.0,
        "assumptions": {"beats_per_bar": 4},
    }

    beat_grid = BeatGrid.from_song_features(song_features)

    # API changed: test properties instead of conversion methods
    assert beat_grid.total_bars == 3
    assert beat_grid.ms_per_bar == pytest.approx(2000.0, abs=1.0)


def test_beats_to_ms():
    """Test beat timing calculations."""
    song_features = {
        "tempo_bpm": 120.0,  # 500ms per beat
        "beats_s": [0.0, 0.5, 1.0, 1.5],
        "bars_s": [0.0, 2.0],
        "duration_s": 2.0,
        "assumptions": {"beats_per_bar": 4},
    }

    beat_grid = BeatGrid.from_song_features(song_features)

    # API changed: test beat properties
    assert beat_grid.ms_per_beat == pytest.approx(500.0, abs=1.0)


def test_ms_to_beats():
    """Test beat timing properties."""
    song_features = {
        "tempo_bpm": 120.0,
        "beats_s": [0.0, 0.5, 1.0, 1.5],
        "bars_s": [0.0, 2.0],
        "duration_s": 2.0,
        "assumptions": {"beats_per_bar": 4},
    }

    beat_grid = BeatGrid.from_song_features(song_features)

    # API changed: test beat properties and boundaries
    assert beat_grid.total_beats == 4
    assert len(beat_grid.beat_boundaries) == 4


# ============================================================================
# Boundary Lookup Tests
# ============================================================================


def test_get_bar_boundaries():
    """Test getting bar boundaries in milliseconds."""
    song_features = {
        "tempo_bpm": 120.0,
        "beats_s": [0.0, 0.5, 1.0, 1.5, 2.0, 2.5, 3.0, 3.5],
        "bars_s": [0.0, 2.0, 4.0],  # 0ms, 2000ms, 4000ms
        "duration_s": 6.0,
        "assumptions": {"beats_per_bar": 4},
    }

    beat_grid = BeatGrid.from_song_features(song_features)

    # API changed: bar_boundaries is now a direct attribute (list)
    boundaries = beat_grid.bar_boundaries
    assert len(boundaries) == 3
    assert boundaries[0] == pytest.approx(0.0, abs=1.0)
    assert boundaries[1] == pytest.approx(2000.0, abs=1.0)
    assert boundaries[2] == pytest.approx(4000.0, abs=1.0)


def test_get_beat_boundaries():
    """Test getting beat boundaries in milliseconds."""
    song_features = {
        "tempo_bpm": 120.0,
        "beats_s": [0.0, 0.5, 1.0, 1.5],  # Every 500ms
        "bars_s": [0.0, 2.0],
        "duration_s": 2.0,
        "assumptions": {"beats_per_bar": 4},
    }

    beat_grid = BeatGrid.from_song_features(song_features)

    # API changed: beat_boundaries is now a direct attribute (list)
    boundaries = beat_grid.beat_boundaries
    assert len(boundaries) == 4
    assert boundaries[0] == pytest.approx(0.0, abs=1.0)
    assert boundaries[1] == pytest.approx(500.0, abs=1.0)
    assert boundaries[2] == pytest.approx(1000.0, abs=1.0)
    assert boundaries[3] == pytest.approx(1500.0, abs=1.0)


# ============================================================================
# Edge Case Tests
# ============================================================================


def test_beatgrid_with_non_integer_bars():
    """Test BeatGrid handles non-integer bar durations."""
    song_features = {
        "tempo_bpm": 120.0,
        "beats_s": [0.0, 0.5, 1.0, 1.5, 2.0, 2.5],
        "bars_s": [0.0, 2.0],
        "duration_s": 3.0,  # 1.5 bars
        "assumptions": {"beats_per_bar": 4},
    }

    beat_grid = BeatGrid.from_song_features(song_features)

    # Test fractional bar handling via properties
    assert beat_grid.duration_ms == 3000.0
    assert beat_grid.ms_per_bar == pytest.approx(2000.0, abs=1.0)


def test_beatgrid_empty_song():
    """Test BeatGrid with minimal song data."""
    song_features = {
        "tempo_bpm": 120.0,
        "beats_s": [0.0],
        "bars_s": [0.0],
        "duration_s": 0.5,
        "assumptions": {"beats_per_bar": 4},
    }

    beat_grid = BeatGrid.from_song_features(song_features)

    assert beat_grid.total_bars == 1
    assert beat_grid.total_beats == 1
