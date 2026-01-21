"""Tests for BeatGrid subdivisions (eighth and sixteenth notes).

Tests that BeatGrid correctly calculates eighth and sixteenth note boundaries
from beat positions for precise musical quantization.
"""

from blinkb0t.core.domains.sequencing.infrastructure.timing.beat_grid import BeatGrid

# ============================================================================
# Eighth Note Boundary Tests
# ============================================================================


def test_eighth_boundaries_exist():
    """Test that eighth_boundaries property exists and is populated."""
    song_features = {
        "tempo_bpm": 120.0,
        "beats_s": [0.0, 0.5, 1.0, 1.5, 2.0],  # 5 beats
        "bars_s": [0.0, 2.0],  # 2 bars
        "duration_s": 2.5,
        "assumptions": {"beats_per_bar": 4},
    }

    beat_grid = BeatGrid.from_song_features(song_features)

    assert hasattr(beat_grid, "eighth_boundaries")
    assert isinstance(beat_grid.eighth_boundaries, list)
    assert len(beat_grid.eighth_boundaries) > 0


def test_eighth_boundaries_count():
    """Test eighth boundaries has correct count (2 per beat)."""
    song_features = {
        "tempo_bpm": 120.0,
        "beats_s": [0.0, 0.5, 1.0, 1.5, 2.0],  # 5 beats
        "bars_s": [0.0, 2.0],
        "duration_s": 2.5,
        "assumptions": {"beats_per_bar": 4},
    }

    beat_grid = BeatGrid.from_song_features(song_features)

    # Should have 2 eighth notes per beat
    # 5 beats = 10 eighth notes (but we only count subdivision points)
    # Between 5 beats, we have 4 intervals, each split in half = 4 midpoints
    # Plus original 5 beats = 9 total eighth note boundaries
    expected_count = len(beat_grid.beat_boundaries) * 2 - 1  # Include subdivisions
    assert len(beat_grid.eighth_boundaries) == expected_count


def test_eighth_boundaries_timing():
    """Test eighth boundaries are correctly positioned between beats."""
    song_features = {
        "tempo_bpm": 120.0,
        "beats_s": [0.0, 0.5, 1.0, 1.5],  # 4 beats at 500ms intervals
        "bars_s": [0.0, 2.0],
        "duration_s": 2.0,
        "assumptions": {"beats_per_bar": 4},
    }

    beat_grid = BeatGrid.from_song_features(song_features)

    # Expected: 0, 250, 500, 750, 1000, 1250, 1500 (ms)
    # (beat at 0, eighth at 250, beat at 500, eighth at 750, etc.)
    expected = [0.0, 250.0, 500.0, 750.0, 1000.0, 1250.0, 1500.0]
    assert beat_grid.eighth_boundaries == expected


def test_eighth_boundaries_sorted():
    """Test eighth boundaries are in ascending order."""
    song_features = {
        "tempo_bpm": 120.0,
        "beats_s": [0.0, 0.5, 1.0, 1.5, 2.0, 2.5],
        "bars_s": [0.0, 2.0],
        "duration_s": 3.0,
        "assumptions": {"beats_per_bar": 4},
    }

    beat_grid = BeatGrid.from_song_features(song_features)

    # Verify sorted
    assert beat_grid.eighth_boundaries == sorted(beat_grid.eighth_boundaries)


# ============================================================================
# Sixteenth Note Boundary Tests
# ============================================================================


def test_sixteenth_boundaries_exist():
    """Test that sixteenth_boundaries property exists and is populated."""
    song_features = {
        "tempo_bpm": 120.0,
        "beats_s": [0.0, 0.5, 1.0, 1.5, 2.0],
        "bars_s": [0.0, 2.0],
        "duration_s": 2.5,
        "assumptions": {"beats_per_bar": 4},
    }

    beat_grid = BeatGrid.from_song_features(song_features)

    assert hasattr(beat_grid, "sixteenth_boundaries")
    assert isinstance(beat_grid.sixteenth_boundaries, list)
    assert len(beat_grid.sixteenth_boundaries) > 0


def test_sixteenth_boundaries_count():
    """Test sixteenth boundaries has correct count (4 per beat)."""
    song_features = {
        "tempo_bpm": 120.0,
        "beats_s": [0.0, 0.5, 1.0, 1.5, 2.0],  # 5 beats
        "bars_s": [0.0, 2.0],
        "duration_s": 2.5,
        "assumptions": {"beats_per_bar": 4},
    }

    beat_grid = BeatGrid.from_song_features(song_features)

    # Should have 4 sixteenth notes per beat
    # 5 beats = 20 sixteenth notes, but 5 already exist as beat boundaries
    # So 4 intervals * 4 subdivisions each = 16 subdivision points
    # Plus original 5 beats = 17 total sixteenth note boundaries
    expected_count = len(beat_grid.beat_boundaries) * 4 - 3
    assert len(beat_grid.sixteenth_boundaries) == expected_count


def test_sixteenth_boundaries_timing():
    """Test sixteenth boundaries are correctly positioned."""
    song_features = {
        "tempo_bpm": 120.0,
        "beats_s": [0.0, 0.5, 1.0],  # 3 beats at 500ms intervals
        "bars_s": [0.0, 2.0],
        "duration_s": 1.5,
        "assumptions": {"beats_per_bar": 4},
    }

    beat_grid = BeatGrid.from_song_features(song_features)

    # Expected: 0, 125, 250, 375, 500, 625, 750, 875, 1000 (ms)
    # (4 sixteenth notes per beat of 500ms = 125ms per sixteenth)
    expected = [0.0, 125.0, 250.0, 375.0, 500.0, 625.0, 750.0, 875.0, 1000.0]
    assert beat_grid.sixteenth_boundaries == expected


def test_sixteenth_boundaries_sorted():
    """Test sixteenth boundaries are in ascending order."""
    song_features = {
        "tempo_bpm": 120.0,
        "beats_s": [0.0, 0.5, 1.0, 1.5, 2.0],
        "bars_s": [0.0, 2.0],
        "duration_s": 2.5,
        "assumptions": {"beats_per_bar": 4},
    }

    beat_grid = BeatGrid.from_song_features(song_features)

    # Verify sorted
    assert beat_grid.sixteenth_boundaries == sorted(beat_grid.sixteenth_boundaries)


# ============================================================================
# Total Count Properties
# ============================================================================


def test_total_eighths_property():
    """Test total_eighths property returns correct count."""
    song_features = {
        "tempo_bpm": 120.0,
        "beats_s": [0.0, 0.5, 1.0, 1.5],
        "bars_s": [0.0, 2.0],
        "duration_s": 2.0,
        "assumptions": {"beats_per_bar": 4},
    }

    beat_grid = BeatGrid.from_song_features(song_features)

    assert beat_grid.total_eighths == len(beat_grid.eighth_boundaries)


def test_total_sixteenths_property():
    """Test total_sixteenths property returns correct count."""
    song_features = {
        "tempo_bpm": 120.0,
        "beats_s": [0.0, 0.5, 1.0, 1.5],
        "bars_s": [0.0, 2.0],
        "duration_s": 2.0,
        "assumptions": {"beats_per_bar": 4},
    }

    beat_grid = BeatGrid.from_song_features(song_features)

    assert beat_grid.total_sixteenths == len(beat_grid.sixteenth_boundaries)


# ============================================================================
# Variable Tempo Tests
# ============================================================================


def test_eighth_boundaries_variable_tempo():
    """Test eighth boundaries work with variable tempo (uneven beat spacing)."""
    # Beats at irregular intervals (tempo changes)
    song_features = {
        "tempo_bpm": 120.0,  # Average
        "beats_s": [0.0, 0.4, 0.9, 1.5],  # Uneven spacing
        "bars_s": [0.0, 1.6],
        "duration_s": 2.0,
        "assumptions": {"beats_per_bar": 4},
    }

    beat_grid = BeatGrid.from_song_features(song_features)

    # Each eighth should be at midpoint between beats
    # Beat 0-1: 0.0 → 0.4, midpoint at 0.2 (200ms)
    # Beat 1-2: 0.4 → 0.9, midpoint at 0.65 (650ms)
    # Beat 2-3: 0.9 → 1.5, midpoint at 1.2 (1200ms)
    expected = [0.0, 200.0, 400.0, 650.0, 900.0, 1200.0, 1500.0]
    assert beat_grid.eighth_boundaries == expected


def test_sixteenth_boundaries_variable_tempo():
    """Test sixteenth boundaries work with variable tempo."""
    song_features = {
        "tempo_bpm": 120.0,
        "beats_s": [0.0, 0.4, 1.0],  # Uneven: 400ms then 600ms
        "bars_s": [0.0, 1.6],
        "duration_s": 1.5,
        "assumptions": {"beats_per_bar": 4},
    }

    beat_grid = BeatGrid.from_song_features(song_features)

    # Beat 0-1 (400ms): sixteenths at 0, 100, 200, 300, 400
    # Beat 1-2 (600ms): sixteenths at 400, 550, 700, 850, 1000
    expected = [0.0, 100.0, 200.0, 300.0, 400.0, 550.0, 700.0, 850.0, 1000.0]
    assert beat_grid.sixteenth_boundaries == expected


# ============================================================================
# Edge Cases
# ============================================================================


def test_subdivisions_single_beat():
    """Test subdivisions work with a single beat."""
    song_features = {
        "tempo_bpm": 120.0,
        "beats_s": [0.0],  # Just one beat
        "bars_s": [0.0],
        "duration_s": 0.5,
        "assumptions": {"beats_per_bar": 4},
    }

    beat_grid = BeatGrid.from_song_features(song_features)

    # With only 1 beat, no subdivisions possible
    assert len(beat_grid.eighth_boundaries) == 1
    assert beat_grid.eighth_boundaries == [0.0]
    assert len(beat_grid.sixteenth_boundaries) == 1
    assert beat_grid.sixteenth_boundaries == [0.0]


def test_subdivisions_two_beats():
    """Test subdivisions work with exactly two beats."""
    song_features = {
        "tempo_bpm": 120.0,
        "beats_s": [0.0, 0.5],  # 2 beats
        "bars_s": [0.0],
        "duration_s": 1.0,
        "assumptions": {"beats_per_bar": 4},
    }

    beat_grid = BeatGrid.from_song_features(song_features)

    # 2 beats → 3 eighth boundaries (0, 250, 500)
    assert len(beat_grid.eighth_boundaries) == 3
    assert beat_grid.eighth_boundaries == [0.0, 250.0, 500.0]

    # 2 beats → 5 sixteenth boundaries (0, 125, 250, 375, 500)
    assert len(beat_grid.sixteenth_boundaries) == 5
    assert beat_grid.sixteenth_boundaries == [0.0, 125.0, 250.0, 375.0, 500.0]
