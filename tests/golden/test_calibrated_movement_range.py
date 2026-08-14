"""P4-F9: the fixture calibration bounds the emitted DMX.

The worked example from the review, as a test. A fixture calibrated to
`tilt_min_dmx=110, tilt_max_dmx=145` — a narrow, physically-safe tilt window — with
a base tilt at the centre of that window and `Intensity.SMOOTH` used to emit
normalized [0.30, 0.70], i.e. DMX 76-179: more than four times the calibrated span,
in both directions. On a real moving head that is mechanical-limit exposure.

The calibration was read (`handlers/movement/default.py` computed a max safe
amplitude from it) but reached the curve only through `center_offset`, which every
pattern in the library leaves at its 0.5 default, so the term was identically zero
and the calibration had no effect on emitted DMX by any route.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from tests.golden.harness import RIGS

if TYPE_CHECKING:
    from collections.abc import Callable

    from tests.golden.harness import RenderResult, RigSpec

NARROW = RIGS["mh4_narrow_calibration"]
TILT_CHANNEL = 13
PAN_CHANNEL = 11


@pytest.mark.parametrize(
    ("channel", "dmx_min", "dmx_max"),
    [(TILT_CHANNEL, 110, 145), (PAN_CHANNEL, 100, 150)],
)
def test_emitted_movement_stays_within_the_calibrated_range(
    channel: int,
    dmx_min: int,
    dmx_max: int,
    render_cached: Callable[[RigSpec], RenderResult],
) -> None:
    """Every emitted point on a calibrated axis, across the whole plan."""
    result = render_cached(NARROW)
    assert result.effects

    out_of_range: list[str] = []
    for effect in result.effects:
        values = _curve_values(effect.settings, channel=channel)
        if values is None:
            continue
        emitted = [value * 255.0 for value in values]
        # The exporter writes value-curve points at 2-decimal resolution (P4-F10),
        # which is worth ~1.3 DMX; the tolerance is that quantisation, not slack.
        if min(emitted) < dmx_min - 1.5 or max(emitted) > dmx_max + 1.5:
            out_of_range.append(f"{effect.header}: DMX {min(emitted):.1f}..{max(emitted):.1f}")

    assert not out_of_range, (
        f"channel {channel} left its calibrated range [{dmx_min}, {dmx_max}]:\n  "
        + "\n  ".join(out_of_range)
    )


def test_the_narrow_window_actually_narrows_the_output(
    render_cached: Callable[[RigSpec], RenderResult],
) -> None:
    """The bound is doing work: the same plan on the default calibration goes wider.

    Without this, a renderer that emitted a constant would pass the range test.
    """
    narrow = _tilt_span(render_cached(NARROW))
    default = _tilt_span(render_cached(RIGS["mh4_minimal"]))

    assert narrow > 0.0, "the narrow rig emitted no tilt movement at all"
    assert narrow < default


def _tilt_span(result: RenderResult) -> float:
    values = [
        value
        for effect in result.effects
        for value in (_curve_values(effect.settings, channel=TILT_CHANNEL) or [])
    ]
    assert values, "no tilt value curves in the render"
    return max(values) - min(values)


def _curve_values(settings: str, *, channel: int) -> list[float] | None:
    token = f"E_VALUECURVE_DMX{channel}="
    for part in settings.split(","):
        if part.startswith(token):
            payload = part[len(token) :]
            return [
                float(point.split(":")[1])
                for point in payload.split("Values=")[1].rstrip("|").split(";")
            ]
    return None
