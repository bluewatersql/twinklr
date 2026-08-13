"""The BLACKOUT full-brightness inversion from P4-M2 [V], verbatim mechanism.

`DimmerType.BLACKOUT` declares a single categorical entry at `Intensity.SMOOTH`
(`max_intensity=0`). Any other intensity misses that entry and falls back to
`DEFAULT_DIMMER_PARAMS[Intensity.SMOOTH]` (`max_intensity=128`), discarding the
pattern's own semantics. `_resolve_static_dmx_value` then treats that DMX-range
`max_intensity` as if it were normalized (`int(normalized_value * 255)`), so
`128 * 255` clamps to the ceiling -- **255, full brightness** -- for every preset
except `moderate` (which maps to SMOOTH and is the one arm that is correct today).

`build_plan()`'s `drop` section renders `pop_lock_spotlight_blackout` under the
`energetic` preset specifically to make this visible: ENERGETIC -> DRAMATIC misses
SMOOTH, so today's golden shows the inversion this module pins.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from tests.golden.harness import RIGS

if TYPE_CHECKING:
    from collections.abc import Callable

    from tests.golden.harness import RenderResult, RigSpec


def test_blackout_emits_full_brightness_under_energetic_preset(
    render_cached: Callable[[RigSpec], RenderResult],
) -> None:
    """KNOWN-WRONG PIN (P4-M2): BLACKOUT under a non-MODERATE preset is DMX 255, not 0.

    `pop_lock_spotlight_blackout`'s dimmer is mapped to channel 15 by every rig this
    harness renders. When P1P-T5 fixes the unit bug and the semantics-discarding
    fallback, this assertion inverts to `E_SLIDER_DMX15=0` and the goldens regenerate.
    """
    result = render_cached(RIGS["mh4_minimal"])
    drop_effects = result.for_section("drop")
    assert drop_effects, "expected the 'drop' (blackout) section to render segments"

    for effect in drop_effects:
        assert "E_SLIDER_DMX15=255" in effect.settings, (
            f"{effect.header} did not emit the expected (defective) full-brightness "
            "blackout value E_SLIDER_DMX15=255"
        )
        assert "E_VALUECURVE_DMX15" not in effect.settings, (
            "BLACKOUT's HOLD curve takes the static branch -- a value curve here means "
            "the render path changed and this pin needs re-deriving"
        )
