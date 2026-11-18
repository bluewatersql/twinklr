"""Density BUSY on the render (`density.play_busy`, W10d): an accent each bar on each
head's first lit beat, HIGH under a shaped intensity, never a strobe, never inside a planner
event's seen span or a transition's window, never shortening a transition; and repair's
feedback on BUSY over more than a quarter of the song. Every render test runs on the tagged
family rig and on the same rig with allowed ranges narrower than physical and heads at 150
degree/s, gated (`test_density_render`)."""

from __future__ import annotations

from collections.abc import Sequence
import math
from typing import Any

import pytest

from tests.support import moving_heads as m
from tests.unit.sequencer.moving_heads.test_density_render import (
    MODES,
    RIGS,
    _catalog,  # noqa: F401  (the autouse catalog fixture)
    assert_physical,
    density_of,
    play,
    three,
    transition,
    windows,
)
from tests.unit.sequencer.moving_heads.test_events_render import (
    HEADS,
    Frames,
    event,
    grid,
    rig,
)
from twinklr.core.agents.sequencer.moving_heads.models import ChoreographyPlan
from twinklr.core.agents.sequencer.moving_heads.rig_repair import repair_rig_intent
from twinklr.core.formats.xlights.sequence.fresh import EFFECT_GRID_MS
from twinklr.core.sequencer.moving_heads.events import HIT_LATE_FRAMES, HIT_MIN_LIT_FRAMES
from twinklr.core.sequencer.moving_heads.pipeline import (
    RenderingPipeline,
    worse,
)
from twinklr.core.sequencer.moving_heads.song_intent import rig_offer

FRAME = EFFECT_GRID_MS


def first_lit_beats(plain: RenderingPipeline, head: str, bars: Sequence[int]) -> list[int]:
    """Per bar, the frame of the first beat the head is lit on for `HIT_MIN_LIT_FRAMES`
    running in the render without BUSY (within `HIT_LATE_FRAMES` of the beat's frame), read
    from its encoded frames."""
    dark = Frames(plain).dark(head)
    beat_grid = plain.beat_grid
    out = []
    for bar in bars:
        for index in beat_grid.bar_beat_indices(bar):
            at = math.floor(beat_grid.beat_boundaries[index] / FRAME + 0.5)
            start = next(
                (
                    s
                    for s in range(at, at + HIT_LATE_FRAMES + 1)
                    if all(s + k < len(dark) and not dark[s + k] for k in range(HIT_MIN_LIT_FRAMES))
                ),
                None,
            )
            if start is not None:
                out.append(start * FRAME)
                break
    return out


def non_dimmer(pipeline: RenderingPipeline, head: str) -> list[list[int]]:
    frames = Frames(pipeline)
    dimmer = frames.profile.axes["dimmer"].coarse_offset
    return [[v for k, v in sorted(raw.items()) if k != dimmer] for raw in frames.raw(head)]


@pytest.mark.parametrize("template_id", ["mirror_wings", "fly_in_cascade", "masked_wheel_flick"])
@pytest.mark.parametrize("kind", RIGS)
def test_busy_accents_each_heads_first_lit_beat_of_every_bar(kind: str, template_id: str) -> None:
    busy = play([m.plan_section("s1", 1, 8, template_id, density="BUSY")], kind)
    plain = play([m.plan_section("s1", 1, 8, template_id)], kind)
    entry = density_of(busy)
    assert entry["emphasis"] == "MED"
    for head in HEADS:
        assert entry["placed"][head] == first_lit_beats(plain, head, range(1, 9)), head
        # Only the dimmer changes: never a strobe, never a move or a wheel.
        assert non_dimmer(busy, head) == non_dimmer(plain, head), head
        dimmer, base = Frames(busy).dimmer(head), Frames(plain).dimmer(head)
        changed = [i * FRAME for i, (a, b) in enumerate(zip(dimmer, base, strict=True)) if a != b]
        assert changed
        for t in changed:
            assert any(at - 500 <= t < at + 500 for at in entry["placed"][head]), (head, t)
    assert_physical(busy, plain)


@pytest.mark.parametrize(
    ("intensity", "emphasis"),
    [
        (None, "MED"),
        ("SLOW", "MED"),
        ("SMOOTH", "MED"),
        ("FAST", "MED"),
        ("DRAMATIC", "HIGH"),
        ("INTENSE", "HIGH"),
    ],
)
@pytest.mark.parametrize("kind", RIGS)
def test_busy_accents_are_high_under_a_shaped_intensity(
    kind: str, intensity: str | None, emphasis: str
) -> None:
    busy = play(
        [m.plan_section("s1", 1, 8, "mirror_wings", density="BUSY", intensity=intensity)], kind
    )
    plain = play([m.plan_section("s1", 1, 8, "mirror_wings", intensity=intensity)], kind)
    entry = density_of(busy)
    assert entry["emphasis"] == emphasis
    assert sum(len(at) for at in entry["placed"].values()) + len(
        entry.get("not_visible", [])
    ) == 8 * len(HEADS)
    assert busy.frames != plain.frames
    assert_physical(busy, plain)


def test_an_accent_that_would_not_show_is_traced_one_by_one() -> None:
    """A dimmer too slow to flash: every accent would differ from the section's level on no
    frame, so none plays, and each says so (never a blanket record)."""

    def render(density: str) -> RenderingPipeline:
        pipeline = RenderingPipeline(
            choreography_plan=ChoreographyPlan(
                sections=[m.plan_section("s1", 1, 8, "mirror_wings", density=density)],
                overall_strategy="",
            ),
            beat_grid=grid(120),
            fixture_group=rig(dimmer_speed=3.0),
            job_config=m.family_job(HEADS),
            media_file="silence.wav",
        )
        pipeline.render()
        return pipeline

    busy, plain = render("BUSY"), render("BALANCED")
    assert busy.frames == plain.frames
    entry = density_of(busy)
    assert entry["placed"] == {}
    assert len(entry["not_visible"]) == 8 * len(HEADS)
    assert all(d["reason"].startswith("no visible change") for d in entry["not_visible"])


@pytest.mark.parametrize("kind", RIGS)
def test_busy_gives_way_to_the_planners_events_and_transitions(kind: str) -> None:
    """An accent inside a planner event's seen span (a hit's widened by a beat) or inside a
    transition's window is dropped and traced; every event plays as at BALANCED."""
    events = [event(3, 1, "hit"), event(5, 1, "color", color="red"), event(7, 2, "hit")]
    entering = [transition("crossfade")]

    def plan(density: str) -> list[Any]:
        return [
            m.plan_section("s0", 1, 2, "target_orbit"),
            m.plan_section(
                "s1", 3, 8, "mirror_wings", density=density, events=events, transitions=entering
            ),
        ]

    busy, plain = play(plan("BUSY"), kind), play(plan("BALANCED"), kind)
    entry = density_of(busy)
    reasons = {(d["fixture_id"], d["bar"]): d["reason"] for d in entry["dropped"]}
    for head in HEADS:
        # Bar 3's first lit beat lies in the crossfade (the render without it accents a
        # later beat there): dropped either way, never moved past the window.
        assert "transition" in reasons[(head, 3)]
        assert "color at bar 5 beat 1's seen span" in reasons[(head, 5)]
        assert "hit at bar 7 beat 2's seen span" in reasons[(head, 7)]
    assert busy.render_record is not None and plain.render_record is not None
    assert worse(plain, busy) == []
    assert windows(busy) == windows(plain)
    (_, (start, end)) = windows(busy)[0]
    for head in HEADS:
        a, b = Frames(busy).raw(head), Frames(plain).raw(head)
        assert a[start // FRAME : end // FRAME] == b[start // FRAME : end // FRAME], head
    assert_physical(busy, plain)


@pytest.mark.parametrize("mode", MODES)
@pytest.mark.parametrize("kind", RIGS)
def test_busy_accents_never_shorten_a_transition(kind: str, mode: str) -> None:
    busy = play(three("BUSY", mode), kind, bars=12)
    plain = play(three("BALANCED", mode), kind, bars=12)
    assert windows(busy) == windows(plain)
    for _, (start, end) in windows(busy):
        assert abs((end - start) - 2000) <= FRAME
    assert_physical(busy, plain)


@pytest.mark.parametrize("kind", RIGS)
def test_busy_over_two_parts_accents_every_bar_of_the_section(kind: str) -> None:
    section = m.plan_section("s1", 1, 8, "mirror_wings", density="BUSY").model_copy(
        update={
            "parts": [
                m.plan_section("x", 1, 4, "mirror_wings").parts[0],
                m.plan_section("x", 5, 8, "target_orbit").parts[0],
            ]
        }
    )
    busy = play([section], kind)
    first, second = density_of(busy, "s1|A"), density_of(busy, "s1|B")
    for head in HEADS:
        bars = [*first["placed"][head], *second["placed"][head]]
        assert len(bars) == 8, head


def test_busy_over_a_quarter_of_the_song_is_fed_back_lowest_energy_first() -> None:
    """Never a refusal: the sections keep BUSY; the lowest-energy BUSY sections are recorded
    until the rest cover at most a quarter of the song."""
    sections = [
        m.plan_section("verse", 1, 4, "mirror_wings", density="BUSY", energy_level=40),
        m.plan_section("chorus", 5, 8, "mirror_wings", density="BUSY", energy_level=90),
        m.plan_section("bridge", 9, 12, "target_orbit", density="BUSY", energy_level=60),
        m.plan_section("outro", 13, 16, "target_orbit"),
    ]
    beat_grid = grid(120, 16)
    plan = ChoreographyPlan(sections=sections, overall_strategy="")
    repaired = repair_rig_intent(plan, rig_offer(rig(), beat_grid), {}, beat_grid)
    said = [r for r in repaired.repairs if r.item == "density BUSY"]
    assert [r.section_id for r in said] == ["verse", "bridge"]
    assert all("more than 25%" in r.reason for r in said)
    assert repaired.sections == sections


@pytest.mark.parametrize("mode", ["snap", "crossfade"])
@pytest.mark.parametrize("kind", RIGS)
def test_busy_never_changes_what_a_transition_plays(kind: str, mode: str) -> None:
    """Accents are decided once, without the transitions, and dropped only inside a
    transition that plays on the head: a transition that plays nothing on a head at
    BALANCED plays nothing under BUSY (the played rule sees no accent difference)."""

    def plan(density: str) -> list[Any]:
        return [
            m.plan_section("s1", 1, 4, "mirror_wings"),
            m.plan_section(
                "s2", 5, 8, "fly_in_cascade", density=density, transitions=[transition(mode)]
            ),
            m.plan_section("s3", 9, 12, "target_orbit"),
        ]

    busy = play(plan("BUSY"), kind, bars=12)
    plain = play(plan("BALANCED"), kind, bars=12)

    def statuses(pipeline: RenderingPipeline) -> list[dict[str, str]]:
        assert pipeline.render_record is not None
        return [
            {h: o.get("plays", "not played").split(":")[0] for h, o in t["heads"].items()}
            for look in pipeline.render_record["section_looks"]
            for t in look.get("transitions", [])
        ]

    assert statuses(busy) == statuses(plain)
    assert worse(plain, busy) == []


def test_density_units_that_cost_nothing_settle_in_one_trial() -> None:
    """Every unit on its first candidate at once: three BUSY sections that make nothing
    worse take the reference and one trial, not one each."""
    pipeline = RenderingPipeline(
        choreography_plan=ChoreographyPlan(
            sections=[
                m.plan_section(f"s{i}", 2 * i - 1, 2 * i, "mirror_wings", density="BUSY")
                for i in (1, 2, 3)
            ],
            overall_strategy="",
        ),
        beat_grid=grid(120),
        fixture_group=rig(),
        job_config=m.family_job(HEADS),
        media_file="silence.wav",
    )
    pipeline.render()
    assert pipeline.arrangement_renders == 2
    for section_id in ("s1", "s2", "s3"):
        assert density_of(pipeline, section_id)["placed"]
