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
    ]
    assert len(result.effects) == 28  # 4 fixtures x (4 sections + 3 transitions)


@pytest.mark.parametrize(
    "rig_id", ["mh4_minimal", "mh4_shutter_in_window", "mh4_shutter_out_of_window"]
)
def test_shutter_mapping_is_invisible_in_the_emitted_settings(
    rig_id: str,
    render_cached: Callable[[RigSpec], RenderResult],
) -> None:
    """KNOWN-WRONG PIN (P4-F3): the shutter mapping does not change what is emitted.

    All three rigs emit the identical set of `E_SLIDER_DMX` tokens — channels 1..16,
    zero-filled — whether the shutter is mapped to channel 6, to channel 17, or not at
    all. Nothing in the render path consults `shutter_channel`, so the byte on channel 6
    is a zero-fill artefact rather than a shutter command, and a shutter above 16 is
    never addressed. `test_shutter_channel_emission.py` pins the consequences of that
    for each arm.
    """
    settings = render_cached(RIGS[rig_id]).effects[0].settings
    emitted = {part.split("=")[0] for part in settings.split(",") if part.startswith("E_SLIDER_")}
    assert emitted == {f"E_SLIDER_DMX{channel}" for channel in range(1, 17)}


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


def test_unchoreographed_channels_are_zero_filled(
    render_cached: Callable[[RigSpec], RenderResult],
) -> None:
    """KNOWN-WRONG PIN (P4-F3): channels 1..16 are always emitted, zero-filled.

    Only pan/tilt/dimmer are choreographed, yet the builder emits an
    `E_SLIDER_DMX<n>` for every channel up to 16. On a real console that overwrites
    channels the show never intended to touch. Recorded, not fixed, by P1P-T1.
    """
    settings = render_cached(RIGS["mh4_minimal"]).effects[0].settings
    for channel in range(1, 17):
        assert f"E_SLIDER_DMX{channel}=" in settings
    unchoreographed = [channel for channel in range(1, 17) if channel not in {11, 13, 15}]
    for channel in unchoreographed:
        assert f"E_SLIDER_DMX{channel}=0" in settings


def test_value_curve_points_are_two_decimal(
    render_cached: Callable[[RigSpec], RenderResult],
) -> None:
    """KNOWN-WRONG PIN (P4-F10): curve points are written at 2-decimal resolution.

    `_curve_points_to_xlights_string` rounds both time and value to two decimals, so a
    255-step DMX range is emitted through 101 distinct levels — a curve cannot express a
    one-step change, and the quantisation is visible as repeated values in the goldens.
    Pinned so the resolution fix is a reviewable diff rather than whole-file churn of
    unclear origin.
    """
    curve = _value_curve(render_cached(RIGS["mh4_minimal"]).effects[0].settings, channel=11)
    points = curve.split("Values=")[1].rstrip("|").split(";")
    assert len(points) == EXPECTED_N_SAMPLES + 1  # 64 samples plus the t=1.0 anchor

    decimals = {
        len(coordinate.split(".")[1]) for point in points for coordinate in point.split(":")
    }
    assert decimals == {2}

    values = [point.split(":")[1] for point in points]
    assert len(set(values)) < len(values), (
        "2-decimal rounding used to collapse distinct DMX levels onto the same value; "
        "if it no longer does, the curve resolution changed and this pin needs updating."
    )


def test_transition_segments_emit_all_zero(
    render_cached: Callable[[RigSpec], RenderResult],
) -> None:
    """KNOWN-WRONG PIN (not previously catalogued): transitions emit a full blackout.

    `ChannelBlender.create_blended_channel_value` returns a `ChannelValue` carrying its
    blend on the `curve` field, leaving `static_dmx`, `base_dmx` and `value_points`
    unset. `DmxSettingsBuilder._extract_channel_data` reads only those three, never
    `curve`, so the entire blend is dropped and the zero-fill writes 0 to all sixteen
    channels. Every section boundary therefore emits one second of pan, tilt and dimmer
    slammed to zero on layer 1.

    The existing validator's all-zero CRITICAL check does not catch this: it reads only
    the first `EffectLayer` per element, and transitions are placed on layer 1.
    """
    transitions = render_cached(RIGS["mh4_minimal"]).for_section("transition_intro_to_chorus")
    assert transitions, "expected transition segments at the section boundary"

    for effect in transitions:
        assert "E_VALUECURVE_DMX" not in effect.settings, (
            f"{effect.header} now emits a value curve — the blend reaches the exporter, "
            "so this pin should be replaced by an assertion on the blended curve."
        )
        sliders = {
            part.split("=")[1]
            for part in effect.settings.split(",")
            if part.startswith("E_SLIDER_")
        }
        assert sliders == {"0"}


def _value_curve(settings: str, *, channel: int) -> str:
    """Extract the `E_VALUECURVE_DMX<channel>` payload from a settings string."""
    token = f"E_VALUECURVE_DMX{channel}="
    for part in settings.split(","):
        if part.startswith(token):
            return part[len(token) :]
    raise AssertionError(f"no value curve for channel {channel} in settings string")
