"""Unit tests for the TimingResolver."""

from __future__ import annotations

from twinklr.core.sequencer.display.composition.timing_resolver import (
    TimingResolver,
)
from twinklr.core.sequencer.timing.beat_grid import BeatGrid
from twinklr.core.sequencer.vocabulary import EffectDuration, PlanningTimeRef


def _make_beat_grid(
    tempo_bpm: float = 120.0,
    beats_per_bar: int = 4,
    num_bars: int = 16,
) -> BeatGrid:
    """Create a synthetic BeatGrid for testing.

    At 120 BPM:
    - 1 beat = 500ms
    - 1 bar = 2000ms
    - 16 bars = 32000ms
    """
    ms_per_beat = 60_000.0 / tempo_bpm
    ms_per_bar = ms_per_beat * beats_per_bar
    total_beats = num_bars * beats_per_bar

    beat_boundaries = [i * ms_per_beat for i in range(total_beats + 1)]
    bar_boundaries = [i * ms_per_bar for i in range(num_bars + 1)]
    eighth_boundaries = [i * ms_per_beat / 2 for i in range(total_beats * 2 + 1)]
    sixteenth_boundaries = [i * ms_per_beat / 4 for i in range(total_beats * 4 + 1)]

    return BeatGrid(
        bar_boundaries=bar_boundaries,
        beat_boundaries=beat_boundaries,
        eighth_boundaries=eighth_boundaries,
        sixteenth_boundaries=sixteenth_boundaries,
        tempo_bpm=tempo_bpm,
        beats_per_bar=beats_per_bar,
        duration_ms=num_bars * ms_per_bar,
    )


class TestTimingResolver:
    """Tests for the TimingResolver."""

    def test_first_beat_of_first_bar(self) -> None:
        """bar=1, beat=1 → 0ms."""
        grid = _make_beat_grid()
        resolver = TimingResolver(grid)
        ms = resolver.resolve_start_ms(PlanningTimeRef(bar=1, beat=1))
        assert ms == 0

    def test_second_beat(self) -> None:
        """bar=1, beat=2 → 500ms at 120 BPM."""
        grid = _make_beat_grid()
        resolver = TimingResolver(grid)
        ms = resolver.resolve_start_ms(PlanningTimeRef(bar=1, beat=2))
        assert ms == 500

    def test_second_bar(self) -> None:
        """bar=2, beat=1 → 2000ms at 120 BPM."""
        grid = _make_beat_grid()
        resolver = TimingResolver(grid)
        ms = resolver.resolve_start_ms(PlanningTimeRef(bar=2, beat=1))
        assert ms == 2000

    def test_hit_duration(self) -> None:
        """HIT = 1 beat = 500ms at 120 BPM."""
        grid = _make_beat_grid()
        resolver = TimingResolver(grid)
        end = resolver.resolve_end_ms(start_ms=0, duration=EffectDuration.HIT)
        assert end == 500

    def test_burst_duration(self) -> None:
        """BURST = 4 beats = 2000ms at 120 BPM."""
        grid = _make_beat_grid()
        resolver = TimingResolver(grid)
        end = resolver.resolve_end_ms(start_ms=0, duration=EffectDuration.BURST)
        assert end == 2000

    def test_phrase_duration_default_bias(self) -> None:
        """PHRASE at default bias (0.5) = 12 beats = 6000ms at 120 BPM."""
        grid = _make_beat_grid()
        resolver = TimingResolver(grid)
        end = resolver.resolve_end_ms(start_ms=0, duration=EffectDuration.PHRASE)
        # PHRASE range: 8-16 beats, bias=0.5 → 12 beats → 6000ms
        assert end == 6000

    def test_phrase_duration_max_bias(self) -> None:
        """PHRASE at max bias (1.0) = 16 beats = 8000ms at 120 BPM."""
        grid = _make_beat_grid()
        resolver = TimingResolver(grid)
        end = resolver.resolve_end_ms(start_ms=0, duration=EffectDuration.PHRASE, duration_bias=1.0)
        assert end == 8000

    def test_phrase_duration_min_bias(self) -> None:
        """PHRASE at min bias (0.0) = 8 beats = 4000ms at 120 BPM."""
        grid = _make_beat_grid()
        resolver = TimingResolver(grid)
        end = resolver.resolve_end_ms(start_ms=0, duration=EffectDuration.PHRASE, duration_bias=0.0)
        assert end == 4000

    def test_section_duration(self) -> None:
        """SECTION uses section_end_ms when provided."""
        grid = _make_beat_grid()
        resolver = TimingResolver(grid)
        end = resolver.resolve_end_ms(
            start_ms=0,
            duration=EffectDuration.SECTION,
            section_end_ms=15000,
        )
        assert end == 15000

    def test_section_fallback_to_sequence(self) -> None:
        """SECTION without section_end_ms uses sequence duration."""
        grid = _make_beat_grid()  # 32000ms
        resolver = TimingResolver(grid)
        end = resolver.resolve_end_ms(start_ms=0, duration=EffectDuration.SECTION)
        assert end == 32000

    def test_clamp_to_section_boundary(self) -> None:
        """Duration clamped to section end."""
        grid = _make_beat_grid()
        resolver = TimingResolver(grid)
        # EXTENDED at max bias = 32 beats = 16000ms, but section ends at 5000ms
        end = resolver.resolve_end_ms(
            start_ms=0,
            duration=EffectDuration.EXTENDED,
            section_end_ms=5000,
            duration_bias=1.0,
        )
        assert end == 5000

    def test_snap_to_grid(self) -> None:
        """Times are snapped to 20ms grid."""
        grid = _make_beat_grid()
        resolver = TimingResolver(grid)
        # At 120 BPM, beat times are exactly 500ms multiples,
        # which are already on the 20ms grid
        ms = resolver.resolve_start_ms(PlanningTimeRef(bar=1, beat=1))
        assert ms % 20 == 0


class TestTimingResolverSectionOffset:
    """Tests for section-relative bar/beat resolution."""

    def test_bar1_beat1_with_zero_offset(self) -> None:
        """section_start_bar=0 gives same result as no offset."""
        grid = _make_beat_grid()  # 120 BPM, 2000ms/bar
        resolver = TimingResolver(grid)
        ms = resolver.resolve_start_ms(PlanningTimeRef(bar=1, beat=1), section_start_bar=0)
        assert ms == 0

    def test_bar1_beat1_offset_to_bar4(self) -> None:
        """bar=1 in a section starting at song-bar 4 → 8000ms."""
        grid = _make_beat_grid()  # 120 BPM, 2000ms/bar
        resolver = TimingResolver(grid)
        # Song bar 4 starts at 4 * 2000 = 8000ms
        ms = resolver.resolve_start_ms(PlanningTimeRef(bar=1, beat=1), section_start_bar=4)
        assert ms == 8000

    def test_bar3_beat2_with_section_offset(self) -> None:
        """Section-relative bar=3, beat=2 with offset."""
        grid = _make_beat_grid()  # 120 BPM, 500ms/beat, 2000ms/bar
        resolver = TimingResolver(grid)
        # Section starts at song-bar 2 (4000ms)
        # bar=3 → song-bar 4, beat=2 → +500ms = 8000 + 500 = 8500
        ms = resolver.resolve_start_ms(PlanningTimeRef(bar=3, beat=2), section_start_bar=2)
        assert ms == 8500

    def test_section_offset_clamps_to_max_beat(self) -> None:
        """Large offset clamps to last available beat."""
        grid = _make_beat_grid(num_bars=4)  # 4 bars = 16 beats
        resolver = TimingResolver(grid)
        # bar=1 + offset=100 → song-bar 100 → way past 4 bars
        ms = resolver.resolve_start_ms(PlanningTimeRef(bar=1, beat=1), section_start_bar=100)
        # Clamped to last beat time, snapped to 20ms grid
        assert ms == resolver.snap(grid.beat_boundaries[-1])

    def test_section_offset_with_section_end(self) -> None:
        """SECTION duration respects section_end_ms from bar map."""
        grid = _make_beat_grid()  # 120 BPM, 2000ms/bar
        resolver = TimingResolver(grid)
        # Section starts at song-bar 4 (8000ms)
        start_ms = resolver.resolve_start_ms(PlanningTimeRef(bar=1, beat=1), section_start_bar=4)
        assert start_ms == 8000

        # Section ends at 16000ms (bar 8)
        end_ms = resolver.resolve_end_ms(
            start_ms=start_ms,
            duration=EffectDuration.SECTION,
            section_end_ms=16000,
        )
        assert end_ms == 16000
