"""Movement curve wrappers: what sets excursion, and what happens at t=1.0.

`_movement_post_process` rescales each curve to the full [0, 1] range
(`center_curve`) and closes it on its start value (`loop_mode="append"`). P1P-T3
replaced both (P4-M6 translation, P4-M5 "extend"); both were reverted on
2026-11-12 at the owner's request, to restore the look accepted in xLights. The
handler applies its own amplitude scaling downstream, so these are pinned here,
on the wrapper's own result.
"""

from __future__ import annotations

import pytest

from twinklr.core.curves.functions.movement import (
    generate_movement_sine,
    generate_movement_triangle,
)
from twinklr.core.curves.models import CurvePoint

GENERATORS = [generate_movement_sine, generate_movement_triangle]


def span(points: list[CurvePoint]) -> float:
    values = [p.v for p in points]
    return max(values) - min(values)


@pytest.mark.parametrize("generate", GENERATORS, ids=lambda g: g.__name__)
class TestCenteringRescalesToFullRange:
    """P4-M6 reverted: every curve spans [0, 1] whatever its frequency or amplitude."""

    def test_span_is_full_range_at_every_frequency(self, generate) -> None:
        spans = [
            span(generate(64, cycles=1.0, frequency=frequency, amplitude=1.0))
            for frequency in (0.25, 1.0, 2.0)
        ]
        assert spans == pytest.approx([1.0, 1.0, 1.0])

    def test_span_is_full_range_at_every_amplitude(self, generate) -> None:
        spans = [
            span(generate(64, cycles=1.0, frequency=1.0, amplitude=amplitude))
            for amplitude in (0.25, 0.5, 1.0)
        ]
        assert spans == pytest.approx([1.0, 1.0, 1.0])


@pytest.mark.parametrize("generate", GENERATORS, ids=lambda g: g.__name__)
@pytest.mark.parametrize("frequency", [0.25, 0.6, 1.0, 1.5, 3.0])
def test_curve_closes_on_its_start_value(generate, frequency: float) -> None:
    """P4-M5 reverted: the t=1.0 anchor carries the start value ("append")."""
    points = generate(64, cycles=1.0, frequency=frequency, amplitude=1.0)

    assert points[-1].t == pytest.approx(1.0)
    assert points[-1].v == pytest.approx(points[0].v)
