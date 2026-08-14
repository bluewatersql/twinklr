"""P1P-T4: bar <-> millisecond conversion against the detected downbeats.

`get_bar_start_ms` and `nearest_bar_index` are the single grid authority every consumer
on the moving-heads path resolves time through. These tests cover the two shapes a
real recording has that a metronomic fixture hides — a first downbeat after 0 ms and
bars of unequal length — plus the bounds behaviour of `get_bar_start_ms`, which had
no production callers before this task and so was entirely unproven.
"""

from __future__ import annotations

import logging

import pytest

from twinklr.core.sequencer.timing.beat_grid import BeatGrid

# Bars: 1500-3500 (2000ms), 3500-6000 (2500ms), 6000-7500 (1500ms), 7500-10000 (2500ms).
# Average bar duration is (10000 - 1500) / 4 = 2125ms, which matches no actual bar.
UNEVEN_BARS = [1500.0, 3500.0, 6000.0, 7500.0, 10000.0]


def make_grid(bar_boundaries: list[float]) -> BeatGrid:
    """A grid with the given downbeats; beats are the downbeats (irrelevant here)."""
    return BeatGrid(
        bar_boundaries=bar_boundaries,
        beat_boundaries=list(bar_boundaries),
        eighth_boundaries=[],
        sixteenth_boundaries=[],
        tempo_bpm=120.0,
        beats_per_bar=4,
        duration_ms=bar_boundaries[-1] if bar_boundaries else 0.0,
    )


@pytest.fixture
def uneven() -> BeatGrid:
    return make_grid(UNEVEN_BARS)


class TestBarStartMs:
    def test_first_bar_is_the_first_detected_downbeat(self, uneven: BeatGrid) -> None:
        """Bar index 0 is `bar_boundaries[0]`, not 0 ms.

        This is the constant-offset half of the defect: every real recording has a
        lead-in, so anchoring at 0 ms shifts the whole show.
        """
        assert uneven.get_bar_start_ms(0) == 1500.0

    def test_in_range_indices_return_detected_boundaries_verbatim(self, uneven: BeatGrid) -> None:
        for index, expected in enumerate(UNEVEN_BARS):
            assert uneven.get_bar_start_ms(index) == expected

    def test_in_range_indices_do_not_use_the_average(self, uneven: BeatGrid) -> None:
        """The drift half: bar 3 is 6000ms, but 2 x the 2125ms average is 4250ms."""
        assert uneven.ms_per_bar == pytest.approx(2125.0)
        assert uneven.get_bar_start_ms(2) == 6000.0

    def test_fractional_index_interpolates_within_the_real_bar(self, uneven: BeatGrid) -> None:
        """Half of bar 3 (1500ms long) is 750ms in, not half an average bar."""
        assert uneven.get_bar_start_ms(2.5) == 6750.0

    def test_index_past_the_detected_range_extrapolates_from_the_average(
        self, uneven: BeatGrid
    ) -> None:
        """Out of range must render, not raise — sections can outrun the analysis."""
        assert uneven.get_bar_start_ms(5) == pytest.approx(10000.0 + uneven.ms_per_bar)
        assert uneven.get_bar_start_ms(6) == pytest.approx(10000.0 + 2 * uneven.ms_per_bar)

    def test_out_of_range_logs_the_fallback(
        self, uneven: BeatGrid, caplog: pytest.LogCaptureFixture
    ) -> None:
        with caplog.at_level(logging.DEBUG, logger="twinklr.core.sequencer.timing.beat_grid"):
            uneven.get_bar_start_ms(9)
        assert "past the detected grid" in caplog.text

    def test_negative_index_extrapolates_backwards(self, uneven: BeatGrid) -> None:
        assert uneven.get_bar_start_ms(-1) == pytest.approx(1500.0 - uneven.ms_per_bar)

    def test_empty_grid_falls_back_to_the_tempo_derived_average(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        empty = make_grid([])
        with caplog.at_level(logging.WARNING, logger="twinklr.core.sequencer.timing.beat_grid"):
            assert empty.get_bar_start_ms(2) == pytest.approx(2 * 2000.0)
        assert "no bar boundaries" in caplog.text

    def test_single_bar_grid_returns_its_only_downbeat(self) -> None:
        single = make_grid([1500.0])
        assert single.get_bar_start_ms(0) == 1500.0


class TestBarSpanMs:
    def test_span_measures_the_bars_it_actually_covers(self, uneven: BeatGrid) -> None:
        """One bar starting at index 2 is 1500ms; the average would say 2125ms."""
        assert uneven.bar_span_ms(2, 1) == 1500.0
        assert uneven.bar_span_ms(0, 2) == 4500.0


class TestNearestBarIndex:
    def test_resolves_to_the_nearest_downbeat_not_the_previous_one(self, uneven: BeatGrid) -> None:
        """The floor was the defect: a start just shy of a downbeat belongs to it.

        100ms after bar 2's downbeat resolves to bar 2; 100ms before bar 3's
        downbeat resolves to bar 3, where flooring would have said bar 2.
        """
        assert uneven.nearest_bar_index(3600.0) == 1
        assert uneven.nearest_bar_index(5900.0) == 2

    def test_exact_downbeats_resolve_to_themselves(self, uneven: BeatGrid) -> None:
        for index, boundary in enumerate(UNEVEN_BARS):
            assert uneven.nearest_bar_index(boundary) == index

    def test_time_before_the_first_downbeat_resolves_to_bar_one(self, uneven: BeatGrid) -> None:
        assert uneven.nearest_bar_index(0.0) == 0
        assert uneven.nearest_bar_index(400.0) == 0

    def test_time_past_the_grid_extrapolates(self, uneven: BeatGrid) -> None:
        assert uneven.nearest_bar_index(10000.0 + uneven.ms_per_bar) == 5

    def test_round_trip_is_identity_across_the_detected_range(self, uneven: BeatGrid) -> None:
        for index in range(len(UNEVEN_BARS)):
            assert uneven.nearest_bar_index(uneven.get_bar_start_ms(index)) == index

    def test_round_trip_survives_truncation_to_int(self, uneven: BeatGrid) -> None:
        """Callers store milliseconds as ints; truncation must not move the bar."""
        grid = make_grid([1500.7, 3500.2, 6000.9])
        for index in range(3):
            assert grid.nearest_bar_index(float(int(grid.get_bar_start_ms(index)))) == index

    def test_empty_grid_falls_back_to_the_average(self, caplog: pytest.LogCaptureFixture) -> None:
        empty = make_grid([])
        with caplog.at_level(logging.WARNING, logger="twinklr.core.sequencer.timing.beat_grid"):
            assert empty.nearest_bar_index(4100.0) == 2
        assert "no bar boundaries" in caplog.text


class TestSnapToNearestBarUsesTheSameResolution:
    def test_snap_returns_the_nearest_detected_downbeat(self, uneven: BeatGrid) -> None:
        assert uneven.snap_to_nearest_bar(5900.0) == 6000.0

    def test_snap_stays_clamped_to_an_existing_boundary(self, uneven: BeatGrid) -> None:
        """Unlike `get_bar_start_ms`, snapping never invents a boundary past the end."""
        assert uneven.snap_to_nearest_bar(99_000.0) == 10000.0
