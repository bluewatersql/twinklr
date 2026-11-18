"""Density end to end (`density`, W10d): every family plays each level visibly differently
from BALANCED; SPARSE lights every head at least once on every admitted variant; repair's
predictions agree with the render; density holds across parts and with motif, variation,
events and every intensity. Every case runs on the zoom pilot rig (every catalog family)
and on the same rig with allowed ranges narrower than physical and heads at 150 degree/s,
each gated and repaired as `twinklr run` renders."""

from __future__ import annotations

from collections.abc import Iterator
import functools
from typing import Any

import pytest

from tests.support import moving_heads as m
from tests.unit.sequencer.moving_heads.test_density_render import (
    assert_physical,
    density_of,
    shown,
    transition,
)
from tests.unit.sequencer.moving_heads.test_events_render import HEADS, Frames, event, grid
from twinklr.core.agents.sequencer.moving_heads.models import (
    ChoreographyPlan,
    Density,
    PlanSection,
)
from twinklr.core.agents.sequencer.moving_heads.rig_repair import repair_rig_intent
from twinklr.core.config.fixtures import FixtureGroup
from twinklr.core.config.models import JobConfig
from twinklr.core.sequencer.moving_heads.pipeline import (
    RenderingPipeline,
    TemplateAdmission,
    _event_outcomes,
    _worse_events,
    admit_templates,
)

LEVELS = ("REST", "SPARSE", "BUSY")
RIGS = ("fast", "allowed_slow")


@pytest.fixture(autouse=True)
def _catalog() -> Iterator[None]:
    with m.family_catalog():
        yield


def fixture_group(kind: str) -> FixtureGroup:
    """The zoom rig (every catalog family), at 150 degree/s with allowed ranges narrower
    than physical for `allowed_slow` (zoom 10..38, which admits `zoom_wave`)."""
    group = m.zoom_rig(HEADS)
    if kind == "fast":
        return group
    payload = group.model_dump(mode="json")
    for fixture in payload["fixtures"]:
        for axis in ("pan", "tilt"):
            fixture["config"]["physical_profile"]["axes"][axis]["travel_speed_per_s"] = 150.0
    return m.allowed_rig(FixtureGroup.model_validate(payload), zoom=(10.0, 38.0))


def job() -> JobConfig:
    return m.zoom_job(HEADS)


@functools.cache
def _gate(kind: str, bars: int) -> TemplateAdmission:
    policy = job().moving_heads
    return admit_templates(
        list(m.CATALOG_IDS),
        beat_grid=grid(120, bars),
        fixture_group=fixture_group(kind),
        initial_states=policy.initial_states,
        failure_mode=policy.reposition_fallback,
        on_unplayable=policy.on_unplayable,
        excludable=list(m.CATALOG_IDS),
    )


def play(
    sections: list[PlanSection], kind: str, bars: int = 8
) -> tuple[RenderingPipeline, ChoreographyPlan]:
    """The plan repaired against the gate's offer and rendered, as `twinklr run` does."""
    admission = _gate(kind, bars)
    repaired = repair_rig_intent(
        ChoreographyPlan(sections=sections, overall_strategy=""),
        admission.offer,
        {},
        grid(120, bars),
    )
    pipeline = RenderingPipeline(
        choreography_plan=repaired,
        beat_grid=grid(120, bars),
        fixture_group=fixture_group(kind),
        job_config=job(),
        media_file="silence.wav",
        admission=admission,
    )
    pipeline.render()
    return pipeline, repaired


@pytest.mark.parametrize("level", LEVELS)
@pytest.mark.parametrize("template_id", m.CATALOG_IDS)
@pytest.mark.parametrize("kind", RIGS)
def test_every_family_plays_each_density_differently_from_balanced(
    kind: str, template_id: str, level: str
) -> None:
    dense, _ = play([m.plan_section("s1", 1, 8, template_id, density=level)], kind)
    plain, _ = play([m.plan_section("s1", 1, 8, template_id)], kind)
    assert dense.frames != plain.frames
    assert density_of(dense)["level"] == level
    assert_physical(dense, plain)


@pytest.mark.parametrize("template_id", m.CATALOG_IDS)
@pytest.mark.parametrize("kind", RIGS)
def test_sparse_lights_every_head_at_least_once_on_every_admitted_variant(
    kind: str, template_id: str
) -> None:
    """On every variant the gate admits, SPARSE alternates on that variant's cycle and every
    head lit as BALANCED is lit at least once (three frames running); where a variant
    could not, the part says so (never silently)."""
    offered = _gate(kind, 8).offer.templates[template_id]
    for variant in offered.variants:
        section = m.plan_section(
            "s1", 1, 8, template_id, None if variant == "base" else variant, density="SPARSE"
        )
        sparse, _ = play([section], kind)
        entry = density_of(sparse)
        assert entry["plays"] != "BALANCED" or entry["fallback"], variant
        if entry["plays"] == "BALANCED":
            continue
        frames = Frames(sparse)
        for head in HEADS:
            before, after = entry["lit_share"][head]
            if before > 0:
                assert shown(frames.dark(head), range(len(frames.dark(head)))), (variant, head)
            assert after <= before


@pytest.mark.parametrize("bars", [1, 2, 3, 4])
@pytest.mark.parametrize("template_id", m.CATALOG_IDS)
@pytest.mark.parametrize("kind", RIGS)
def test_repair_predicts_how_sparse_alternates(kind: str, template_id: str, bars: int) -> None:
    """Repair = render: from the variant's published dark phases repair says where SPARSE
    swaps every half cycle or plays BALANCED; the render's trace says the same."""
    sections = [
        m.plan_section("s1", 1, bars, template_id, density="SPARSE"),
        m.plan_section("s2", bars + 1, 8, "mirror_wings"),
    ]
    sparse, repaired = play(sections, kind)
    entry = density_of(sparse)
    said = [r.reason for r in repaired.repairs if r.item == "density SPARSE"]
    if entry["plays"] == "BALANCED":
        assert said and said[0].endswith("so it plays as BALANCED; give SPARSE a longer section")
    elif entry["alternates"] == "half cycle":
        assert said and said[0].endswith("so its halves swap every half cycle"), said
    else:
        assert said == []


EVENTS = [
    event(2, 3, "hit"),
    event(4, 1, "color", color="red"),
    event(6, 2, "hit", moment_cue_id="cue", cue_ms=10_300),
    event(7, 3, "gobo", gobo="dots"),
]


@pytest.mark.parametrize("level", ["SPARSE", "BUSY"])
@pytest.mark.parametrize("template_id", m.FAMILY_IDS)
@pytest.mark.parametrize("kind", RIGS)
def test_repair_and_render_agree_that_sparse_and_busy_leave_events_as_balanced(
    kind: str, template_id: str, level: str
) -> None:
    """The song outranks the arrangement by construction: SPARSE keeps every head as
    BALANCED over what an event shows and BUSY drops its accents there, so the events play
    as at BALANCED and repair's event predictions are BALANCED's."""

    def sections(density: str) -> list[PlanSection]:
        return [
            m.plan_section(
                "s1",
                1,
                8,
                template_id,
                events=EVENTS,
                moment_cues=["cue"],
                density=density,
            )
        ]

    dense, dense_plan = play(sections(level), kind)
    plain, plain_plan = play(sections("BALANCED"), kind)
    assert dense.render_record is not None and plain.render_record is not None
    assert (
        _worse_events(_event_outcomes(plain.render_record), _event_outcomes(dense.render_record))
        == []
    )

    def events_said(plan: ChoreographyPlan) -> list[tuple[str, str]]:
        return [(r.item, r.reason) for r in plan.repairs if r.item.startswith("event at")]

    assert events_said(dense_plan) == events_said(plain_plan)


@pytest.mark.parametrize("level", LEVELS)
@pytest.mark.parametrize("kind", RIGS)
def test_the_songs_first_entry_snap_plays_nothing_under_any_density(kind: str, level: str) -> None:
    """Repair = render for a transition that plays nothing: the song's first ENTRY `snap`
    is the plain cut whatever the density."""
    snap = {**transition("snap"), "length": "BEAT"}
    dense, repaired = play(
        [m.plan_section("s1", 1, 8, "mirror_wings", density=level, transitions=[snap])], kind
    )
    assert dense.render_record is not None
    (entry,) = dense.render_record["section_looks"][0]["transitions"]
    assert all(h["plays"].startswith("nothing: ") for h in entry["heads"].values())
    assert any("plays as the plain cut (nothing)" in r.reason for r in repaired.repairs)


@pytest.mark.parametrize("kind", RIGS)
def test_density_holds_across_parts_each_on_its_own_variant(kind: str) -> None:
    parts = [
        m.plan_section("x", 1, 4, "mirror_wings").parts[0],
        m.plan_section("x", 5, 8, "finite_snap_hold").parts[0],
    ]
    sparse, _ = play(
        [
            m.plan_section("s1", 1, 8, "mirror_wings", density="SPARSE").model_copy(
                update={"parts": parts}
            )
        ],
        kind,
    )
    first, second = density_of(sparse, "s1|A"), density_of(sparse, "s1|B")
    assert (first["cycle_bars"], second["cycle_bars"]) == (2.0, 1.0)
    assert first["alternates"] == second["alternates"] == "cycle"
    assert_physical(sparse)


@pytest.mark.parametrize("intensity", [None, "SLOW", "SMOOTH", "FAST", "DRAMATIC", "INTENSE"])
@pytest.mark.parametrize("kind", RIGS)
def test_density_with_motif_variation_events_and_each_intensity(
    kind: str, intensity: str | None
) -> None:
    """A song shaped with every density, a motif carried and varied, events and one
    intensity throughout: each section plays its density on the variant it resolved to."""

    def section(section_id: str, bars: tuple[int, int], template: str, **fields: Any) -> Any:
        return m.plan_section(section_id, *bars, template, intensity=intensity, **fields)

    sections = [
        section(
            "intro",
            (1, 4),
            "mirror_wings",
            motif_id="m",
            density="REST",
            events=[event(3, 1, "hit")],
        ),
        section(
            "verse",
            (5, 8),
            "mirror_wings",
            motif_id="m",
            variation="NARROW",
            density="SPARSE",
            events=[event(6, 1, "color", color="blue")],
        ),
        section(
            "chorus",
            (9, 12),
            "mirror_wings",
            motif_id="m",
            variation="WIDEN",
            density="BUSY",
            events=[event(10, 2, "hit")],
        ),
        section("outro", (13, 16), "target_orbit", density="BALANCED"),
    ]
    dense, _ = play(sections, kind, bars=16)
    plain, _ = play(
        [s.model_copy(update={"density": Density.BALANCED}) for s in sections], kind, bars=16
    )
    assert density_of(dense, "intro")["plays"] == "dark"
    assert density_of(dense, "verse")["alternates"] == "cycle"
    assert sum(len(v) for v in density_of(dense, "chorus")["placed"].values()) > 0
    assert dense.render_record is not None
    looks = {look["section_id"]: look for look in dense.render_record["section_looks"]}
    assert looks["verse"]["arrangement"]["variation"]["asked"] == "NARROW"
    assert "density" not in looks.get("outro", {}).get("arrangement", {})
    assert dense.render_record is not None and plain.render_record is not None
    assert (
        _worse_events(_event_outcomes(plain.render_record), _event_outcomes(dense.render_record))
        == []
    )
    assert_physical(dense, plain)
