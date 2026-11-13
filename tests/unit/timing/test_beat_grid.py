"""Tests for BeatGrid - adapted from .dev/tests.

Tests the BeatGrid model which provides pre-calculated bar and beat boundaries.
Imports updated for new architecture: core.sequencer.timing
"""

import pytest

from twinklr.core.sequencer.timing.beat_grid import BeatGrid
from twinklr.core.sequencer.timing.resolver import TimeResolver

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


class TestExtendedToDuration:
    """The grid continues past the last detected beat to the end of the song."""

    @staticmethod
    def _grid(duration_ms: float) -> BeatGrid:
        beats = [i * 500.0 for i in range(17)]  # 0..8000ms, 4 bars of 4/4 at 120 BPM
        return BeatGrid(
            bar_boundaries=[i * 2000.0 for i in range(5)],
            beat_boundaries=beats,
            eighth_boundaries=BeatGrid._calculate_eighth_boundaries(beats),
            sixteenth_boundaries=BeatGrid._calculate_sixteenth_boundaries(beats),
            tempo_bpm=120.0,
            beats_per_bar=4,
            duration_ms=duration_ms,
        )

    def test_tail_is_filled_at_the_average_beat_duration(self) -> None:
        extended = self._grid(duration_ms=12_300.0).extended_to_duration()

        assert extended.beat_boundaries[-1] == 12_000.0
        assert extended.bar_boundaries[-1] == 12_000.0
        assert extended.beat_boundaries[17:20] == [8500.0, 9000.0, 9500.0]

    def test_detected_boundaries_are_kept_verbatim(self) -> None:
        grid = self._grid(duration_ms=12_300.0)
        extended = grid.extended_to_duration()

        assert extended.beat_boundaries[:17] == grid.beat_boundaries
        assert extended.bar_boundaries[:5] == grid.bar_boundaries
        assert extended.duration_ms == grid.duration_ms

    def test_appended_downbeats_sit_on_appended_beats_when_the_grid_is_offset(self) -> None:
        """Real grids start mid-bar and drift; appended bars must still land on beats."""
        beats = [137.0 + i * 503.0 + (7.0 if i % 3 == 0 else -4.0) for i in range(18)]
        detected_bars = [beats[i] for i in range(1, 18, 4)]  # downbeat phase 1
        grid = BeatGrid(
            bar_boundaries=detected_bars,
            beat_boundaries=beats,
            eighth_boundaries=BeatGrid._calculate_eighth_boundaries(beats),
            sixteenth_boundaries=BeatGrid._calculate_sixteenth_boundaries(beats),
            tempo_bpm=119.3,
            beats_per_bar=4,
            duration_ms=16_000.0,
        )

        extended = grid.extended_to_duration()
        appended_bars = extended.bar_boundaries[len(detected_bars) :]

        assert len(appended_bars) >= 2
        for bar_ms in appended_bars:
            index = extended.beat_boundaries.index(bar_ms)
            assert index >= len(beats)
            assert index % 4 == 1  # same downbeat phase as the detected bars

    def test_subdivisions_follow_the_extended_beats(self) -> None:
        extended = self._grid(duration_ms=12_300.0).extended_to_duration()

        assert extended.eighth_boundaries[-1] >= 12_000.0
        assert extended.sixteenth_boundaries[-1] >= 12_000.0

    def test_grid_that_already_reaches_the_end_is_returned_unchanged(self) -> None:
        grid = self._grid(duration_ms=8_200.0)

        assert grid.extended_to_duration() is grid
