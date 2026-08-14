"""P4-M1 repaired: the template's declared dimmer floor bounds the emitted curve.

All 37 templates declare `defaults={"dimmer_floor_dmx": 60, "dimmer_ceiling_dmx":
255}` as an anti-flicker floor. `Template.defaults` was read exactly once, at preset
merge time, and never again by any consumer; the dimmer handler took its clamp from
the *fixture calibration*, which the shipped path builds without a floor, so the
effective floor was 0 and dimmers were driven fully to black.

`build_plan()`'s `breakdown` section renders `circle_asym_left_strobe`, whose dimmer
declares `min_norm=0.05` against that 60-DMX floor, specifically to make the
difference visible: 0.05 normalized is ~13 DMX.

This module used to assert the dip below the floor; it now asserts the floor holds.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from tests.golden.harness import RIGS

if TYPE_CHECKING:
    from collections.abc import Callable

    from tests.golden.harness import RenderResult, RigSpec

DECLARED_FLOOR_DMX = 60
DECLARED_FLOOR_NORMALIZED = DECLARED_FLOOR_DMX / 255
# Value-curve points are written at 2-decimal resolution (P4-F10), worth ~1.3 DMX.
ROUNDING_TOLERANCE = 0.005


def test_breakdown_dimmer_curve_stays_at_or_above_the_declared_floor(
    render_cached: Callable[[RigSpec], RenderResult],
) -> None:
    result = render_cached(RIGS["mh4_minimal"])
    breakdown_effects = result.for_section("breakdown")
    assert breakdown_effects, "expected the 'breakdown' (floor-declaring) section to render"

    for effect in breakdown_effects:
        values = _curve_values(effect.settings, channel=15)
        assert min(values) >= DECLARED_FLOOR_NORMALIZED - ROUNDING_TOLERANCE, (
            f"{effect.header}: dimmer minimum {min(values)} is below the declared "
            f"floor {DECLARED_FLOOR_NORMALIZED:.3f}"
        )


def test_no_non_blackout_section_dips_below_the_floor(
    render_cached: Callable[[RigSpec], RenderResult],
) -> None:
    """Every section of the plan except the blackout, which is exempt by design."""
    result = render_cached(RIGS["mh4_minimal"])

    below: list[str] = []
    for effect in result.effects:
        if effect.step_id == "transition" or effect.section_id == "drop":
            continue
        values = _curve_values_or_none(effect.settings, channel=15)
        if values is None:
            continue
        if min(values) < DECLARED_FLOOR_NORMALIZED - ROUNDING_TOLERANCE:
            below.append(f"{effect.header}: min {min(values)}")

    assert not below, "dimmer curves below the declared 60-DMX floor:\n  " + "\n  ".join(below)


def test_the_blackout_section_is_exempt(
    render_cached: Callable[[RigSpec], RenderResult],
) -> None:
    """The exemption is explicit (`DimmerPattern.bypasses_dimmer_floor`), not luck:
    a blackout held at the anti-flicker floor would sit at 60 DMX, not black."""
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
