"""Exact musical phase from the detected beat grid, with explicit boundary provenance."""

from __future__ import annotations

from fractions import Fraction
import math

import pytest

from twinklr.core.sequencer.timing.beat_grid import BeatGrid
from twinklr.core.sequencer.timing.musical_phase import (
    MusicalPhaseError,
    MusicalPhaseMap,
    PhaseKnot,
    build_musical_phase_map,
    musical_phase_at,
    musical_phase_fraction,
    musical_time_at,
)


def _grid(beats: list[float], duration_ms: float) -> BeatGrid:
    return BeatGrid(
        bar_boundaries=beats[:1],
        beat_boundaries=beats,
        eighth_boundaries=BeatGrid._calculate_eighth_boundaries(beats),
        sixteenth_boundaries=BeatGrid._calculate_sixteenth_boundaries(beats),
        tempo_bpm=120.0,
        beats_per_bar=4,
        duration_ms=duration_ms,
    )


def test_variable_tempo_phase_interpolates_between_observed_beats() -> None:
    phase_map = build_musical_phase_map(_grid([0, 500, 1000, 2000], 2000))

    assert musical_phase_at(phase_map, 1500, origin_ms=0, period_beats=1) == 2.5
    assert musical_phase_at(phase_map, 750, origin_ms=0, period_beats=1) == 1.5
    assert musical_phase_at(phase_map, 1500, origin_ms=0, period_beats=2) == 1.25


def test_phase_at_observed_beats_is_exactly_integer() -> None:
    beats = [0.0, 466.66666666666663, 933.3333333333333, 1400.0, 1871.2]
    phase_map = build_musical_phase_map(_grid(beats, 1871.2))

    for index, beat in enumerate(beats):
        phase = musical_phase_at(phase_map, beat, origin_ms=0, period_beats=1)
        assert phase == index
        assert float(phase).is_integer()


def test_tempo_grid_extends_to_duration_by_one_adjacent_interval() -> None:
    grid = BeatGrid.from_tempo(tempo_bpm=120, total_bars=1)
    assert grid.beat_boundaries == [0.0, 500.0, 1000.0, 1500.0]
    assert grid.duration_ms == 2000.0

    phase_map = build_musical_phase_map(grid)

    assert musical_phase_at(phase_map, 1980, origin_ms=0, period_beats=1) == 3.96
    assert musical_phase_at(phase_map, 2000, origin_ms=0, period_beats=1) == 4
    assert phase_map.knots[-1] == PhaseKnot(
        time_ms=2000.0, beat_index=4.0, provenance="adjacent_interval"
    )


def test_pickup_before_first_beat_is_inferred_and_traced() -> None:
    phase_map = build_musical_phase_map(_grid([100, 600, 1100], 1600))

    assert musical_phase_at(phase_map, 0, origin_ms=100, period_beats=1) == -0.2
    assert phase_map.knots[0] == PhaseKnot(
        time_ms=0.0, beat_index=-0.2, provenance="adjacent_interval"
    )
    assert [knot.provenance for knot in phase_map.knots] == [
        "adjacent_interval",
        "observed",
        "observed",
        "observed",
        "adjacent_interval",
    ]


def test_observed_beat_at_zero_needs_no_inferred_head() -> None:
    phase_map = build_musical_phase_map(_grid([0, 500, 1000], 1000))

    assert all(knot.provenance == "observed" for knot in phase_map.knots)


def test_long_tail_is_covered_one_interval_past_the_last_beat() -> None:
    grid = _grid([0, 500, 1000, 1500], 3500)

    phase_map = build_musical_phase_map(grid)
    assert (phase_map.covered_start_ms, phase_map.covered_end_ms) == (0, 2000)
    assert phase_map.knots[-1] == PhaseKnot(
        time_ms=2000.0, beat_index=4.0, provenance="adjacent_interval"
    )
    assert musical_phase_at(phase_map, 2000, origin_ms=0, period_beats=1) == 4
    with pytest.raises(MusicalPhaseError, match=r"\[0\.0, 2000\.0\]"):
        musical_phase_at(phase_map, 2500, origin_ms=0, period_beats=1)

    phase_map = build_musical_phase_map(
        grid, boundary_knots=(PhaseKnot(time_ms=3500, beat_index=7, provenance="explicit"),)
    )
    assert musical_phase_at(phase_map, 2500, origin_ms=0, period_beats=1) == 5
    assert phase_map.knots[-1].provenance == "explicit"


def test_long_head_is_covered_one_interval_before_the_first_beat() -> None:
    phase_map = build_musical_phase_map(_grid([700, 1200, 1700], 1700))

    assert (phase_map.covered_start_ms, phase_map.covered_end_ms) == (200, 1700)
    assert phase_map.knots[0] == PhaseKnot(
        time_ms=200.0, beat_index=-1.0, provenance="adjacent_interval"
    )
    with pytest.raises(MusicalPhaseError, match=r"\[200\.0, 1700\.0\]"):
        musical_phase_at(phase_map, 100, origin_ms=700, period_beats=1)


def test_silent_lead_in_is_covered_from_one_interval_before_the_first_beat() -> None:
    beats = [3000.0 + 500 * index for index in range(8)]
    phase_map = build_musical_phase_map(_grid(beats, beats[-1]))

    assert phase_map.covered_start_ms == 2500
    assert phase_map.knots[0] == PhaseKnot(
        time_ms=2500.0, beat_index=-1.0, provenance="adjacent_interval"
    )
    assert musical_phase_at(phase_map, 2500, origin_ms=3000, period_beats=1) == -1
    with pytest.raises(MusicalPhaseError, match=r"2000 ms lies outside .*\[2500\.0, 6500\.0\]"):
        musical_phase_at(phase_map, 2000, origin_ms=3000, period_beats=1)


def test_silent_edge_knot_keeps_the_adjacent_slope_exactly() -> None:
    """One interval past 2031.1 ms is not a float; the stored knot time is the nearest one,
    and phase up to it follows the adjacent observed interval's slope exactly."""
    phase_map = build_musical_phase_map(_grid([1596.3, 2031.1], 4000))

    interval = Fraction(2031.1) - Fraction(1596.3)
    end = Fraction(phase_map.covered_end_ms)
    assert end != Fraction(2031.1) + interval
    assert (
        musical_phase_fraction(
            phase_map, phase_map.covered_end_ms, origin_ms=2031.1, period_beats=1
        )
        == (end - Fraction(2031.1)) / interval
    )


def test_edges_within_one_interval_keep_the_phase1_knots() -> None:
    phase_map = build_musical_phase_map(_grid([100, 600, 1100], 1600))

    assert phase_map.model_dump() == {
        "knots": (
            {"time_ms": 0.0, "beat_index": -0.2, "provenance": "adjacent_interval"},
            {"time_ms": 100.0, "beat_index": 0.0, "provenance": "observed"},
            {"time_ms": 600.0, "beat_index": 1.0, "provenance": "observed"},
            {"time_ms": 1100.0, "beat_index": 2.0, "provenance": "observed"},
            {"time_ms": 1600.0, "beat_index": 3.0, "provenance": "adjacent_interval"},
        ),
        "duration_ms": 1600.0,
    }
    assert (phase_map.covered_start_ms, phase_map.covered_end_ms) == (0, 1600)


def test_mid_song_gap_is_one_long_beat() -> None:
    """Far-apart detected beats are one beat: no knot is added and nothing is held dark."""
    beats = [0.0, 500.0, 1000.0, 1500.0, 2000.0, 5000.0, 5500.0, 6000.0]
    phase_map = build_musical_phase_map(_grid(beats, 6000))

    assert musical_phase_at(phase_map, 3500, origin_ms=0, period_beats=1) == 4.5
    assert [knot.time_ms for knot in phase_map.knots] == beats
    assert all(knot.provenance == "observed" for knot in phase_map.knots)


def test_silent_edge_sweep_builds_every_grid() -> None:
    """961 grids at 120 BPM, lead-ins 0-3 s by 100 ms and tails 0-6 s by 200 ms, all build;
    each covered edge is the song edge or one interval beyond the outermost beat."""
    built = 0
    for lead_in in range(0, 3001, 100):
        for tail in range(0, 6001, 200):
            beats = [float(lead_in + 500 * index) for index in range(16)]
            grid = _grid(beats, beats[-1] + tail)
            phase_map = build_musical_phase_map(grid)

            first, last = grid.beat_boundaries[0], grid.beat_boundaries[-1]
            head = grid.beat_boundaries[1] - first
            tail_interval = last - grid.beat_boundaries[-2]
            assert phase_map.covered_start_ms == (0 if first <= head else first - head)
            assert phase_map.covered_end_ms == (
                grid.duration_ms
                if grid.duration_ms - last <= tail_interval
                else last + tail_interval
            )
            built += 1
    assert built == 961


@pytest.mark.parametrize("beats", [[], [500.0]])
def test_fewer_than_two_observed_beats_need_explicit_knots(beats: list[float]) -> None:
    grid = _grid(beats, 1000)

    with pytest.raises(MusicalPhaseError):
        build_musical_phase_map(grid)

    knots = (
        PhaseKnot(time_ms=0, beat_index=-1, provenance="explicit"),
        PhaseKnot(time_ms=1000, beat_index=1, provenance="explicit"),
    )
    phase_map = build_musical_phase_map(grid, boundary_knots=knots)
    assert musical_phase_at(phase_map, 1000, origin_ms=0, period_beats=1) == 2


@pytest.mark.parametrize(
    ("knot", "match"),
    [
        (PhaseKnot(time_ms=500, beat_index=1, provenance="explicit"), "observed"),
        (PhaseKnot(time_ms=750, beat_index=1.5, provenance="explicit"), "observed"),
        (PhaseKnot(time_ms=3500, beat_index=2, provenance="explicit"), "monoton"),
        (PhaseKnot(time_ms=3500, beat_index=7, provenance="observed"), "explicit"),
        (PhaseKnot(time_ms=3600, beat_index=7, provenance="explicit"), "domain"),
    ],
)
def test_explicit_knots_cannot_overwrite_beats_or_break_monotonicity(
    knot: PhaseKnot, match: str
) -> None:
    with pytest.raises(MusicalPhaseError, match=match):
        build_musical_phase_map(_grid([0, 500, 1000, 1500], 3500), boundary_knots=(knot,))


def test_explicit_tail_knot_inside_the_song_bounds_the_covered_span() -> None:
    phase_map = build_musical_phase_map(
        _grid([0, 500, 1000, 1500], 3500),
        boundary_knots=(PhaseKnot(time_ms=2500, beat_index=5, provenance="explicit"),),
    )

    assert phase_map.covered_end_ms == 2500
    assert phase_map.knots[-1] == PhaseKnot(time_ms=2500, beat_index=5, provenance="explicit")


def test_phase_is_evaluated_only_inside_the_domain() -> None:
    phase_map = build_musical_phase_map(_grid([0, 500, 1000], 1000))

    with pytest.raises(MusicalPhaseError, match="domain"):
        musical_phase_at(phase_map, 1001, origin_ms=0, period_beats=1)
    with pytest.raises(MusicalPhaseError, match="domain"):
        musical_phase_at(phase_map, 500, origin_ms=-1, period_beats=1)
    with pytest.raises(ValueError, match="period"):
        musical_phase_at(phase_map, 500, origin_ms=0, period_beats=0)


def test_observed_beats_outside_the_duration_are_rejected() -> None:
    with pytest.raises(MusicalPhaseError, match="domain"):
        build_musical_phase_map(_grid([0, 500, 1000, 1500], 1200))


def test_phase_map_requires_a_covered_monotonic_domain() -> None:
    partial = MusicalPhaseMap(
        knots=(
            PhaseKnot(time_ms=0, beat_index=0, provenance="observed"),
            PhaseKnot(time_ms=500, beat_index=1, provenance="observed"),
        ),
        duration_ms=1000,
    )
    assert (partial.covered_start_ms, partial.covered_end_ms) == (0, 500)
    assert "covered_start_ms" not in partial.model_dump()
    with pytest.raises(ValueError):
        MusicalPhaseMap(
            knots=(
                PhaseKnot(time_ms=0, beat_index=1, provenance="observed"),
                PhaseKnot(time_ms=1000, beat_index=1, provenance="observed"),
            ),
            duration_ms=1000,
        )
    with pytest.raises(ValueError, match="within"):
        MusicalPhaseMap(
            knots=(
                PhaseKnot(time_ms=500, beat_index=0, provenance="observed"),
                PhaseKnot(time_ms=1500, beat_index=1, provenance="observed"),
            ),
            duration_ms=1000,
        )


@pytest.mark.parametrize(("beats", "duration_ms"), [([0.0], 0.0), ([0.0, 500.0], math.inf)])
def test_unusable_duration_raises_a_phase_error(beats: list[float], duration_ms: float) -> None:
    with pytest.raises(MusicalPhaseError, match="duration"):
        build_musical_phase_map(_grid(beats, duration_ms))


def test_inferred_edges_stay_exact() -> None:
    phase_map = build_musical_phase_map(_grid([100, 400, 700], 800))

    assert musical_phase_fraction(phase_map, 0, origin_ms=100, period_beats=1) == Fraction(-1, 3)
    assert musical_phase_fraction(phase_map, 800, origin_ms=100, period_beats=1) == Fraction(7, 3)
    assert musical_phase_fraction(phase_map, 800, origin_ms=0, period_beats=1) == Fraction(8, 3)


def test_time_at_phase_inverts_the_map_exactly() -> None:
    phase_map = build_musical_phase_map(_grid([0, 500, 1000, 2000], 2000))

    assert musical_time_at(phase_map, Fraction(5, 2), origin_ms=0, period_beats=1) == 1500
    assert musical_time_at(phase_map, Fraction(1), origin_ms=750, period_beats=1) == 1500
    assert musical_time_at(phase_map, Fraction(7, 5), origin_ms=0, period_beats=0.5) == 350
    with pytest.raises(MusicalPhaseError, match="domain"):
        musical_time_at(phase_map, Fraction(5), origin_ms=0, period_beats=1)


def test_authored_decimals_are_taken_at_their_decimal_value() -> None:
    phase_map = build_musical_phase_map(_grid([0, 500, 1000], 1000))

    # 0.1 beat is the decimal one tenth, not the nearest binary float.
    assert musical_phase_fraction(phase_map, 50, origin_ms=0, period_beats=0.1) == 1


def test_absurd_period_raises_a_phase_error_not_overflow() -> None:
    phase_map = build_musical_phase_map(_grid([0, 500, 1000], 1000))

    with pytest.raises(MusicalPhaseError):
        musical_phase_at(phase_map, 500, origin_ms=0, period_beats=1e-310)


def test_evaluation_caches_leave_equality_and_copies_alone() -> None:
    """Exact values cached as a map is evaluated are not part of its value: two equal
    maps stay equal once one is evaluated, and a copy with other knots computes afresh
    instead of returning the original's cached phase."""
    grid = _grid([0, 500, 1000, 1500], 1500)
    first, second = build_musical_phase_map(grid), build_musical_phase_map(grid)
    assert musical_phase_fraction(first, 750, origin_ms=0, period_beats=1.0) == Fraction(3, 2)
    assert first == second

    slower = first.model_copy(
        update={
            "knots": tuple(k.model_copy(update={"time_ms": k.time_ms * 2}) for k in first.knots)
        }
    )
    assert slower.knot_times_ms == (0, 1000, 2000, 3000)
    assert musical_phase_fraction(slower, 750, origin_ms=0, period_beats=1.0) == Fraction(3, 4)
    assert musical_phase_fraction(first, 750, origin_ms=0, period_beats=1.0) == Fraction(3, 2)
