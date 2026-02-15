"""Unit tests for section_map: section-to-bar mapping."""

from __future__ import annotations

import pytest

from twinklr.core.sequencer.display.composition.section_map import (
    _find_nearest_bar_index,
    build_section_bar_map,
)
from twinklr.core.sequencer.timing.beat_grid import BeatGrid


def _make_beat_grid(
    tempo_bpm: float = 120.0,
    beats_per_bar: int = 4,
    num_bars: int = 64,
) -> BeatGrid:
    """Create a synthetic BeatGrid for testing.

    At 120 BPM, 4/4:
    - 1 beat = 500ms
    - 1 bar  = 2000ms
    - 64 bars = 128000ms
    """
    ms_per_beat = 60_000.0 / tempo_bpm
    ms_per_bar = ms_per_beat * beats_per_bar
    total_beats = num_bars * beats_per_bar

    return BeatGrid(
        bar_boundaries=[i * ms_per_bar for i in range(num_bars + 1)],
        beat_boundaries=[i * ms_per_beat for i in range(total_beats + 1)],
        eighth_boundaries=[i * ms_per_beat / 2 for i in range(total_beats * 2 + 1)],
        sixteenth_boundaries=[i * ms_per_beat / 4 for i in range(total_beats * 4 + 1)],
        tempo_bpm=tempo_bpm,
        beats_per_bar=beats_per_bar,
        duration_ms=num_bars * ms_per_bar,
    )


# ── _find_nearest_bar_index ──────────────────────────────────────────


class TestFindNearestBarIndex:
    """Tests for the internal _find_nearest_bar_index helper."""

    def test_exact_match(self) -> None:
        """Returns exact index when time matches a bar boundary."""
        bars = [0.0, 2000.0, 4000.0, 6000.0]
        assert _find_nearest_bar_index(bars, 2000.0) == 1

    def test_snaps_to_nearest_below(self) -> None:
        """Snaps to the nearest bar below when closer."""
        bars = [0.0, 2000.0, 4000.0, 6000.0]
        # 2400 is closer to 2000 than 4000
        assert _find_nearest_bar_index(bars, 2400.0) == 1

    def test_snaps_to_nearest_above(self) -> None:
        """Snaps to the nearest bar above when closer."""
        bars = [0.0, 2000.0, 4000.0, 6000.0]
        # 3800 is closer to 4000 than 2000
        assert _find_nearest_bar_index(bars, 3800.0) == 2

    def test_first_boundary(self) -> None:
        """Time before first bar returns index 0."""
        bars = [100.0, 2100.0, 4100.0]
        assert _find_nearest_bar_index(bars, 0.0) == 0

    def test_last_boundary(self) -> None:
        """Time past last bar returns last index."""
        bars = [0.0, 2000.0, 4000.0]
        assert _find_nearest_bar_index(bars, 99999.0) == 2

    def test_empty_boundaries(self) -> None:
        """Empty boundaries returns 0."""
        assert _find_nearest_bar_index([], 1000.0) == 0

    def test_equidistant_prefers_earlier(self) -> None:
        """When equidistant, prefers the earlier bar (<=)."""
        bars = [0.0, 2000.0, 4000.0]
        # 1000 is exactly equidistant between 0 and 2000
        assert _find_nearest_bar_index(bars, 1000.0) == 0


# ── build_section_bar_map ────────────────────────────────────────────


class TestBuildSectionBarMap:
    """Tests for building the section → bar mapping."""

    def test_single_section_at_start(self) -> None:
        """Section starting at 0ms maps to bar 0."""
        grid = _make_beat_grid()
        result = build_section_bar_map(
            [("intro", 0, 2000)],
            grid,
        )
        assert "intro" in result
        assert result["intro"].start_bar == 0
        assert result["intro"].start_ms == 0.0

    def test_two_adjacent_sections(self) -> None:
        """Two sections map to adjacent bar ranges."""
        grid = _make_beat_grid()  # 2000ms per bar
        result = build_section_bar_map(
            [
                ("intro", 0, 2000),
                ("chorus_1", 2000, 10000),
            ],
            grid,
        )
        assert result["intro"].start_bar == 0
        assert result["intro"].end_bar == 1
        assert result["chorus_1"].start_bar == 1
        assert result["chorus_1"].end_bar == 5

    def test_section_boundary_snaps_to_nearest_bar(self) -> None:
        """Section boundary not on a bar snaps to nearest."""
        grid = _make_beat_grid()  # 2000ms per bar
        # 2300ms is closer to bar 1 (2000ms) than bar 2 (4000ms)
        result = build_section_bar_map(
            [("verse", 2300, 10000)],
            grid,
        )
        assert result["verse"].start_bar == 1
        assert result["verse"].start_ms == 2000.0

    def test_section_boundary_snaps_up(self) -> None:
        """Section boundary closer to next bar snaps up."""
        grid = _make_beat_grid()  # 2000ms per bar
        # 3800ms is closer to bar 2 (4000ms) than bar 1 (2000ms)
        result = build_section_bar_map(
            [("verse", 3800, 10000)],
            grid,
        )
        assert result["verse"].start_bar == 2
        assert result["verse"].start_ms == 4000.0

    def test_bar_count(self) -> None:
        """bar_count property returns correct value."""
        grid = _make_beat_grid()  # 2000ms per bar
        result = build_section_bar_map(
            [("chorus", 0, 8000)],
            grid,
        )
        assert result["chorus"].bar_count == 4

    def test_full_song_sections(self) -> None:
        """Multiple sections covering the full song."""
        grid = _make_beat_grid(num_bars=16)  # 16 bars = 32000ms
        sections = [
            ("intro", 0, 4000),  # bars 0-2
            ("verse", 4000, 16000),  # bars 2-8
            ("chorus", 16000, 32000),  # bars 8-16
        ]
        result = build_section_bar_map(sections, grid)

        assert result["intro"].start_bar == 0
        assert result["intro"].end_bar == 2
        assert result["verse"].start_bar == 2
        assert result["verse"].end_bar == 8
        assert result["chorus"].start_bar == 8
        assert result["chorus"].end_bar == 16

    def test_resolved_ms_comes_from_beatgrid(self) -> None:
        """start_ms/end_ms are BeatGrid bar boundaries, not raw input."""
        grid = _make_beat_grid()  # 2000ms per bar
        result = build_section_bar_map(
            [("verse", 2300, 9700)],  # NOT on bar boundaries
            grid,
        )
        # Snapped to bars 1 (2000) and 5 (10000)
        assert result["verse"].start_ms == 2000.0
        assert result["verse"].end_ms == 10000.0

    def test_end_bar_never_less_than_start(self) -> None:
        """Zero-length section still has end_bar >= start_bar."""
        grid = _make_beat_grid()
        result = build_section_bar_map(
            [("tiny", 500, 500)],
            grid,
        )
        assert result["tiny"].end_bar >= result["tiny"].start_bar

    def test_empty_sections_raises(self) -> None:
        """Empty sections list raises ValueError."""
        grid = _make_beat_grid()
        with pytest.raises(ValueError, match="sections must not be empty"):
            build_section_bar_map([], grid)
