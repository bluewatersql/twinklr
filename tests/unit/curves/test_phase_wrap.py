"""`apply_phase_shift_samples` wraps by modulo.

P1P-T3 (P4-F14) extended curves that do not close on their start value by
reflection rather than modulo. That was reverted on 2026-11-12 at the owner's
request: every curve, closing or not, is wrapped by modulo again, so reading past
t=1 returns to v(0). For a non-closing curve that is a jump mid-segment, and it is
the accepted look.
"""

from __future__ import annotations

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


@pytest.mark.parametrize("make_curve", [_ramp, _triangle], ids=["non_closing", "closing"])
@pytest.mark.parametrize("offset", [0.1, 0.25, 0.5, 0.75, 0.9])
def test_shift_wraps_by_modulo(make_curve, offset: float) -> None:
    """Sample i reads from (t + offset) mod 1, whether or not the curve closes."""
    points = make_curve()
    shifted = apply_phase_shift_samples(points, offset, N_SAMPLES, wrap=True)

    for point in shifted:
        source_t = (point.t + offset) % 1.0
        assert point.v == pytest.approx(interpolate_linear(points, source_t), abs=1e-9)


def test_zero_offset_is_the_identity() -> None:
    shifted = apply_phase_shift_samples(_ramp(), 0.0, N_SAMPLES, wrap=True)

    assert [point.v for point in shifted] == pytest.approx([point.t for point in shifted])
