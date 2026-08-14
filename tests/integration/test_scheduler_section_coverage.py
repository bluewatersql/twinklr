"""Every section of a plan renders, and no section renders past its end.

These are the end-to-end counterparts to `tests/unit/.../test_scheduler.py`: they
run the real pipeline, so they cover the scheduler, the boundary clip and the
exporter together. Before P1P-T5 a 1-bar section emitted nothing for all 37
templates and a 3-bar section emitted nothing for 35 of them, with no exception and
no surfaced warning — the CLI reported a successful render of a dark show.
"""

from __future__ import annotations

import pytest

from tests.golden.harness import RIGS, render_single_section
from twinklr.core.sequencer.moving_heads.templates import (
    list_templates,
    load_builtin_templates,
)


def _template_ids() -> list[str]:
    load_builtin_templates()
    return sorted(info.template_id for info in list_templates())


TEMPLATE_IDS = _template_ids()


@pytest.mark.parametrize("template_id", TEMPLATE_IDS)
def test_one_bar_section_renders(template_id: str) -> None:
    """The smallest cycle in the library is 2 bars, so this used to be silence for
    every template without exception."""
    effects = render_single_section(
        RIGS["mh4_minimal"], template_id=template_id, preset_id="moderate", bars=1
    )

    assert effects, f"{template_id} rendered nothing for a 1-bar section"


@pytest.mark.parametrize("template_id", TEMPLATE_IDS)
def test_three_bar_section_renders(template_id: str) -> None:
    """35 of the 37 templates have a cycle of 4 bars or more."""
    effects = render_single_section(
        RIGS["mh4_minimal"], template_id=template_id, preset_id="moderate", bars=3
    )

    assert effects, f"{template_id} rendered nothing for a 3-bar section"


@pytest.mark.parametrize("template_id", TEMPLATE_IDS)
def test_schedule_never_exceeds_the_section(template_id: str) -> None:
    """P4-F6, for every template rather than only the one known to overrun.

    `split_lr_sweep_counter` scheduled two 4-bar steps per 4-bar cycle end to end, so
    a 16-bar section ran 16 bars past its own end. Its `HOLD_LAST_POSE` remainder
    policy meant the clip never ran, and nothing else checked.
    """
    bars = 16
    effects = render_single_section(
        RIGS["mh4_minimal"], template_id=template_id, preset_id="moderate", bars=bars
    )
    assert effects

    # 120 BPM, 4 beats per bar => 2000 ms per bar, first downbeat at 0 ms.
    section_end_ms = bars * 2000
    overrunning = [effect.header for effect in effects if effect.t1_ms > section_end_ms]
    assert not overrunning, (
        f"{template_id} emitted effects past the section end ({section_end_ms} ms): {overrunning}"
    )


def test_short_section_truncates_rather_than_compresses() -> None:
    """The head of the cycle at its nominal rate, not the whole cycle squeezed in.

    A 4-bar pattern crushed into 1 bar plays at 4x speed — the time-compression
    defect P4-F7 documents for remainders. The truncated curve therefore has about a
    quarter of the points of the full one, and starts with the same values.
    """
    full = render_single_section(
        RIGS["mh4_minimal"], template_id="sweep_lr_fan_hold", preset_id="moderate", bars=4
    )
    short = render_single_section(
        RIGS["mh4_minimal"], template_id="sweep_lr_fan_hold", preset_id="moderate", bars=1
    )

    full_values = _curve_values(full[0].settings, channel=11)
    short_values = _curve_values(short[0].settings, channel=11)

    assert 2 <= len(short_values) <= len(full_values) // 3
    assert short_values[0] == full_values[0]


@pytest.mark.parametrize(
    ("template_id", "bars", "expected_steps"),
    [
        ("build_drop_recover", 6, {"build", "drop", "recover"}),
        ("intro_main_outro_phrase", 8, {"intro", "main", "outro"}),
    ],
)
def test_narrative_templates_render_all_steps(
    template_id: str, bars: int, expected_steps: set[str]
) -> None:
    """P4-F5: both templates looped only their middle step."""
    effects = render_single_section(
        RIGS["mh4_minimal"], template_id=template_id, preset_id="moderate", bars=bars
    )

    assert {effect.step_id for effect in effects} == expected_steps


@pytest.mark.parametrize(
    ("template_id", "bars"), [("build_drop_recover", 6), ("intro_main_outro_phrase", 8)]
)
def test_narrative_templates_emit_a_fade_in_and_a_fade_out(template_id: str, bars: int) -> None:
    """The point of both templates: they shape their own entry and exit.

    FADE_IN rises across its step and FADE_OUT falls across its own; with only the
    middle step scheduled, neither curve existed anywhere in the output.
    """
    effects = render_single_section(
        RIGS["mh4_minimal"], template_id=template_id, preset_id="moderate", bars=bars
    )
    by_step = {effect.step_id: effect for effect in effects}

    entry_step = "build" if template_id == "build_drop_recover" else "intro"
    exit_step = "recover" if template_id == "build_drop_recover" else "outro"

    entry = _curve_values(by_step[entry_step].settings, channel=15)
    exit_ = _curve_values(by_step[exit_step].settings, channel=15)

    assert entry[-1] > entry[0], "FADE_IN should end brighter than it starts"
    assert exit_[-1] < exit_[0], "FADE_OUT should end darker than it starts"


def _curve_values(settings: str, *, channel: int) -> list[float]:
    token = f"E_VALUECURVE_DMX{channel}="
    for part in settings.split(","):
        if part.startswith(token):
            payload = part[len(token) :]
            return [
                float(point.split(":")[1])
                for point in payload.split("Values=")[1].rstrip("|").split(";")
            ]
    raise AssertionError(f"no value curve for channel {channel} in settings string")
