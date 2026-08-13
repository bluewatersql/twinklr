"""The shutter emitted-bytes test from P4-F3 [V].

Render one section twice against two otherwise-identical fixture configs — one with
`shutter_channel=6`, one with `shutter_channel=17` — and assert on the *emitted
settings string* rather than on intent. This distinguishes "actively shuttered closed"
from "left to the console", and settles the no-audio/no-light question without needing
physical hardware.

The only fixture configuration tracked in the repository today uses
`shutter_channel=17` (`tests/unit/config/test_fixtures.py`) — i.e. outside the emitted
1-16 window — which is why both arms are required.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from tests.golden.harness import RIGS

if TYPE_CHECKING:
    from collections.abc import Callable

    from tests.golden.harness import RenderResult, RigSpec


def test_shutter_channel_6_is_actively_zeroed(
    render_cached: Callable[[RigSpec], RenderResult],
) -> None:
    """With shutter mapped to channel 6, every emitted effect carries `E_SLIDER_DMX6=0`.

    KNOWN-WRONG PIN (P4-F3). The zero is not a deliberate "close the shutter" command —
    it is the builder zero-filling channels 1..16 (`_calculate_max_channel` rounds up to
    16 and the emit loop writes 0 for anything unchoreographed). Nothing in the render
    path ever sets a shutter value. The emitted byte is nonetheless what the console
    receives: on this rig the show actively holds the shutter closed, so the heads move
    in the dark. P1P-T6 changes this; when it does, this expectation changes with it.
    """
    result = render_cached(RIGS["mh4_shutter_in_window"])
    assert result.effects, "shutter rig rendered no effects"
    for effect in result.effects:
        assert "E_SLIDER_DMX6=0" in effect.settings, f"{effect.header} did not emit E_SLIDER_DMX6=0"


def test_shutter_channel_17_is_not_emitted(
    render_cached: Callable[[RigSpec], RenderResult],
) -> None:
    """With shutter mapped to channel 17, no `E_SLIDER_DMX17` token is emitted at all.

    Channel 17 is above the 16-channel window the builder emits, so the shutter is left
    to whatever the console already holds — the opposite failure mode from the arm
    above, and the reason the two arms disagree on whether the rig lights up.
    """
    result = render_cached(RIGS["mh4_shutter_out_of_window"])
    assert result.effects, "shutter rig rendered no effects"
    for effect in result.effects:
        assert "E_SLIDER_DMX17" not in effect.settings, (
            f"{effect.header} unexpectedly emitted an E_SLIDER_DMX17 token"
        )
        assert "E_CHECKBOX_INVDMX17" not in effect.settings


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
