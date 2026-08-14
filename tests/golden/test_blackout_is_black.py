"""P4-M2 repaired: BLACKOUT emits DMX 0 under every preset.

Two bugs composed into a plan-triggerable inversion on exactly the templates a
planner picks for drops. `DimmerType.BLACKOUT` declares a single categorical entry
at `Intensity.SMOOTH` (`max_intensity=0`); any other intensity missed it and fell
back to `DEFAULT_DIMMER_PARAMS[Intensity.SMOOTH]` (`max_intensity=128`), discarding
the pattern's own semantics. `_resolve_static_dmx_value` then treated that DMX-range
value as normalized (`int(normalized_value * 255)`), so `128 * 255` clamped to the
ceiling -- **255, full brightness** -- for every preset except `moderate`.

`build_plan()`'s `drop` section renders `pop_lock_spotlight_blackout` under
`energetic` precisely because ENERGETIC -> DRAMATIC misses the SMOOTH entry. This
module used to assert the inversion; P1P-T5 fixed both halves and it now asserts
the blackout.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from tests.golden.harness import RIGS, render_single_section

if TYPE_CHECKING:
    from collections.abc import Callable

    from tests.golden.harness import RenderResult, RigSpec

BLACKOUT_TEMPLATES = ["pop_lock_spotlight_blackout", "spiral_xross_blackout"]
PRESETS = ["chill", "moderate", "energetic", "intense"]


def test_blackout_section_emits_zero_on_the_dimmer_channel(
    render_cached: Callable[[RigSpec], RenderResult],
) -> None:
    """The plan's `drop` section, on the rig the goldens pin."""
    result = render_cached(RIGS["mh4_minimal"])
    drop_effects = result.for_section("drop")
    assert drop_effects, "expected the 'drop' (blackout) section to render segments"

    for effect in drop_effects:
        assert "E_SLIDER_DMX15=0" in effect.settings, (
            f"{effect.header} does not emit a blackout on the dimmer channel"
        )
        assert "E_VALUECURVE_DMX15" not in effect.settings, (
            "BLACKOUT's HOLD curve takes the static branch -- a value curve here means "
            "the render path changed and this pin needs re-deriving"
        )


@pytest.mark.parametrize("template_id", BLACKOUT_TEMPLATES)
@pytest.mark.parametrize("preset_id", PRESETS)
def test_blackout_is_zero_under_all_presets(template_id: str, preset_id: str) -> None:
    """All four presets, both blackout templates: 255 for three of four before.

    Their `recommended_sections` are `drop`/`peak` and `drop`/`breakdown`, so the
    planner selects them exactly where a blackout is the intent -- and used to get
    the maximum-visibility opposite.
    """
    effects = render_single_section(
        RIGS["mh4_minimal"], template_id=template_id, preset_id=preset_id
    )
    assert effects

    for effect in effects:
        assert "E_SLIDER_DMX15=0" in effect.settings, (
            f"{template_id} under '{preset_id}': {effect.header} is not black"
        )


def test_a_hold_template_still_reaches_full_brightness() -> None:
    """The unit fix changes HOLD's arithmetic (255*255 clamped, now 255 direct) even
    though its output is unchanged; a render-level check that it did not break."""
    effects = render_single_section(
        RIGS["mh4_minimal"], template_id="sweep_lr_fan_hold", preset_id="moderate"
    )

    assert effects
    for effect in effects:
        assert "E_SLIDER_DMX15=255" in effect.settings
