"""Golden pins over the emitted DMX settings string of a real render.

No mocking: `RenderingPipeline.render()` runs the template compiler, the geometry /
movement / dimmer handlers, the curve generator and `DmxSettingsBuilder` for real. The
absence of `unittest.mock` in this module is deliberate and is itself an acceptance
criterion of P1P-T1.

The committed goldens encode the render's behavior *as it is today*, defects and all,
so that every Lane-R fix in P1P-T3..T6 arrives as a reviewable diff. See the banner at
the top of any golden file for the defect ids visible in the baseline.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from tests.golden.harness import (
    EXPECTED_N_SAMPLES,
    RIGS,
    actual_n_samples,
    assert_or_write_golden,
    golden_path,
    render_golden_text,
    render_rig,
    render_single_section,
)

if TYPE_CHECKING:
    from collections.abc import Callable

    from tests.golden.harness import RenderResult, RigSpec


def test_golden_harness_pins_n_samples() -> None:
    """The goldens were generated at this curve resolution.

    `n_samples` is not settable through `RenderingPipeline`, so the goldens inherit
    `TemplateCompileContext`'s default. Asserting it here turns a silent, repo-wide
    golden churn into one explicit failure that names the cause.
    """
    assert actual_n_samples() == EXPECTED_N_SAMPLES


def test_settings_string_golden(
    rig: RigSpec,
    render_cached: Callable[[RigSpec], RenderResult],
    regen_goldens: bool,
) -> None:
    """Every emitted effect's complete settings string matches its committed golden."""
    result = render_cached(rig)
    sections = result.sections()
    assert sections, f"rig {rig.rig_id} rendered no effects at all"

    for section_id in sections:
        assert_or_write_golden(
            golden_path(rig.rig_id, section_id),
            render_golden_text(result, section_id),
            regen=regen_goldens,
        )


def test_golden_render_is_deterministic(rig: RigSpec) -> None:
    """Two independent renders of the same rig emit byte-identical settings strings."""
    first = render_rig(rig)
    second = render_rig(rig)

    assert [effect.header for effect in first.effects] == [
        effect.header for effect in second.effects
    ]
    assert [effect.settings for effect in first.effects] == [
        effect.settings for effect in second.effects
    ]


def test_every_rendered_section_has_a_golden(
    rig: RigSpec,
    render_cached: Callable[[RigSpec], RenderResult],
) -> None:
    """A newly emitted section cannot slip through without a committed pin."""
    result = render_cached(rig)
    missing = [
        section_id
        for section_id in result.sections()
        if not golden_path(rig.rig_id, section_id).exists()
    ]
    assert not missing, (
        f"rig {rig.rig_id} emitted sections with no golden file: {missing}. "
        "Regenerate with: uv run pytest tests/golden --regen-goldens -q"
    )


def test_plan_sections_and_transition_are_all_covered(
    render_cached: Callable[[RigSpec], RenderResult],
) -> None:
    """A regression that drops a section fails here rather than shipping silently."""
    result = render_cached(RIGS["mh4_minimal"])
    assert result.sections() == [
        "intro",
        "transition_intro_to_chorus",
        "chorus",
        "transition_chorus_to_drop",
        "drop",
        "transition_drop_to_breakdown",
        "breakdown",
        "transition_breakdown_to_one_bar",
        "one_bar",
        "transition_one_bar_to_phrase",
        "phrase",
        "transition_phrase_to_arc",
        "arc",
    ]
    # 4 fixtures x (5 single-step sections + 6 transitions + 3 steps for each of the
    # two narrative sections).
    assert len(result.effects) == 4 * (5 + 6 + 3 + 3)


@pytest.mark.parametrize(
    ("rig_id", "expected_extra_channels"),
    [
        ("mh4_minimal", set()),
        ("mh4_shutter_in_window", {6, 7, 8}),
        ("mh4_shutter_out_of_window", {17, 18}),
    ],
)
def test_shutter_mapping_changes_the_emitted_settings(
    rig_id: str,
    expected_extra_channels: set[int],
    render_cached: Callable[[RigSpec], RenderResult],
) -> None:
    """REPAIRED (P4-F3, P1P-T6): the shutter/colour/gobo mapping now changes what is
    emitted. Was the KNOWN-WRONG PIN `test_shutter_mapping_is_invisible_in_the_emitted_settings`.

    Before this task, all three rigs emitted the identical 16-channel zero-filled set
    regardless of where shutter/colour/gobo were mapped, or whether they were mapped at
    all. Now the emitted window (`get_max_channel`) and each mapped channel's declared
    default both depend on the mapping: pan/tilt/dimmer (11/13/15) are always present,
    unmapped channels never appear, and shutter/colour/gobo appear at their declared
    default whenever the fixture maps them. `test_shutter_channel_emission.py` pins the
    exact values for the shutter arms.
    """
    settings = render_cached(RIGS[rig_id]).effects[0].settings
    emitted = {
        int(part.removeprefix("E_SLIDER_DMX").split("=")[0])
        for part in settings.split(",")
        if part.startswith("E_SLIDER_DMX")
    }
    assert emitted == {11, 13, 15} | expected_extra_channels


@pytest.mark.parametrize("preset_pair", [("chill", "energetic"), ("chill", "intense")])
def test_preset_id_changes_the_movement_curve(preset_pair: tuple[str, str]) -> None:
    """P4-F1 (FIXED in P1P-T3): preset intensity reaches the movement curve.

    This pin used to assert `==`. `DefaultMovementHandler.generate` overwrote its
    `intensity` argument with a lookup in the step's movement params — a dict that
    never carries that key — so the intensity the pipeline derives from `preset_id`
    was discarded and the emitted settings string was byte-identical across presets:
    a planner asking for INTENSE got exactly what CHILL produced.

    `sweep_lr` is the sharpest probe because it declares no `categorical_params` of
    its own and resolves through `DEFAULT_MOVEMENT_PARAMS`, so nothing but the
    intensity plumbing can make these payloads differ.
    """
    low, high = preset_pair
    low_effects = render_single_section(
        RIGS["mh4_minimal"], template_id="sweep_lr_fan_hold", preset_id=low
    )
    high_effects = render_single_section(
        RIGS["mh4_minimal"], template_id="sweep_lr_fan_hold", preset_id=high
    )

    assert [effect.settings for effect in low_effects] != [
        effect.settings for effect in high_effects
    ]


def test_preset_id_does_change_curves_where_the_pattern_declares_intensities() -> None:
    """The same guarantee for a pattern that declares its own per-intensity table.

    `bounce` resolves through its own `categorical_params` rather than through
    `DEFAULT_MOVEMENT_PARAMS`, so this covers the other half of the lookup that
    P1P-T3 repaired — and the P4-F1a fill-in that gave that table all five
    intensities instead of two.
    """
    low_effects = render_single_section(
        RIGS["mh4_minimal"], template_id="bounce_fan_pulse", preset_id="chill"
    )
    high_effects = render_single_section(
        RIGS["mh4_minimal"], template_id="bounce_fan_pulse", preset_id="energetic"
    )

    assert [effect.settings for effect in low_effects] != [
        effect.settings for effect in high_effects
    ]


def test_unmapped_channels_are_omitted_not_zero_filled(
    render_cached: Callable[[RigSpec], RenderResult],
) -> None:
    """REPAIRED (P4-F3, P1P-T6): channels the fixture does not map are omitted.

    Was the KNOWN-WRONG PIN `test_unchoreographed_channels_are_zero_filled`. Only
    pan/tilt/dimmer are mapped on `mh4_minimal` (no shutter/colour/gobo), so
    `get_max_channel` narrows the emitted window to 15 and every channel other than
    11/13/15 is absent from the settings string entirely -- not zero-filled, which on
    a real console used to overwrite channels the show never intended to touch.
    """
    settings = render_cached(RIGS["mh4_minimal"]).effects[0].settings
    for channel in (11, 13, 15):
        assert f"E_SLIDER_DMX{channel}=" in settings
    for channel in range(1, 19):
        if channel in (11, 13, 15):
            continue
        assert f"E_SLIDER_DMX{channel}=" not in settings


def test_value_curve_points_are_four_decimal(
    render_cached: Callable[[RigSpec], RenderResult],
) -> None:
    """REPAIRED (P4-F10, P1P-T6): curve points are written at 4-decimal resolution.

    Was the KNOWN-WRONG PIN `test_value_curve_points_are_two_decimal`. 2-decimal `v`
    was 2.55 DMX steps of quantisation -- a curve could not express a one-step change,
    and repeated values were visible in the goldens. At 4 decimals the resolution is
    ~0.026 DMX steps and, at this curve's `n_samples` grid, no two points collapse
    onto the same value.
    """
    curve = _value_curve(render_cached(RIGS["mh4_minimal"]).effects[0].settings, channel=11)
    points = curve.split("Values=")[1].rstrip("|").split(";")
    assert len(points) == EXPECTED_N_SAMPLES + 1  # 64 samples plus the t=1.0 anchor

    decimals = {
        len(coordinate.split(".")[1]) for point in points for coordinate in point.split(":")
    }
    assert decimals == {4}

    values = [point.split(":")[1] for point in points]
    assert len(set(values)) == len(values), (
        "4-decimal rounding was chosen so distinct DMX levels no longer collapse onto "
        "the same value at this curve's sample grid; if they do again, the resolution "
        "regressed and this pin needs updating."
    )


def test_transition_segments_carry_their_blend(
    render_cached: Callable[[RigSpec], RenderResult],
) -> None:
    """The blend reaches the exporter (was: every transition emitted a blackout).

    `ChannelBlender.create_blended_channel_value` returns a `ChannelValue` carrying
    its blend on the `curve` field, leaving `static_dmx`, `base_dmx` and
    `value_points` unset. `DmxSettingsBuilder._extract_channel_data` read only those
    three, never `curve`, so the entire blend was dropped and the zero-fill wrote 0
    to all sixteen channels: one second of pan, tilt and dimmer slammed to zero at
    every section boundary, on layer 1 where the validator's all-zero check (which
    reads only the first `EffectLayer` per element) could not see it.

    P1P-T6 owns the channel-default policy and is barred from "resolving" this with
    defaults -- a default would make the emitted bytes look plausible while the blend
    was still discarded, which is why this pin is on the value curve itself.
    """
    transitions = render_cached(RIGS["mh4_minimal"]).for_section("transition_intro_to_chorus")
    assert transitions, "expected transition segments at the section boundary"

    for effect in transitions:
        for channel in (11, 13, 15):
            assert f"E_VALUECURVE_DMX{channel}=" in effect.settings, (
                f"{effect.header} dropped the blended curve for channel {channel}"
            )

        # The sliders are legitimately 0 here: the exporter's contract is that
        # E_SLIDER_DMX<n> reads 0 wherever a value curve is present. What used to be
        # wrong is that there were no curves at all, so 0 was the whole message.
        values = [
            float(pair.split(":")[1])
            for pair in _value_curve(effect.settings, channel=13)
            .split("Values=")[1]
            .rstrip("|")
            .split(";")
        ]
        assert max(values) > 0.0, f"{effect.header} blended to a flat zero on tilt"


def test_value_curves_are_emitted_in_channel_order(
    render_cached: Callable[[RigSpec], RenderResult],
) -> None:
    """The settings string must not depend on the order channels were built in.

    The transition compiler collected its channels into a `set[ChannelName]`, which
    iterates in hash order, so the emitted string differed between processes — a
    golden that passed locally and failed in CI under a different PYTHONHASHSEED.
    Invisible until the blend started reaching the exporter at all.
    """
    for effect in render_cached(RIGS["mh4_minimal"]).effects:
        channels = [
            int(part.split("=")[0].removeprefix("E_VALUECURVE_DMX"))
            for part in effect.settings.split(",")
            if part.startswith("E_VALUECURVE_DMX")
        ]
        assert channels == sorted(channels), f"{effect.header} emits curves out of order"


def _value_curve(settings: str, *, channel: int) -> str:
    """Extract the `E_VALUECURVE_DMX<channel>` payload from a settings string."""
    token = f"E_VALUECURVE_DMX{channel}="
    for part in settings.split(","):
        if part.startswith(token):
            return part[len(token) :]
    raise AssertionError(f"no value curve for channel {channel} in settings string")
