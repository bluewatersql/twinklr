"""The song outranks the arrangement (`RenderingPipeline._choose_arrangement`, `worse`):
the arrangement is built up from the reference (every variation step off), and a section's
variation plays only where no event anywhere is worse than in the reference (no event lost
on a head, a hit farther from its lyric or beat, a colour shown later or more briefly, ...);
else it takes its next candidate or gives way, traced; repair predicts where it may.
Every rig here narrows its allowed ranges
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
    admit_templates,
)
from twinklr.core.sequencer.moving_heads.pipeline import worse as worse_than
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


def worse(varied: RenderingPipeline, plain: RenderingPipeline) -> list[str]:
    return worse_than(plain, varied)


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
    # Repair predicts where a variation may give way; the render decides.
    assert all(r.reason.startswith("the variation may") for r in said if "events worse" in r.reason)
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


def test_a_harmless_variation_after_one_that_gives_way_still_plays() -> None:
    """The arrangement is built up from the reference in plan order: the break's FASTER
    costs its own lyric hits and the chorus's downbeat hit, so it gives way; the chorus's
    WIDEN, judged with the break at its source variant, costs nothing and plays (it was
    once blamed for the break's loss and given up for nothing)."""
    beat_grid = m.pickup_grid(60_000 / 79.5, 12, pickup=2)
    fg = slow(owner_like_rig())
    admission = gate(fg, beat_grid)
    sections = owner_shaped("FASTER", beat_grid)
    chorus = sections[2].model_copy(
        update={"motif_id": "m", "variation": type(sections[2].variation)("WIDEN")}
    )
    sections = [sections[0], sections[1], chorus]
    pipeline, _ = played(sections, fg, beat_grid, admission)
    plain, _ = played(
        [s.model_copy(update={"variation": type(s.variation)("NONE")}) for s in sections],
        fg,
        beat_grid,
        admission,
    )

    assert worse(pipeline, plain) == []
    assert pipeline.render_record is not None
    looks = {look["section_id"]: look for look in pipeline.render_record["section_looks"]}
    brk = looks["break"]["arrangement"]["variation"]
    chorus_step = looks["chorus"]["arrangement"]["variation"]
    if "gave way" in (brk.get("reason") or ""):
        assert brk["plays"] == brk["from"]
    assert chorus_step["plays"] == "wide" and not chorus_step.get("reason")
    # One reference render plus one per distinct candidate tried: the break's two, the
    # chorus's one, and the break's two again once the chorus is accepted.
    assert 1 < pipeline.arrangement_renders <= 1 + 2 + 1 + 2


def test_worse_is_empty_for_a_render_against_itself() -> None:
    beat_grid = m.pickup_grid(60_000 / 120, 12, pickup=0)
    fg = m.allowed_rig(rig())
    admission = gate(fg, beat_grid)
    pipeline, _ = played(owner_shaped("NONE", beat_grid), fg, beat_grid, admission)

    assert worse(pipeline, pipeline) == []


@pytest.mark.parametrize("ending", ["exit_blackout", "entry_repositioning"])
def test_shown_time_matches_the_encoded_frames(ending: str) -> None:
    """`shown_for_ms` equals what the encoded frames show: lit, holding the state, from
    the reveal; before an EXIT blackout and before the next section's entry repositioning
    (a colour change on the section's last beat)."""
    from tests.unit.sequencer.moving_heads.test_events_render import Frames

    beat_grid = m.pickup_grid(500.0, 8, pickup=0)
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
    first = m.plan_section(
        "s",
        1,
        4,
        "mirror_wings",
        color="red",
        events=[event(4, 3, "color", color="blue")],
        transitions=[blackout] if ending == "exit_blackout" else [],
    )
    sections = (
        [first]
        if ending == "exit_blackout"
        else [first, m.plan_section("t", 5, 8, "fly_out_cascade")]
    )
    pipeline, _ = played(sections, fg, beat_grid, admission)
    assert pipeline.render_record is not None
    looks = {look["section_id"]: look for look in pipeline.render_record["section_looks"]}
    (entry,) = looks["s"]["events"]
    frames = Frames(pipeline)
    checked = 0
    for head, outcome in entry["heads"].items():
        if outcome.get("shown_ms") is None:
            continue
        dark, colours = frames.dark(head), frames.state(head, "color")
        i = outcome["shown_ms"] // 20
        j = i
        while j < len(dark) and not dark[j] and colours[j] == outcome["state"]:
            j += 1
        assert outcome["shown_for_ms"] == (j - i) * 20, (head, outcome)
        checked += 1
    assert checked


def test_a_registered_unit_kind_is_built_up_from_the_reference(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The unit interface (`ArrangementUnit`, `register_arrangement_units`): a kind's units
    are tried, after the reference, with the render reading `unit_choice`; a candidate
    that plays no event worse is kept. Here a kind whose choice changes nothing."""
    from twinklr.core.sequencer.moving_heads import pipeline as module

    def kind(pipeline: RenderingPipeline) -> list[module.ArrangementUnit]:
        return [module.ArrangementUnit(key="probe:s", order=(0, 9), candidates=("on",))]

    monkeypatch.setattr(module, "_UNIT_KINDS", [*module._UNIT_KINDS, kind])
    beat_grid = m.pickup_grid(500.0, 8, pickup=0)
    fg = m.allowed_rig(rig())
    admission = gate(fg, beat_grid)
    pipeline, _ = played(
        [m.plan_section("s", 1, 8, "mirror_wings", events=[event(2, 1, "hit")])],
        fg,
        beat_grid,
        admission,
    )

    assert pipeline.unit_choice("probe:s") == "on"
    assert pipeline.unit_gave_way("probe:s") is None
    assert pipeline.arrangement_renders == 2  # the reference and the one candidate
