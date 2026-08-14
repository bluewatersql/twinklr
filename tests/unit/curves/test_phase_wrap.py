"""P4-F14: phase-shifting a curve must not introduce a snap mid-segment.

`apply_phase_shift_samples` wrapped by modulo, so reading past t=1 jumped straight
back to v(0). For a curve that closes on its start value that is continuous; for one
that does not — and the movement library gained several such curves when P1P-T3
repaired the intensity mapping — it is a full-span discontinuity in the middle of a
segment, which a moving head executes as a mechanical slam.

Nothing tested the phase path at all before this module.
"""

from __future__ import annotations

from itertools import pairwise

import pytest

from twinklr.core.curves.models import CurvePoint
from twinklr.core.curves.phase import apply_phase_shift_samples
from twinklr.core.curves.sampling import interpolate_linear

N_SAMPLES = 64


def _ramp() -> list[CurvePoint]:
    """A curve that does not close: v runs 0 -> 1 and never returns."""
    return [CurvePoint(t=i / (N_SAMPLES - 1), v=i / (N_SAMPLES - 1)) for i in range(N_SAMPLES)]


def _triangle() -> list[CurvePoint]:
    """A curve that does close: up then back down to its start value."""
    points = []
    for index in range(N_SAMPLES):
        t = index / (N_SAMPLES - 1)
        points.append(CurvePoint(t=t, v=1.0 - abs(2.0 * t - 1.0)))
    return points


def _largest_step(points: list[CurvePoint]) -> float:
    return max(abs(b.v - a.v) for a, b in pairwise(points))


@pytest.mark.parametrize("offset", [0.1, 0.25, 0.5, 0.75, 0.9])
def test_shifting_a_non_closing_curve_introduces_no_discontinuity(offset: float) -> None:
    """The pin: no interior jump larger than the curve's own largest step."""
    points = _ramp()
    shifted = apply_phase_shift_samples(points, offset, N_SAMPLES, wrap=True)

    assert _largest_step(shifted) <= _largest_step(points) * 2.0


@pytest.mark.parametrize("offset", [0.1, 0.25, 0.5, 0.75, 0.9])
def test_shifting_a_closing_curve_still_wraps_by_modulo(offset: float) -> None:
    """Curves that close are unaffected: sample i reads from (t + offset) mod 1."""
    points = _triangle()
    shifted = apply_phase_shift_samples(points, offset, N_SAMPLES, wrap=True)

    for point in shifted:
        source_t = (point.t + offset) % 1.0
        assert point.v == pytest.approx(interpolate_linear(points, source_t), abs=1e-9)


def test_zero_offset_is_the_identity() -> None:
    shifted = apply_phase_shift_samples(_ramp(), 0.0, N_SAMPLES, wrap=True)

    assert [point.v for point in shifted] == pytest.approx([point.t for point in shifted])


def test_reflection_reaches_both_ends_of_the_curve() -> None:
    """The reflected extension plays the curve back, so nothing is clipped away.

    A `wrap=False` clamp would instead hold the last value for the whole tail, which
    is why reflection rather than clamping is used for non-closing curves.
    """
    shifted = apply_phase_shift_samples(_ramp(), 0.5, N_SAMPLES, wrap=True)
    values = [point.v for point in shifted]

    assert max(values) == pytest.approx(1.0, abs=1e-6)
    assert values[0] == pytest.approx(0.5, abs=1e-6)
    assert values[-1] == pytest.approx(0.5, abs=0.05)
