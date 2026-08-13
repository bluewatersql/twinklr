"""Movement curve wrappers: what sets excursion, and what happens at t=1.0.

These pin P4-M6 and P4-M5 at the seam where they are observable. The handler
applies its own amplitude scaling downstream, which masks both defects when you
measure at the handler's output — so the discriminating assertions belong here,
on `_movement_post_process`'s own result.
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
class TestExcursionIsAmplitudesJob:
    """P4-M6: frequency sets the rate, amplitude sets how far the head travels."""

    def test_lowering_frequency_does_not_widen_the_swing(self, generate) -> None:
        """The inversion, stated directly.

        `center_curve` used to rescale each sampled window to full range. A window
        holding less than a whole oscillation has a narrower observed min/max, so
        stretching it back out made a *slower* movement a *wider* one — and because
        low intensities are paired with low frequencies, SLOW swung widest. Before
        the fix every span below was 1.0 regardless of frequency.
        """
        narrow = span(generate(64, cycles=1.0, frequency=0.25, amplitude=1.0))
        full = span(generate(64, cycles=1.0, frequency=1.0, amplitude=1.0))
        faster = span(generate(64, cycles=1.0, frequency=2.0, amplitude=1.0))

        assert narrow < full
        assert full == pytest.approx(faster)

    def test_amplitude_survives_centering(self, generate) -> None:
        """Rescale-to-full-range erased the amplitude it was handed; translation keeps it."""
        spans = [
            span(generate(64, cycles=1.0, frequency=1.0, amplitude=amplitude))
            for amplitude in (0.25, 0.5, 1.0)
        ]
        assert spans == sorted(spans)
        assert spans[0] < spans[-1]
        assert spans[0] == pytest.approx(0.25, abs=0.01)


@pytest.mark.parametrize("generate", GENERATORS, ids=lambda g: g.__name__)
@pytest.mark.parametrize("frequency", [0.25, 0.6, 1.0, 1.5, 3.0])
def test_no_terminal_snapback(generate, frequency: float) -> None:
    """P4-M5: the final sample interval is never the largest one in the curve.

    Samples land on [0, 1), so the t=1.0 anchor decides the last step. Carrying the
    start value there — the old behavior — made every curve whose window does not
    close on a whole oscillation end with a full-excursion snap in the final 1/n.
    """
    points = generate(64, cycles=1.0, frequency=frequency, amplitude=1.0)
    assert points[-1].t == pytest.approx(1.0)

    deltas = [abs(points[i + 1].v - points[i].v) for i in range(len(points) - 1)]
    assert deltas[-1] <= max(deltas[:-1]) + 1e-9
