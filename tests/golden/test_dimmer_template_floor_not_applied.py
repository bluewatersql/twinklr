"""P4-M1 reverted: the template's declared dimmer floor is not applied.

All 37 templates declare `defaults={"dimmer_floor_dmx": 60, "dimmer_ceiling_dmx":
255}` as an anti-flicker floor. P1P-T5 made the dimmer handler clamp to it; that
brightened the dim end of most templates and was reverted on 2026-11-12 at the
owner's request. Only the rig calibration bounds the dimmer, and the golden rigs
declare no dimmer floor.

`build_plan()`'s `breakdown` section renders `circle_asym_left_strobe`, whose dimmer
declares `min_norm=0.05` against that 60-DMX floor, specifically to make the
difference visible: 0.05 normalized is ~13 DMX.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from tests.golden.harness import RIGS

if TYPE_CHECKING:
    from collections.abc import Callable

    from tests.golden.harness import RenderResult, RigSpec

DECLARED_FLOOR_DMX = 60
DECLARED_FLOOR_NORMALIZED = DECLARED_FLOOR_DMX / 255
DECLARED_MIN_NORM = 0.05
# Value-curve points are written at 4-decimal resolution (P4-F10).
ROUNDING_TOLERANCE = 0.0001


def test_breakdown_dimmer_curve_dips_below_the_declared_floor(
    render_cached: Callable[[RigSpec], RenderResult],
) -> None:
    """The breakdown dimmer reaches its own `min_norm`, not the template's floor."""
    result = render_cached(RIGS["mh4_minimal"])
    breakdown_effects = result.for_section("breakdown")
    assert breakdown_effects, "expected the 'breakdown' (floor-declaring) section to render"

    for effect in breakdown_effects:
        values = _curve_values(effect.settings, channel=15)
        assert min(values) < DECLARED_FLOOR_NORMALIZED, (
            f"{effect.header}: dimmer minimum {min(values)} was lifted to the declared "
            f"floor {DECLARED_FLOOR_NORMALIZED:.3f}"
        )
        assert abs(min(values) - DECLARED_MIN_NORM) <= ROUNDING_TOLERANCE


def test_the_blackout_section_is_exempt(
    render_cached: Callable[[RigSpec], RenderResult],
) -> None:
    """The blackout section is black. With no floor applied this holds trivially here;
    the floor exemption itself (`DimmerPattern.bypasses_dimmer_floor`, for a rig
    calibration floor) is pinned in the dimmer handler unit tests."""
    result = render_cached(RIGS["mh4_minimal"])
    drop_effects = result.for_section("drop")
    assert drop_effects

    for effect in drop_effects:
        assert "E_SLIDER_DMX15=0" in effect.settings


def _curve_values(settings: str, *, channel: int) -> list[float]:
    values = _curve_values_or_none(settings, channel=channel)
    if values is None:
        raise AssertionError(f"no value curve for channel {channel} in settings string")
    return values


def _curve_values_or_none(settings: str, *, channel: int) -> list[float] | None:
    token = f"E_VALUECURVE_DMX{channel}="
    for part in settings.split(","):
        if part.startswith(token):
            payload = part[len(token) :]
            return [
                float(point.split(":")[1])
                for point in payload.split("Values=")[1].rstrip("|").split(";")
            ]
    return None
