"""The shutter emitted-bytes test from P4-F3 [V], repaired by P1P-T6.

Render one section twice against two otherwise-identical fixture configs — one with
`shutter_channel=6`, one with `shutter_channel=17` — and assert on the *emitted
settings string* rather than on intent. This distinguishes "actively shuttered closed"
from "left to the console", and settles the no-audio/no-light question without needing
physical hardware.

The only fixture configuration tracked in the repository today uses
`shutter_channel=17` (`tests/unit/config/test_fixtures.py`) — i.e. above the old
floor-16 window — which is why both arms are required. Both arms now emit the
fixture's declared shutter default (255, "usually open") since `get_max_channel`
widens the window to whatever the fixture actually maps.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from tests.golden.harness import RIGS

if TYPE_CHECKING:
    from collections.abc import Callable

    from tests.golden.harness import RenderResult, RigSpec


def test_shutter_channel_6_emits_its_declared_default(
    render_cached: Callable[[RigSpec], RenderResult],
) -> None:
    """REPAIRED (P4-F3, P5-V1, P1P-T6): shutter on channel 6 emits 255, not 0.

    Was the KNOWN-WRONG PIN `test_shutter_channel_6_is_actively_zeroed`. The old zero
    was a zero-fill artefact, not a shutter command — nothing in the render path ever
    set a shutter value, yet the byte the console received held the shutter closed, so
    the heads moved in the dark. An unwritten but mapped shutter now emits the
    fixture's declared default (`shutter_default`, "usually open" = 255) instead.
    """
    result = render_cached(RIGS["mh4_shutter_in_window"])
    assert result.effects, "shutter rig rendered no effects"
    for effect in result.effects:
        assert "E_SLIDER_DMX6=255" in effect.settings, (
            f"{effect.header} did not emit E_SLIDER_DMX6=255"
        )


def test_shutter_channel_17_emits_its_declared_default(
    render_cached: Callable[[RigSpec], RenderResult],
) -> None:
    """REPAIRED (P4-F3, P5-V1, P1P-T6): a shutter above the old floor-16 is visible now.

    Was `test_shutter_channel_17_is_not_emitted`. `get_max_channel` widens the emitted
    window to include every channel the fixture actually maps, regardless of its
    number, so channel 17 now carries the declared default exactly like channel 6 does
    — the two arms no longer disagree on whether the rig lights up.
    """
    result = render_cached(RIGS["mh4_shutter_out_of_window"])
    assert result.effects, "shutter rig rendered no effects"
    for effect in result.effects:
        assert "E_SLIDER_DMX17=255" in effect.settings, (
            f"{effect.header} did not emit E_SLIDER_DMX17=255"
        )
        assert "E_CHECKBOX_INVDMX17=0" in effect.settings


def test_shutter_arms_differ_only_in_the_shutter_mapping(
    render_cached: Callable[[RigSpec], RenderResult],
) -> None:
    """The two arms really are otherwise-identical configs, so the diff is the shutter.

    Both rigs choreograph the same pan/tilt/dimmer channels with the same plan, so their
    value curves must match exactly; only the emitted channel window may differ.
    """
    in_window = render_cached(RIGS["mh4_shutter_in_window"])
    out_of_window = render_cached(RIGS["mh4_shutter_out_of_window"])

    assert [effect.header for effect in in_window.effects] == [
        effect.header for effect in out_of_window.effects
    ]
    for left, right in zip(in_window.effects, out_of_window.effects, strict=True):
        assert _curves(left.settings) == _curves(right.settings)


def _curves(settings: str) -> list[str]:
    return sorted(part for part in settings.split(",") if part.startswith("E_VALUECURVE_DMX"))
