"""The song outranks the arrangement (`RenderingPipeline._settle_arrangement`): a section's
variation never makes one of the plan's events worse than the same plan with every part on
its source variant (no event lost on a head, a hit farther from its lyric or beat, a colour
shown later or more briefly), and where it would, it takes its next candidate or gives
way, traced; repair predicts it for the planner. Every rig here narrows its allowed ranges
(`allowed_rig`) and most move at 150 degree/s."""

from __future__ import annotations

from collections.abc import Iterator
import random
from typing import Any

import pytest

from tests.support import moving_heads as m
from tests.unit.sequencer.moving_heads.test_events_render import HEADS, owner_like_rig, rig
from twinklr.core.agents.sequencer.moving_heads.models import ChoreographyPlan
from twinklr.core.agents.sequencer.moving_heads.rig_repair import repair_rig_intent
from twinklr.core.config.fixtures import FixtureGroup
from twinklr.core.sequencer.moving_heads.pipeline import (
    RenderingPipeline,
    TemplateAdmission,
    _event_outcomes,
    _worse_events,
    admit_templates,
)
from twinklr.core.sequencer.timing.beat_grid import BeatGrid

FAMILIES = (
    "fly_out_cascade",
    "fly_in_cascade",
    "target_orbit",
    "mirror_wings",
    "masked_wheel_flick",
    "finite_snap_hold",
)


@pytest.fixture(autouse=True)
def _catalog() -> Iterator[None]:
    with m.family_catalog():
        yield


def slow(group: FixtureGroup, speed: float = 150.0) -> FixtureGroup:
    payload = group.model_dump(mode="json")
    for fixture in payload["fixtures"]:
        for axis in ("pan", "tilt"):
            fixture["config"]["physical_profile"]["axes"][axis]["travel_speed_per_s"] = speed
    return m.allowed_rig(FixtureGroup.model_validate(payload))


def gate(fg: FixtureGroup, beat_grid: BeatGrid) -> TemplateAdmission:
    job = m.family_job(HEADS)
    return admit_templates(
        list(FAMILIES),
        beat_grid=beat_grid,
        fixture_group=fg,
        initial_states=job.moving_heads.initial_states,
        failure_mode=job.moving_heads.reposition_fallback,
        on_unplayable=job.moving_heads.on_unplayable,
        excludable=list(FAMILIES),
    )


def event(bar: int, beat: int, action: str, **fields: Any) -> dict[str, Any]:
    return {
        "bar": bar,
        "beat": beat,
        "action": action,
        "color": None,
        "gobo": None,
        "moment_cue_id": None,
        **fields,
    }


def played(
    sections: list, fg: FixtureGroup, beat_grid: BeatGrid, admission: TemplateAdmission
) -> tuple[RenderingPipeline, list[Any]]:
    repaired = repair_rig_intent(
        ChoreographyPlan(sections=sections, overall_strategy=""), admission.offer, {}, beat_grid
    )
    pipeline = RenderingPipeline(
        choreography_plan=repaired,
        beat_grid=beat_grid,
        fixture_group=fg,
        job_config=m.family_job(HEADS),
        media_file="silence.wav",
        admission=admission,
    )
    pipeline.render()
    return pipeline, list(repaired.repairs)


def worse(varied: RenderingPipeline, plain: RenderingPipeline) -> list[tuple[str, str]]:
    assert varied.render_record is not None and plain.render_record is not None
    return _worse_events(
        _event_outcomes(plain.render_record), _event_outcomes(varied.render_record)
    )


def owner_shaped(variation: str, beat_grid: BeatGrid) -> list[Any]:
    """An introduction, a FASTER-varied fly_in_cascade section with two cue-bound hits and
    a colour change, and a section whose first downbeat carries a hit (the owner's
    break and chorus_2, synthetic)."""

    def cue(bar: int, beat: int, share: float) -> int:
        i = beat_grid.beat_index(bar, beat)
        assert i is not None
        beats = beat_grid.beat_boundaries
        return int(beats[i] + share * (beats[i + 1] - beats[i]))

    return [
        m.plan_section("verse", 1, 4, "fly_in_cascade", motif_id="m"),
        m.plan_section(
            "break",
            5,
            8,
            "fly_in_cascade",
            motif_id="m",
            variation=variation,
            moment_cues=["hail", "god"],
            events=[
                event(6, 3, "hit", moment_cue_id="hail", cue_ms=cue(6, 3, 0.1)),
                event(7, 3, "hit", moment_cue_id="god", cue_ms=cue(7, 3, 0.1)),
                event(8, 1, "color", color="white"),
            ],
        ),
        m.plan_section("chorus", 9, 12, "mirror_wings", events=[event(9, 1, "hit")]),
    ]


@pytest.mark.parametrize("variation", ["FASTER", "SLOWER", "WIDEN", "NARROW"])
def test_the_owner_shaped_break_never_costs_an_event(variation: str) -> None:
    beat_grid = m.pickup_grid(60_000 / 79.5, 12, pickup=2)
    fg = slow(owner_like_rig())
    admission = gate(fg, beat_grid)
    varied, said = played(owner_shaped(variation, beat_grid), fg, beat_grid, admission)
    plain, _ = played(owner_shaped("NONE", beat_grid), fg, beat_grid, admission)

    assert worse(varied, plain) == []
    assert varied.render_record is not None
    looks = {look["section_id"]: look for look in varied.render_record["section_looks"]}
    step = looks["break"]["arrangement"]["variation"]
    gave_way = "gave way" in (step.get("reason") or "")
    # Repair predicts it for the planner (from the published dark phases).
    assert gave_way == any(r.section_id == "break" and "gives way" in r.reason for r in said)
    if gave_way:
        assert step["plays"] == step["from"]
        assert any(
            "does not play" in d["message"] and "gave way" in d["message"]
            for d in varied.render_record["diagnostics"]
        )


@pytest.mark.parametrize("seed", range(10))
def test_no_variation_makes_an_event_worse_on_random_plans(seed: int) -> None:
    """Random three-section plans (a family, an introduced motif, one varied section with
    hits, a cue-bound hit and a colour change, a next section with a downbeat hit), on the
    plain rig and on 150 degree/s narrowed heads: never an event worse than with the
    variation off."""
    chooser = random.Random(seed)
    bpm = chooser.choice([79.5, 120.0, 170.0])
    beat_grid = m.pickup_grid(60_000 / bpm, 12, pickup=0)
    fg = chooser.choice([m.allowed_rig(rig()), slow(rig())])
    admission = gate(fg, beat_grid)
    family = chooser.choice([f for f in FAMILIES if f in admission.admitted])
    variation = chooser.choice(["FASTER", "SLOWER", "WIDEN", "NARROW"])
    intro = chooser.choice([None, "wide", "narrow"])
    beats = beat_grid.beat_boundaries

    def plan(step: str) -> list[Any]:
        i = beat_grid.beat_index(6, 2)
        assert i is not None
        return [
            m.plan_section("s1", 1, 4, family, intro, motif_id="m"),
            m.plan_section(
                "s2",
                5,
                8,
                family,
                motif_id="m",
                variation=step,
                moment_cues=["c"],
                events=[
                    event(5, 1, "hit"),
                    event(6, 2, "hit", moment_cue_id="c", cue_ms=int(beats[i] + 120)),
                    event(7, chooser.choice([1, 2, 3]), "color", color="blue"),
                    event(8, 4, "hit"),
                ],
            ),
            m.plan_section("s3", 9, 12, family, events=[event(9, 1, "hit")]),
        ]

    state = chooser.getstate()
    varied, _ = played(plan(variation), fg, beat_grid, admission)
    chooser.setstate(state)
    plain, _ = played(plan("NONE"), fg, beat_grid, admission)

    assert worse(varied, plain) == [], (bpm, family, intro, variation)


def test_a_colour_change_shown_until_an_exit_is_counted_to_the_exit() -> None:
    """`shown_for_ms` is counted on the planned frames: an EXIT blackout laid after the
    events ends it (D3)."""
    beat_grid = m.pickup_grid(500.0, 4, pickup=0)
    fg = m.allowed_rig(rig())
    admission = gate(fg, beat_grid)
    blackout = {
        "edge": "EXIT",
        "mode": "blackout",
        "length": "BAR",
        "curve": "linear",
        "split": "HALF",
        "channels": [],
    }
    pipeline, _ = played(
        [
            m.plan_section(
                "s",
                1,
                4,
                "mirror_wings",
                color="red",
                events=[event(4, 1, "color", color="blue")],
                transitions=[blackout],
            )
        ],
        fg,
        beat_grid,
        admission,
    )
    assert pipeline.render_record is not None
    (look,) = pipeline.render_record["section_looks"]
    (entry,) = look["events"]
    (exit_,) = look["transitions"]
    for head in entry["heads"].values():
        if head.get("shown_ms") is None:
            continue
        assert head["shown_ms"] + head["shown_for_ms"] <= exit_["window_ms"][0] + 20
