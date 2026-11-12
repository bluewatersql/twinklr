"""P4-F9 reverted: the rig's pan/tilt calibration does not bound emitted movement.

P1P-T5 scaled and re-centred every movement curve into the rig's calibrated
pan/tilt window. That collapsed the fan and tilt geometry the templates are built
on, and was reverted on 2026-11-12 at the owner's request. The calibration again
reaches the curve only through the `center_offset` term, which every pattern in
the library leaves at 0.5, so a narrowly calibrated rig emits exactly the movement
a default rig does.

`mh4_narrow_calibration` is the review's worked example (`tilt 110-145, pan
100-150`); these tests pin that it no longer changes the output.
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


@pytest.mark.parametrize("channel", [TILT_CHANNEL, PAN_CHANNEL])
def test_narrow_calibration_emits_the_default_rig_movement(
    channel: int,
    render_cached: Callable[[RigSpec], RenderResult],
) -> None:
    """Every pan/tilt value curve is identical on the narrow and default rigs."""
    narrow = render_cached(NARROW)
    default = render_cached(RIGS["mh4_minimal"])
    assert narrow.effects
    assert [effect.header for effect in narrow.effects] == [
        effect.header for effect in default.effects
    ]

    differing = [
        narrow_effect.header
        for narrow_effect, default_effect in zip(narrow.effects, default.effects, strict=True)
        if _curve_values(narrow_effect.settings, channel=channel)
        != _curve_values(default_effect.settings, channel=channel)
    ]

    assert not differing, f"channel {channel} differs between rigs:\n  " + "\n  ".join(differing)


def test_movement_leaves_the_narrow_window(
    render_cached: Callable[[RigSpec], RenderResult],
) -> None:
    """The calibration is not a bound: tilt runs outside `110-145` on the narrow rig.

    Without this, a plan that happened to stay inside the window would pass the
    equality test above even if the window were being applied.
    """
    values = [
        value * 255.0
        for effect in render_cached(NARROW).effects
        for value in (_curve_values(effect.settings, channel=TILT_CHANNEL) or [])
    ]
    assert values, "no tilt value curves in the render"
    assert min(values) < 110 or max(values) > 145


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
