"""A repeating physical cycle holds whole movement periods in any meter.

Each cycle restarts its steps' motion, so a cycle that ends mid-period would make every
head jump at the boundary. The physical compile stretches such a cycle, with its steps,
to the smallest whole number of bars holding whole periods and every overlay; the gate
and the render share that one compile.
"""

from __future__ import annotations

import pytest

from tests.support.mh_physical import (
    hold_step,
    overlay,
    physical_template_doc,
    sine_step,
    sweep_step,
)
from twinklr.core.sequencer.models.template import Template
from twinklr.core.sequencer.moving_heads.compile.physical import PhysicalCompileError
from twinklr.core.sequencer.moving_heads.compile.preset import apply_preset
from twinklr.core.sequencer.moving_heads.compile.template_compiler import whole_period_cycle
from twinklr.core.sequencer.moving_heads.templates.data_loader import (
    PHYSICAL_TEMPLATE_DIR,
    load_template_document,
)

_PERIODIC = (
    "fly_in_cascade",
    "fly_out_cascade",
    "masked_wheel_flick",
    "mirror_wings",
    "target_orbit",
    "zoom_wave",
)


@pytest.mark.parametrize("template_id", [*_PERIODIC, "finite_snap_hold"])
def test_in_four_four_every_family_and_variant_keeps_its_authored_cycle(template_id: str) -> None:
    document = load_template_document(PHYSICAL_TEMPLATE_DIR / f"{template_id}.json")
    for preset in (None, *document.presets):
        template = apply_preset(document.template, preset) if preset else document.template
        assert whole_period_cycle(template, 4) is template


@pytest.mark.parametrize(
    ("beats_per_bar", "base_bars", "slow_bars"),
    [(3, 4.0, 8.0), (2, 2.0, 4.0), (6, 2.0, 4.0), (5, 4.0, 8.0)],
)
@pytest.mark.parametrize("template_id", ["target_orbit", "mirror_wings", "fly_out_cascade"])
def test_a_cycle_ending_mid_period_grows_to_whole_bars_of_whole_periods(
    template_id: str, beats_per_bar: int, base_bars: float, slow_bars: float
) -> None:
    """2 bars of 3/4 hold 1.5 of the base's 4-beat periods, so the cycle grows to 4 bars
    (12 beats); the slow variant's 8-beat period needs 8 bars (24 beats). In 6/8 the base
    already fits. Every step spanning the cycle spans the grown one."""
    document = load_template_document(PHYSICAL_TEMPLATE_DIR / f"{template_id}.json")
    slow = next(preset for preset in document.presets if preset.preset_id == "slow")
    for template, bars in (
        (document.template, base_bars),
        (apply_preset(document.template, slow), slow_bars),
    ):
        grown = whole_period_cycle(template, beats_per_bar)
        assert grown.repeat.cycle_bars == bars
        if bars == template.repeat.cycle_bars:
            assert grown is template
        for step in grown.steps:
            assert step.timing.base_timing.start_offset_bars == 0.0
            assert step.timing.base_timing.duration_bars == bars


@pytest.mark.parametrize(("beats_per_bar", "bars"), [(4, 2.0), (3, 4.0), (2, 4.0), (6, 2.0)])
def test_a_cycle_ending_before_its_overlay_ends_grows_to_hold_it(
    beats_per_bar: int, bars: float
) -> None:
    """The flick's overlay runs to beat 6 of its cycle. 2 bars of 2/4 end at beat 4, so
    the cycle grows to 4 bars (8 beats: whole 4-beat periods, the overlay inside)."""
    document = load_template_document(PHYSICAL_TEMPLATE_DIR / "masked_wheel_flick.json")
    grown = whole_period_cycle(document.template, beats_per_bar)
    assert grown.repeat.cycle_bars == bars
    assert grown.physical_overlays == document.template.physical_overlays


def test_a_hold_only_cycle_without_overlays_is_never_grown() -> None:
    template = physical_template_doc("p3_still", [hold_step("still", 0.0)]).template
    assert whole_period_cycle(template, 3) is template


def test_a_once_template_is_never_grown() -> None:
    template = physical_template_doc(
        "p3_once", [sweep_step("move", 0.0, 10.0, period_beats=3.0)], mode="ONCE"
    ).template
    assert whole_period_cycle(template, 3) is template


def test_a_cycle_whose_steps_do_not_each_span_it_is_left_as_authored() -> None:
    """Two half-cycle steps: their motion restarts at each step by design, so stretching
    the cycle would change the authored pattern; it is left alone."""
    template = physical_template_doc(
        "p3_halves",
        [
            sine_step("a", 0.0, 10.0, duration=0.5),
            sine_step("b", 0.0, 10.0, start=0.5, duration=0.5),
        ],
    ).template
    assert whole_period_cycle(template, 3) is template


def test_a_cycle_that_would_grow_past_eight_bars_is_refused() -> None:
    """A 4.1-beat period meets whole bars of 4/4 only after 41 bars; the compile refuses
    it, naming the template, the periods and the cycle it would need."""
    template = physical_template_doc(
        "p3_odd", [sine_step("sway", 0.0, 10.0, period_beats=4.1)]
    ).template
    with pytest.raises(PhysicalCompileError, match="p3_odd") as raised:
        whole_period_cycle(template, 4)
    message = str(raised.value)
    assert "4.1" in message and "41 bars" in message


@pytest.mark.parametrize(
    ("cycle_bars", "period_beats", "overlays", "bars"),
    [
        (1.0, 3.0, [], 3.0),
        (0.25, 3.0, [], 3.0),
        (0.25, 4.0, [], 1.0),
        (1.0, 2.5, [], 5.0),
        (1.0, 4.0, [overlay("color", 1.0, 6.0, 1.0, "red")], 2.0),
        (1.0, 32.0, [], 8.0),
        (3.0, 8.0, [], 4.0),
    ],
)
def test_a_cycle_grows_to_the_fewest_whole_bars_up_to_eight(
    cycle_bars: float, period_beats: float, overlays: list[dict[str, object]], bars: float
) -> None:
    """In 4/4: a 3-beat period needs 12 beats (3 bars), from a one-bar or a one-beat
    cycle; a one-beat cycle of a 4-beat period needs one bar; a 2.5-beat period needs 20
    beats; an overlay to beat 6 needs 2 bars; a 32-beat period needs 8 bars, the most a
    cycle grows to; a 3-bar cycle of an 8-beat period grows to 4 bars, never shrinks to 2."""
    step = sine_step("sway", 0.0, 10.0, period_beats=period_beats, duration=cycle_bars)
    template = physical_template_doc(
        "p3_grow", [step], cycle_bars=cycle_bars, overlays=overlays
    ).template
    assert whole_period_cycle(template, 4).repeat.cycle_bars == bars


def test_a_step_starting_after_the_cycle_start_is_left_as_authored() -> None:
    """A one-bar step at offset 0.5 bars in a one-bar cycle of a 3-beat period does not
    span the cycle, so the cycle is not grown."""
    step = sine_step("sway", 0.0, 10.0, period_beats=3.0, start=0.5, duration=1.0)
    template = physical_template_doc("p3_late", [step]).template
    assert whole_period_cycle(template, 4) is template


def test_a_pulse_that_is_not_lit_throughout_counts_like_a_movement_period() -> None:
    """A 3-bar 4/4 cycle (12 beats) of an 8-beat move grows to 4 bars for the move alone;
    with a 6-beat dimmer pulse lit half the time it must hold whole pulses too, so it
    grows to 6 bars (24 beats), where neither restarts. A pulse lit throughout (duty 1,
    as every shipped family's) adds nothing."""

    def template(duty: float) -> Template:
        step = sine_step("sway", 0.0, 10.0, period_beats=8.0, duration=3.0)
        step["dimmer"] = {
            "physical": {"period_beats": 6.0, "duty_cycle": duty, "low": 0.0, "high": 1.0}
        }
        return physical_template_doc("p3_pulse", [step], cycle_bars=3.0).template

    assert whole_period_cycle(template(1.0), 4).repeat.cycle_bars == 4.0
    assert whole_period_cycle(template(0.5), 4).repeat.cycle_bars == 6.0
