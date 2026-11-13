"""Exact musical phase over a song, built from detected beats.

A `MusicalPhaseMap` maps time to a fractional beat index by piecewise-linear
interpolation between knots. Observed beat starts are knots with indexes 0..n-1, kept
verbatim. A `BeatGrid` stores beat starts, not a guaranteed song start or end, so the
map covers `[0, duration_ms]` with labelled boundary knots: one adjacent observed
interval may extend each edge (`adjacent_interval`); anything longer needs a
caller-supplied `explicit` knot. No average tempo is ever inferred.

Phase is computed in exact rational arithmetic, inferred edges included, so phase at an
observed beat is an exact integer. A knot's public `beat_index` is a float for
reporting; the map keeps the exact value.
"""

from __future__ import annotations

import bisect
from fractions import Fraction
from functools import cached_property
from itertools import pairwise
import math
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, PrivateAttr, model_validator

from twinklr.core.sequencer.timing.beat_grid import BeatGrid

PhaseProvenance = Literal["observed", "adjacent_interval", "explicit"]


class MusicalPhaseError(ValueError):
    """The beat grid and boundary knots cannot establish a phase at the requested time."""


class PhaseKnot(BaseModel):
    """A time and the beat index it falls on, with where that pairing came from."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    time_ms: float = Field(allow_inf_nan=False)
    beat_index: float = Field(allow_inf_nan=False)
    provenance: PhaseProvenance


class MusicalPhaseMap(BaseModel):
    """Knots covering `[0, duration_ms]`, strictly increasing in time and beat index."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    knots: tuple[PhaseKnot, ...] = Field(min_length=2)
    duration_ms: float = Field(gt=0, allow_inf_nan=False)
    # Exact beat index per knot: an inferred edge (e.g. -1/3) is not a float.
    _exact_beats: tuple[Fraction, ...] | None = PrivateAttr(default=None)

    @model_validator(mode="after")
    def _validate_knots(self) -> MusicalPhaseMap:
        if self.knots[0].time_ms != 0 or self.knots[-1].time_ms != self.duration_ms:
            raise ValueError(f"knots must span exactly [0, {self.duration_ms}]")
        for earlier, later in pairwise(self.knots):
            if later.time_ms <= earlier.time_ms or later.beat_index <= earlier.beat_index:
                raise ValueError("knots must strictly increase in time and beat index")
        return self

    @cached_property
    def knot_times_ms(self) -> tuple[float, ...]:
        return tuple(knot.time_ms for knot in self.knots)


def build_musical_phase_map(
    grid: BeatGrid, *, boundary_knots: tuple[PhaseKnot, ...] = ()
) -> MusicalPhaseMap:
    """Build the phase domain of `grid` from its detected beats.

    Pass the detected grid, never `BeatGrid.extended_to_duration()`, whose appended
    average-tempo beats would pass as observed.

    Each edge left uncovered by observed beats and `boundary_knots` is extended to time
    0 (head) or `duration_ms` (tail) by the adjacent observed interval, only when that
    edge is no longer than the interval and both of its beats are observed.

    Args:
        grid: Detected beat grid; its beat starts become observed knots.
        boundary_knots: Caller-supplied `explicit` knots before the first or after the
            last observed beat, within `[0, duration_ms]`.

    Returns:
        A phase map covering `[0, grid.duration_ms]`.

    Raises:
        MusicalPhaseError: If observed beats or knots fall outside the domain, an
            explicit knot sits on or between observed beats, phase would not increase,
            or an edge is uncovered and cannot be inferred.
    """
    duration = grid.duration_ms
    if not (math.isfinite(duration) and duration > 0):
        raise MusicalPhaseError(f"the grid's duration must be positive and finite, not {duration}")
    beats = grid.beat_boundaries
    if any(not 0 <= beat <= duration for beat in beats):
        raise MusicalPhaseError(f"observed beats must lie in the domain [0, {duration}]")
    knots = [
        PhaseKnot(time_ms=beat, beat_index=index, provenance="observed")
        for index, beat in enumerate(beats)
    ]

    for knot in boundary_knots:
        if knot.provenance != "explicit":
            raise MusicalPhaseError(f"boundary knot at {knot.time_ms} ms must be explicit")
        if not 0 <= knot.time_ms <= duration:
            raise MusicalPhaseError(
                f"boundary knot at {knot.time_ms} ms lies outside the domain [0, {duration}]"
            )
        if beats and beats[0] <= knot.time_ms <= beats[-1]:
            raise MusicalPhaseError(
                f"boundary knot at {knot.time_ms} ms would overwrite the observed beats "
                f"spanning [{beats[0]}, {beats[-1]}]"
            )
    knots = sorted([*knots, *boundary_knots], key=lambda knot: knot.time_ms)
    for earlier, later in pairwise(knots):
        if later.time_ms <= earlier.time_ms or later.beat_index <= earlier.beat_index:
            raise MusicalPhaseError(
                f"knots at {earlier.time_ms} and {later.time_ms} ms are not strictly "
                "monotonic in time and beat index"
            )

    exact = [Fraction(knot.beat_index) for knot in knots]
    if not knots or knots[0].time_ms > 0:
        knot, beat_index = _adjacent_knot(knots, exact, edge="head", target_ms=0.0)
        knots.insert(0, knot)
        exact.insert(0, beat_index)
    if knots[-1].time_ms < duration:
        knot, beat_index = _adjacent_knot(knots, exact, edge="tail", target_ms=duration)
        knots.append(knot)
        exact.append(beat_index)
    try:
        phase_map = MusicalPhaseMap(knots=tuple(knots), duration_ms=duration)
    except ValueError as error:
        raise MusicalPhaseError(str(error)) from error
    phase_map._exact_beats = tuple(exact)
    return phase_map


def _adjacent_knot(
    knots: list[PhaseKnot],
    exact: list[Fraction],
    *,
    edge: Literal["head", "tail"],
    target_ms: float,
) -> tuple[PhaseKnot, Fraction]:
    pair = knots[:2] if edge == "head" else knots[-2:]
    if len(pair) < 2 or any(knot.provenance != "observed" for knot in pair):
        raise MusicalPhaseError(
            f"the {edge} up to {target_ms} ms is uncovered and has no adjacent observed "
            "interval; supply explicit boundary knots"
        )
    first, second = pair
    interval = Fraction(second.time_ms) - Fraction(first.time_ms)
    anchor_time, anchor_beat = (
        (first.time_ms, exact[0]) if edge == "head" else (second.time_ms, exact[-1])
    )
    gap = Fraction(target_ms) - Fraction(anchor_time)
    if abs(gap) > interval:
        raise MusicalPhaseError(
            f"the {edge} gap of {float(abs(gap))} ms exceeds the adjacent observed interval "
            f"of {float(interval)} ms; supply explicit boundary knots"
        )
    beat_index = anchor_beat + gap / interval
    knot = PhaseKnot(
        time_ms=target_ms, beat_index=float(beat_index), provenance="adjacent_interval"
    )
    return knot, beat_index


def exact_decimal(value: float) -> Fraction:
    """An authored decimal (a period, duty or phase shift) as the exact value it spells.

    `0.1` is one tenth, not the nearest binary float.
    """
    return Fraction(repr(value))


def musical_phase_fraction(
    phase_map: MusicalPhaseMap, time_ms: float, *, origin_ms: float, period_beats: float
) -> Fraction:
    """Exact unwrapped cycles of `period_beats` elapsed from `origin_ms` to `time_ms`.

    Negative before the origin. At observed beats with an observed origin and a
    whole-beat period, the result is an integer. `period_beats` is taken at its
    decimal value (`exact_decimal`).

    Raises:
        MusicalPhaseError: If either time lies outside `[0, duration_ms]`.
        ValueError: If `period_beats` is not a positive finite number.
    """
    period = _period(period_beats)
    return (_beat_index(phase_map, time_ms) - _beat_index(phase_map, origin_ms)) / period


def musical_phase_at(
    phase_map: MusicalPhaseMap, time_ms: float, *, origin_ms: float, period_beats: float
) -> float:
    """`musical_phase_fraction` as a float.

    Raises:
        MusicalPhaseError: If either time lies outside `[0, duration_ms]`, or the phase
            is too large to represent.
        ValueError: If `period_beats` is not a positive finite number.
    """
    phase = musical_phase_fraction(
        phase_map, time_ms, origin_ms=origin_ms, period_beats=period_beats
    )
    try:
        return float(phase)
    except OverflowError as error:
        raise MusicalPhaseError(
            f"phase at {time_ms} ms over a {period_beats}-beat period is too large"
        ) from error


def musical_time_at(
    phase_map: MusicalPhaseMap, cycles: Fraction, *, origin_ms: float, period_beats: float
) -> Fraction:
    """The exact time at which `cycles` periods have elapsed from `origin_ms`.

    The inverse of `musical_phase_fraction`.

    Raises:
        MusicalPhaseError: If the origin or the resulting time lies outside the domain.
        ValueError: If `period_beats` is not a positive finite number.
    """
    target = _beat_index(phase_map, origin_ms) + cycles * _period(period_beats)
    beats = _knot_beats(phase_map)
    if not beats[0] <= target <= beats[-1]:
        raise MusicalPhaseError(
            f"{float(cycles)} cycles from {origin_ms} ms lie outside the phase domain "
            f"[0, {phase_map.duration_ms}]"
        )
    index = bisect.bisect_right(beats, target) - 1
    left_time = Fraction(phase_map.knots[index].time_ms)
    if beats[index] == target:
        return left_time
    right_time = Fraction(phase_map.knots[index + 1].time_ms)
    return left_time + (target - beats[index]) * (right_time - left_time) / (
        beats[index + 1] - beats[index]
    )


def _period(period_beats: float) -> Fraction:
    if not (math.isfinite(period_beats) and period_beats > 0):
        raise ValueError(f"period_beats must be positive and finite, not {period_beats}")
    return exact_decimal(period_beats)


def _knot_beats(phase_map: MusicalPhaseMap) -> tuple[Fraction, ...]:
    if phase_map._exact_beats is None:
        phase_map._exact_beats = tuple(Fraction(knot.beat_index) for knot in phase_map.knots)
    return phase_map._exact_beats


def _beat_index(phase_map: MusicalPhaseMap, time_ms: float) -> Fraction:
    if not 0 <= time_ms <= phase_map.duration_ms:
        raise MusicalPhaseError(
            f"{time_ms} ms lies outside the phase domain [0, {phase_map.duration_ms}]"
        )
    knots = phase_map.knots
    beats = _knot_beats(phase_map)
    index = bisect.bisect_right(phase_map.knot_times_ms, time_ms) - 1
    if knots[index].time_ms == time_ms:
        return beats[index]
    t0, t1 = Fraction(knots[index].time_ms), Fraction(knots[index + 1].time_ms)
    b0, b1 = beats[index], beats[index + 1]
    return b0 + (Fraction(time_ms) - t0) * (b1 - b0) / (t1 - t0)
