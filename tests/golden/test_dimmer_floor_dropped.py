"""The dropped dimmer floor from P4-M1, verbatim mechanism.

All 37 templates declare `defaults={"dimmer_floor_dmx": 60, "dimmer_ceiling_dmx":
255}` as an anti-flicker floor, but `Template.defaults` is read exactly once, at
merge time (`compile/preset.py:118`), and never again by any consumer. The dimmer
handler instead reads its clamp from the *fixture calibration*
(`handlers/dimmers/default.py:94-95,103-104`), which this harness's rigs never set,
so `rig.py`'s `dimmer_floor_dmx or 0` evaluates to **0** -- the declared floor of 60
never reaches the clamp.

`build_plan()`'s `breakdown` section renders `circle_asym_left_strobe`, whose dimmer
declares `min_norm=0.05` against the template's own 60-DMX floor, specifically to
make the dropped floor visible: 0.05 normalized is ~13 DMX, well below both the
declared floor (60 DMX / ~0.235 normalized) and even further below where the floor
*should* clamp it.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from tests.golden.harness import RIGS

if TYPE_CHECKING:
    from collections.abc import Callable

    from tests.golden.harness import RenderResult, RigSpec

DECLARED_FLOOR_NORMALIZED = 60 / 255


def test_dimmer_curve_dips_below_the_declared_floor(
    render_cached: Callable[[RigSpec], RenderResult],
) -> None:
    """KNOWN-WRONG PIN (P4-M1): the breakdown section's dimmer curve ignores the 60-DMX floor.

    When P1P-T5 makes `Template.defaults`' floor reach the dimmer handler's clamp,
    this assertion flips (no curve point below `DECLARED_FLOOR_NORMALIZED`) and the
    goldens regenerate.
    """
    result = render_cached(RIGS["mh4_minimal"])
    breakdown_effects = result.for_section("breakdown")
    assert breakdown_effects, "expected the 'breakdown' (floor-declaring) section to render"

    curve = _value_curve(breakdown_effects[0].settings, channel=15)
    points = curve.split("Values=")[1].rstrip("|").split(";")
    values = [float(point.split(":")[1]) for point in points]

    assert min(values) < DECLARED_FLOOR_NORMALIZED, (
        f"dimmer curve minimum {min(values)} no longer dips below the declared floor "
        f"{DECLARED_FLOOR_NORMALIZED:.3f} -- the floor may already be honored; if so, "
        "update this pin rather than the harness"
    )


def _value_curve(settings: str, *, channel: int) -> str:
    token = f"E_VALUECURVE_DMX{channel}="
    for part in settings.split(","):
        if part.startswith(token):
            return part[len(token) :]
    raise AssertionError(f"no value curve for channel {channel} in settings string")
