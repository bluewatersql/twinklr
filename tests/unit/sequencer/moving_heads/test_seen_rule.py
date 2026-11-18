"""A colour or gobo change is shown well (`events.SHOWN_FOR_BEATS`): a change whose heads
go dark again soon after the reveal moves, within its move bounds, to a beat where some
head stays lit showing it half a beat, else plays and is traced `brief`; repair predicts
both from the template's published dark phases."""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

import pytest

from tests.support import moving_heads as m
from tests.unit.sequencer.moving_heads.test_events_render import HEADS, grid, looks, render, rig
from twinklr.core.agents.sequencer.moving_heads.models import ChoreographyPlan
from twinklr.core.agents.sequencer.moving_heads.rig_repair import repair_rig_intent
from twinklr.core.sequencer.moving_heads.events import SHOWN_FOR_BEATS
from twinklr.core.sequencer.moving_heads.pipeline import admit_templates


def pulsing(template_id: str, duty: float) -> Any:
    """A held aim whose dimmer is lit for `duty` of every two beats, from the cycle's
    start."""
    return m.loop_template_doc(
        template_id,
        [
            m.hold_step(
                "hold",
                0.0,
                tilt=30.0,
                dimmer={"period_beats": 2.0, "duty_cycle": duty, "low": 0.0, "high": 1.0},
            )
        ],
    )


@pytest.fixture(autouse=True)
def _templates() -> Iterator[None]:
    with m.registered_templates(pulsing("lit_0p7", 0.7), pulsing("lit_0p2", 0.2)):
        yield


def play(template_id: str, bar: int, beat: int) -> tuple[dict[str, Any], str]:
    beat_grid = grid(120)
    fg = rig()
    job = m.family_job(HEADS)
    admission = admit_templates(
        [template_id],
        beat_grid=beat_grid,
        fixture_group=fg,
        initial_states=job.moving_heads.initial_states,
        failure_mode=job.moving_heads.reposition_fallback,
        on_unplayable=job.moving_heads.on_unplayable,
    )
    section = m.plan_section(
        "s",
        1,
        4,
        template_id,
        color="red",
        events=[
            {
                "bar": bar,
                "beat": beat,
                "action": "color",
                "color": "blue",
                "moment_cue_id": None,
                "gobo": None,
            }
        ],
    )
    repaired = repair_rig_intent(
        ChoreographyPlan(sections=[section], overall_strategy=""), admission.offer, {}, beat_grid
    )
    pipeline = render(repaired.sections, beat_grid=beat_grid, fixture_group=fg, admission=admission)
    (event,) = looks(pipeline)["s"]["events"]
    return event, " ".join(r.reason for r in repaired.repairs)


def test_a_change_shown_briefly_moves_to_a_beat_where_it_is_shown_well() -> None:
    """Lit 1.4 of every 2 beats: on the cycle's second beat the heads stay lit 0.4 beat
    after the reveal, so the change moves to the next beat (lit 1.4 beats)."""
    event, said = play("lit_0p7", 2, 2)

    for head in event["heads"].values():
        assert head["moved"]["direction"] == "later"
        assert "stays lit showing it" in head["moved"]["reason"]
        assert head["shown_for_ms"] + 20 >= SHOWN_FOR_BEATS * 500
    assert "no head stays lit showing it for 0.5 beat" in said and "it moves later" in said


def test_a_change_shown_briefly_everywhere_plays_and_is_traced_brief() -> None:
    """Lit 0.4 of every 2 beats: no beat within reach shows it half a beat; it plays where
    it is shown, traced `brief`, and repair feeds that back."""
    event, said = play("lit_0p2", 2, 1)

    for head in event["heads"].values():
        assert "not_played" not in head
        assert head["brief"].startswith(f"shown for {head['shown_for_ms']} ms")
        assert head["shown_for_ms"] < SHOWN_FOR_BEATS * 500
    assert "it is shown for less than 0.5 beat on every head" in said


def test_a_change_shown_well_on_its_beat_stays_there() -> None:
    event, said = play("lit_0p7", 2, 1)

    for head in event["heads"].values():
        assert "moved" not in head and "brief" not in head
    assert "moves" not in said and "less than 0.5 beat" not in said
