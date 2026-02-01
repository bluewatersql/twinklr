"""Tests for TimingContext and TimeRef resolution."""

from __future__ import annotations

import pytest

from twinklr.core.agents.sequencer.group_planner.models import TimeRef, TimeRefKind
from twinklr.core.agents.sequencer.group_planner.timing import (
    BarInfo,
    SectionBounds,
    TimingContext,
)


class TestTimingContext:
    """Tests for TimingContext model and TimeRef resolution."""

    @pytest.fixture
    def simple_timing(self) -> TimingContext:
        """Simple 4/4 time at 120 BPM (500ms per beat, 2000ms per bar)."""
        # 4 bars, 4 beats per bar
        return TimingContext(
            song_duration_ms=8000,
            beats_per_bar=4,
            bar_map={
                1: BarInfo(bar=1, start_ms=0, duration_ms=2000),
                2: BarInfo(bar=2, start_ms=2000, duration_ms=2000),
                3: BarInfo(bar=3, start_ms=4000, duration_ms=2000),
                4: BarInfo(bar=4, start_ms=6000, duration_ms=2000),
            },
            section_bounds={
                "verse_1": SectionBounds(
                    section_id="verse_1",
                    start=TimeRef(kind=TimeRefKind.BAR_BEAT, bar=1, beat=1),
                    end=TimeRef(kind=TimeRefKind.BAR_BEAT, bar=2, beat=1),
                ),
                "chorus_1": SectionBounds(
                    section_id="chorus_1",
                    start=TimeRef(kind=TimeRefKind.BAR_BEAT, bar=3, beat=1),
                    end=TimeRef(kind=TimeRefKind.BAR_BEAT, bar=4, beat=1),
                ),
            },
        )

    def test_resolve_bar_beat_to_ms(self, simple_timing: TimingContext) -> None:
        """Resolve BAR_BEAT TimeRef to milliseconds."""
        # Bar 1, beat 1 = 0ms
        ref = TimeRef(kind=TimeRefKind.BAR_BEAT, bar=1, beat=1)
        assert simple_timing.resolve_to_ms(ref) == 0

        # Bar 2, beat 1 = 2000ms
        ref = TimeRef(kind=TimeRefKind.BAR_BEAT, bar=2, beat=1)
        assert simple_timing.resolve_to_ms(ref) == 2000

        # Bar 1, beat 3 = 1000ms (beat 1=0, beat 2=500, beat 3=1000)
        ref = TimeRef(kind=TimeRefKind.BAR_BEAT, bar=1, beat=3)
        assert simple_timing.resolve_to_ms(ref) == 1000

    def test_resolve_bar_beat_with_offset(self, simple_timing: TimingContext) -> None:
        """Resolve BAR_BEAT with offset_ms nudge."""
        # Bar 1, beat 1 + 50ms offset = 50ms
        ref = TimeRef(kind=TimeRefKind.BAR_BEAT, bar=1, beat=1, offset_ms=50)
        assert simple_timing.resolve_to_ms(ref) == 50

    def test_resolve_bar_beat_with_beat_frac(self, simple_timing: TimingContext) -> None:
        """Resolve BAR_BEAT with beat_frac (sub-beat timing)."""
        # Bar 1, beat 1, beat_frac=0.5 = 250ms (half beat at 500ms/beat)
        ref = TimeRef(kind=TimeRefKind.BAR_BEAT, bar=1, beat=1, beat_frac=0.5)
        assert simple_timing.resolve_to_ms(ref) == 250

    def test_resolve_ms_passthrough(self, simple_timing: TimingContext) -> None:
        """MS TimeRef returns offset_ms directly."""
        ref = TimeRef(kind=TimeRefKind.MS, offset_ms=3500)
        assert simple_timing.resolve_to_ms(ref) == 3500

    def test_get_section_bounds(self, simple_timing: TimingContext) -> None:
        """Get section bounds by section_id."""
        bounds = simple_timing.get_section_bounds("verse_1")
        assert bounds is not None
        assert bounds.section_id == "verse_1"
        assert simple_timing.get_section_bounds("nonexistent") is None

    def test_resolve_section_bounds_to_ms(self, simple_timing: TimingContext) -> None:
        """Resolve section bounds to ms range."""
        start_ms, end_ms = simple_timing.resolve_section_bounds_ms("verse_1")
        assert start_ms == 0  # Bar 1, beat 1
        assert end_ms == 2000  # Bar 2, beat 1

    def test_bar_not_found_raises(self, simple_timing: TimingContext) -> None:
        """Resolving unknown bar raises ValueError."""
        ref = TimeRef(kind=TimeRefKind.BAR_BEAT, bar=99, beat=1)
        with pytest.raises(ValueError, match="Bar 99 not found"):
            simple_timing.resolve_to_ms(ref)

    def test_beat_duration_ms(self, simple_timing: TimingContext) -> None:
        """Get beat duration from bar info."""
        # Bar 1: 2000ms / 4 beats = 500ms per beat
        assert simple_timing.beat_duration_ms(bar=1) == 500
