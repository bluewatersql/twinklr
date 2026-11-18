"""Density REST and SPARSE on the render (`density`, W10d): REST dark as a synthetic `closed`
that the planner's events still play through, SPARSE half the heads dark in turn on the
played variant's cycle and never over what a planner event shows. Every render test runs
on the tagged family rig and on the same rig with allowed ranges narrower than physical
(`allowed_rig`) and heads at 150 degree/s, gated."""

from __future__ import annotations

from collections.abc import Iterator, Sequence
from fractions import Fraction
import functools
from itertools import pairwise
import math
from typing import Any

import pytest

from tests.support import moving_heads as m
from tests.unit.sequencer.moving_heads.test_events_render import (
    HEADS,
    Frames,
    assert_wheels_turn_dark,
    event,
    grid,
    rig,
)
from twinklr.core.agents.sequencer.moving_heads.models import ChoreographyPlan, PlanSection
from twinklr.core.agents.sequencer.moving_heads.rig_repair import repair_rig_intent
from twinklr.core.config.fixtures import FixtureGroup
from twinklr.core.formats.xlights.sequence.fresh import EFFECT_GRID_MS
from twinklr.core.sequencer.models.enum import ChannelName
from twinklr.core.sequencer.models.moving_heads.physical import (
    ContinuousTrajectory,
    DiscretePoint,
    DiscreteTrajectory,
    PhysicalPoint,
)
from twinklr.core.sequencer.moving_heads.compile.preset import apply_preset
from twinklr.core.sequencer.moving_heads.compile.template_compiler import whole_period_cycle
from twinklr.core.sequencer.moving_heads.density import (
    REST_INDEX,
    play_sparse,
    rest_record,
    with_rest,
)
from twinklr.core.sequencer.moving_heads.events import (
    HIT_MIN_LIT_FRAMES,
    apply_section_events,
    section_events,
)
from twinklr.core.sequencer.moving_heads.pipeline import (
    RenderingPipeline,
    TemplateAdmission,
    _commanded_dark_runs,
    _dark_over_spans,
    _dark_windows,
    _dip_span,
    admit_templates,
    worse,
)
from twinklr.core.sequencer.moving_heads.song_intent import rig_offer
from twinklr.core.sequencer.moving_heads.templates import get_template
from twinklr.core.sequencer.timing.beat_grid import BeatGrid
from twinklr.core.sequencer.timing.musical_phase import build_musical_phase_map

FRAME = EFFECT_GRID_MS
EVEN, ODD = ("MH1", "MH4"), ("MH2", "MH3")
"""The family rig's SPARSE halves: the outer mirror pair (folded slot 0), the inner (1)."""
MODES = ("snap", "crossfade", "morph", "sweep", "fade_via_black", "blackout")
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


def slow_rig() -> FixtureGroup:
    """The tagged family rig at 150 degree/s with allowed ranges narrower than physical."""
    payload = rig().model_dump(mode="json")
    for fixture in payload["fixtures"]:
        for axis in ("pan", "tilt"):
            fixture["config"]["physical_profile"]["axes"][axis]["travel_speed_per_s"] = 150.0
    return m.allowed_rig(FixtureGroup.model_validate(payload))


RIGS = ("family", "allowed_slow")


def fixture_group(kind: str) -> FixtureGroup:
    return rig() if kind == "family" else slow_rig()


@functools.cache
def _gate(kind: str, bars: int) -> TemplateAdmission | None:
    if kind == "family":
        return None
    job = m.family_job(HEADS)
    return admit_templates(
        list(FAMILIES),
        beat_grid=grid(120, bars),
        fixture_group=fixture_group(kind),
        initial_states=job.moving_heads.initial_states,
        failure_mode=job.moving_heads.reposition_fallback,
        on_unplayable=job.moving_heads.on_unplayable,
        excludable=list(FAMILIES),
    )


def play(sections: Sequence[PlanSection], kind: str, bars: int = 8) -> RenderingPipeline:
    """The plan rendered on `kind`'s rig over `bars` bars at 120 BPM (gated on the slow
    rig, as production renders a repaired plan)."""
    admission = _gate(kind, bars)
    plan = ChoreographyPlan(sections=list(sections), overall_strategy="")
    if admission is not None:
        plan = repair_rig_intent(plan, admission.offer, {}, grid(120, bars))
    pipeline = RenderingPipeline(
        choreography_plan=plan,
        beat_grid=grid(120, bars),
        fixture_group=fixture_group(kind),
        job_config=m.family_job(HEADS),
        media_file="silence.wav",
        admission=admission,
    )
    pipeline.render()
    return pipeline


def density_of(pipeline: RenderingPipeline, section_id: str = "s1") -> dict[str, Any]:
    assert pipeline.render_record is not None
    look = next(
        look for look in pipeline.render_record["section_looks"] if look["section_id"] == section_id
    )
    entry: dict[str, Any] = look["arrangement"]["density"]
    return entry


def assert_physical(pipeline: RenderingPipeline, plain: RenderingPipeline | None = None) -> None:
    """No pan, tilt or zoom word leaves the operable range; between two lit frames no axis
    moves faster than its `travel_speed_per_s` (a word of rounding allowed); no wheel turns
    lit; and (given the same plan at BALANCED) on every frame lit in both, the pose and
    wheels are the BALANCED render's (density lights and darkens, it does not move or turn;
    where it darkens a head's entry, the transaction pass may move it there differently)."""
    frames = Frames(pipeline)
    assert_wheels_turn_dark(frames)
    profile = frames.profile
    for name, axis in profile.axes.items():
        if name == "dimmer":
            continue
        low, high = sorted(axis.dmx_word(v) for v in axis.operable_range)
        step = (axis.travel_speed_per_s or math.inf) * FRAME / 1000
        for head in HEADS:
            dark = frames.dark(head)
            words = []
            for raw in frames.raw(head):
                word = raw[axis.coarse_offset]
                if axis.fine_offset is not None:
                    word = word << 8 | raw[axis.fine_offset]
                assert low <= word <= high, (head, name, word)
                words.append(word)
            span = (axis.physical_max - axis.physical_min) / axis.full_word
            for i in range(1, len(words)):
                if not dark[i] and not dark[i - 1]:
                    moved = abs(words[i] - words[i - 1]) * span
                    assert moved <= step + span, (head, name, i * FRAME, moved)
    if plain is None:
        return
    offsets = [
        offset
        for name, axis in profile.axes.items()
        if name != "dimmer"
        for offset in (axis.coarse_offset, axis.fine_offset)
        if offset is not None
    ] + [profile.discrete[wheel].offset for wheel in ("color", "gobo")]
    base = Frames(plain)
    for head in HEADS:
        lit = [not a and not b for a, b in zip(frames.dark(head), base.dark(head), strict=True)]
        for at, (a, b) in enumerate(zip(frames.raw(head), base.raw(head), strict=True)):
            if lit[at]:
                assert [a[o] for o in offsets] == [b[o] for o in offsets], (head, at * FRAME)


def frames_of(beat_grid: BeatGrid, start_bar: int, end_bar: int) -> range:
    """The frame indices of bars `start_bar`..`end_bar`, as the render places a part."""
    bars = beat_grid.bar_boundaries
    first = math.floor(bars[start_bar - 1] / FRAME + 0.5)
    last = math.floor(bars[end_bar] / FRAME + 0.5) if end_bar < len(bars) else None
    return range(first, last if last is not None else first)


def window_frames(window_ms: Sequence[int]) -> range:
    return range(window_ms[0] // FRAME, window_ms[1] // FRAME)


# --- REST --------------------------------------------------------------------------------


@pytest.mark.parametrize("kind", RIGS)
def test_rest_is_dark_on_every_head_over_its_section_and_nothing_else_moves(kind: str) -> None:
    def plan(density: str) -> list[PlanSection]:
        return [
            m.plan_section("s1", 1, 2, "mirror_wings"),
            m.plan_section("s2", 3, 6, "target_orbit", density=density),
            m.plan_section("s3", 7, 8, "mirror_wings"),
        ]

    rested, plain = play(plan("REST"), kind), play(plan("BALANCED"), kind)
    frames, base = Frames(rested), Frames(plain)
    inside = frames_of(grid(120), 3, 6)
    for head in HEADS:
        assert all(frames.dark(head)[i] for i in inside), head
        assert any(not base.dark(head)[i] for i in inside), head
        assert frames.raw(head)[: inside.start] == base.raw(head)[: inside.start], head
        assert frames.raw(head)[inside.stop :] == base.raw(head)[inside.stop :], head
    entry = density_of(rested, "s2")
    assert entry["plays"] == "dark"
    assert entry["dark_ms"] == [inside.start * FRAME, inside.stop * FRAME]
    assert "lit" not in entry
    assert_physical(rested, plain)


@pytest.mark.parametrize("kind", RIGS)
def test_the_planners_events_still_play_inside_rest(kind: str) -> None:
    """A hit lights the heads from the dark, an `open` ends REST (the template plays as with
    the same events at BALANCED from there), a later `closed` darkens again, a strobe
    flashes; planner intent wins."""
    events = [
        event(2, 2, "hit"),
        event(4, 1, "open"),
        event(5, 1, "closed"),
        event(7, 1, "strobe_slow"),
    ]
    rested = play([m.plan_section("s1", 1, 8, "mirror_wings", events=events, density="REST")], kind)
    plain = play([m.plan_section("s1", 1, 8, "mirror_wings", events=events)], kind)
    frames, base = Frames(rested), Frames(plain)
    beat_grid = grid(120)
    opened = math.floor(beat_grid.bar_boundaries[3] / FRAME + 0.5)
    for head in HEADS:
        # From the `open` on, REST has ended: the frames are the events' alone.
        assert frames.raw(head)[opened:] == base.raw(head)[opened:], head
        # Before it, dark but for the hit.
        assert sum(not dark for dark in frames.dark(head)[:opened]) <= 30, head
    entry = density_of(rested)
    assert entry["dark_ms"][1] == opened * FRAME
    assert entry["ended_by"] == "the planner's open at bar 4 beat 1"
    assert rested.render_record is not None
    hit = rested.render_record["section_looks"][0]["events"][0]
    assert {outcome["how"] for outcome in hit["heads"].values()} == {"lit_from_dark"}
    assert "played_ms" in hit["heads"]["MH1"]
    assert_physical(rested, plain)


@pytest.mark.parametrize("action", ["open", "strobe_medium", "pulse", "closed"])
@pytest.mark.parametrize("kind", RIGS)
def test_a_planner_shutter_event_on_rests_first_beat_replaces_it(kind: str, action: str) -> None:
    """Same-frame precedence: a planner shutter event on REST's own frame wins, so the
    section plays as that event at BALANCED: the same frames lit and dark, every lit frame
    the same (a head REST keeps a dark cue for may move otherwise while dark)."""
    events = [event(1, 1, action)]
    rested = play([m.plan_section("s1", 1, 8, "mirror_wings", events=events, density="REST")], kind)
    plain = play([m.plan_section("s1", 1, 8, "mirror_wings", events=events)], kind)
    for head in HEADS:
        a, b = Frames(rested), Frames(plain)
        assert a.dark(head) == b.dark(head), head
        lit = [i for i, dark in enumerate(a.dark(head)) if not dark]
        assert [a.raw(head)[i] for i in lit] == [b.raw(head)[i] for i in lit], head
    assert density_of(rested)["plays"].startswith(f"nothing: the planner's {action}")


@pytest.mark.parametrize("kind", RIGS)
def test_a_colour_change_in_a_fully_dark_rest_is_not_seen_and_repair_says_so(kind: str) -> None:
    section = m.plan_section(
        "s1",
        1,
        8,
        "mirror_wings",
        events=[event(3, 1, "color", color="red")],
        density="REST",
        color="blue",
        intensity="DRAMATIC",
    )
    rested = play([section], kind)
    assert rested.render_record is not None
    colour = rested.render_record["section_looks"][0]["events"][0]
    assert all("not_played" in outcome for outcome in colour["heads"].values())
    offer = rig_offer(fixture_group(kind), grid(120))
    repaired = repair_rig_intent(
        ChoreographyPlan(sections=[section], overall_strategy=""), offer, {}, grid(120)
    )
    said = [(r.item, r.reason) for r in repaired.repairs]
    assert any(
        item.startswith("event at bar 3 beat 1: color red")
        and "it does not play" in reason
        and "the section's REST" in reason
        for item, reason in said
    ), said
    assert any(
        item == "density REST" and "colour blue, intensity DRAMATIC is not seen" in reason
        for item, reason in said
    ), said
    assert repaired.sections == [section]  # recorded, never cut


def _no_dark_profile_rig() -> FixtureGroup:
    payload = rig().model_dump(mode="json")
    for fixture in payload["fixtures"]:
        if fixture["fixture_id"] == "MH2":
            visibility = fixture["config"]["physical_profile"]["visibility"]
            visibility.update(dimmer_zero_extinguishes=False, extinguishing_shutter_states=[])
    return FixtureGroup.model_validate(payload)


def test_rest_on_a_head_that_cannot_go_dark_is_traced_and_recorded_never_refused() -> None:
    """REST's `closed` on a head with no commandable darkness plays nothing there (its cues
    stay as compiled, no error) and is traced; repair records it. (The transaction pass
    itself cannot park such a head after its last cue, so no render on such a rig gets
    this far: `compile/preposition.py` `_dark_commands`.)"""
    fg = _no_dark_profile_rig()
    profiles = {f.fixture_id: f.config.physical_profile for f in fg.expand_fixtures()}
    beat_grid = grid(120)
    cues = [
        m.fixture_segment({}, fixture_id=head, t0_ms=0, t1_ms=4000, section_id="s1")
        for head in HEADS
    ]
    section = m.plan_section("s1", 1, 2, "mirror_wings", density="REST")
    events = with_rest(
        section_events(section, beat_grid), start_bar=1, start_ms=20, beat_grid=beat_grid
    )
    played, outcome = apply_section_events(
        cues,
        events,
        window=(0, 4000),
        profiles=profiles,  # type: ignore[arg-type]
        heads=[],
        palette=None,
        phase_map=build_musical_phase_map(beat_grid),
        beat_grid=beat_grid,
        darken=lambda own, spans: _dark_over_spans(own, spans, profiles, shortest_lit_ms=40),  # type: ignore[arg-type]
        dip_span=_dip_span,
        dark_runs=_commanded_dark_runs,
        dark_windows=_dark_windows,
        gap_ok=lambda *_: True,
    )
    by_head = {cue.fixture_id: cue for cue in played}
    assert by_head["MH2"] == next(c for c in cues if c.fixture_id == "MH2")
    assert by_head["MH1"] != next(c for c in cues if c.fixture_id == "MH1")
    heads = outcome.records[REST_INDEX]["heads"]
    assert "cannot be commanded dark" in heads["MH2"]["not_played"]
    entry = rest_record(events, (0, 4000), list(HEADS), profiles, heads)  # type: ignore[arg-type]
    assert list(entry["lit"]) == ["MH2"]

    repaired = repair_rig_intent(
        ChoreographyPlan(sections=[section], overall_strategy=""),
        rig_offer(fg, beat_grid),
        {},
        beat_grid,
    )
    assert [r.reason for r in repaired.repairs if r.item == "density REST"] == [
        "only some heads of this rig can be commanded dark; the others play their "
        "template's own light"
    ]


@pytest.mark.parametrize("kind", RIGS)
def test_rest_over_two_parts_is_dark_in_both_and_traced_per_part(kind: str) -> None:
    section = PlanSection.model_validate(
        m.plan_section("s1", 1, 8, "mirror_wings", density="REST").model_dump()
        | {
            "parts": [
                {
                    "start_bar": 1,
                    "template_id": "mirror_wings",
                    "preset_id": None,
                    "modifiers": [],
                    "label": None,
                    "reasoning": "",
                },
                {
                    "start_bar": 5,
                    "template_id": "target_orbit",
                    "preset_id": None,
                    "modifiers": [],
                    "label": None,
                    "reasoning": "",
                },
            ]
        }
    )
    rested = play([section], kind)
    frames = Frames(rested)
    for head in HEADS:
        assert all(frames.dark(head)[i] for i in frames_of(grid(120), 1, 8)), head
    assert density_of(rested, "s1|A")["plays"] == "dark"
    assert density_of(rested, "s1|B")["plays"] == "dark"


def transition(mode: str) -> dict[str, Any]:
    return {
        "edge": "ENTRY",
        "mode": mode,
        "length": "BAR",
        "curve": "linear",
        "split": "HALF",
        "channels": [],
    }


def three(density: str, mode: str) -> list[PlanSection]:
    """A section of `density` between two at BALANCED, entered and left by `mode`."""
    return [
        m.plan_section("s1", 1, 4, "mirror_wings"),
        m.plan_section("s2", 5, 8, "target_orbit", density=density, transitions=[transition(mode)]),
        m.plan_section("s3", 9, 12, "mirror_wings", transitions=[transition(mode)]),
    ]


def windows(pipeline: RenderingPipeline) -> list[tuple[str, list[int]]]:
    assert pipeline.render_record is not None
    return [
        (look["section_id"], t["window_ms"])
        for look in pipeline.render_record["section_looks"]
        for t in look.get("transitions", [])
    ]


@pytest.mark.parametrize("mode", MODES)
@pytest.mark.parametrize("kind", RIGS)
def test_transitions_into_and_out_of_rest(kind: str, mode: str) -> None:
    """REST is not an event: a transition into or out of it keeps its whole window (a bar,
    2000 ms here, as at BALANCED). Into REST a fade reads as a fade to dark: the light only
    falls across the window and is dark at its end; out of REST it only rises from dark."""
    rested = play(three("REST", mode), kind, bars=12)
    plain = play(three("BALANCED", mode), kind, bars=12)
    assert windows(rested) == windows(plain)
    for _, (start, end) in windows(rested):
        assert abs((end - start) - 2000) <= FRAME or (mode == "snap" and end - start == 2000)
    frames = Frames(rested)
    (_, into), (_, out) = windows(rested)
    fades = mode in ("crossfade", "morph", "sweep", "fade_via_black")
    for head in HEADS:
        dimmer, dark = frames.dimmer(head), frames.dark(head)
        span = window_frames(into)
        if fades:
            falling = [0 if dark[i] else dimmer[i] for i in span]
            assert all(b <= a for a, b in pairwise(falling)), (head, falling)
        # Dark from the window's end (from the boundary for snap and blackout) to the
        # transition out of REST, and from its start into its boundary.
        rest = range(span.stop - 1, window_frames(out).start + 1)
        assert all(dark[i] for i in rest), head
        span = window_frames(out)
        if fades:
            rising = [0 if dark[i] else dimmer[i] for i in span]
            assert all(b >= a for a, b in pairwise(rising)), (head, rising)
    assert_physical(rested)


# --- SPARSE ------------------------------------------------------------------------------


def unit_frames(beat_grid: BeatGrid, start_bar: int, cycle_bars: float, count: int) -> list[range]:
    out = []
    for k in range(count):
        a = beat_grid.get_bar_start_ms(start_bar - 1 + k * cycle_bars)
        b = beat_grid.get_bar_start_ms(start_bar - 1 + (k + 1) * cycle_bars)
        out.append(range(math.floor(a / FRAME + 0.5), math.floor(b / FRAME + 0.5)))
    return out


def shown(dark: Sequence[bool], frames: range) -> bool:
    run = 0
    for i in frames:
        run = 0 if dark[i] else run + 1
        if run >= HIT_MIN_LIT_FRAMES:
            return True
    return False


@pytest.mark.parametrize("template_id", ["mirror_wings", "target_orbit", "fly_in_cascade"])
@pytest.mark.parametrize("kind", RIGS)
def test_sparse_darkens_half_the_heads_in_turn_on_the_variants_cycle(
    kind: str, template_id: str
) -> None:
    """Unit 0 of the variant's cycle: the outer pair lit, the inner dark; unit 1 the other
    way. Mirror partners stay together, the lit half plays as BALANCED, and every head is
    lit at least once."""
    sparse = play([m.plan_section("s1", 1, 8, template_id, density="SPARSE")], kind)
    plain = play([m.plan_section("s1", 1, 8, template_id)], kind)
    frames, base = Frames(sparse), Frames(plain)
    entry = density_of(sparse)
    assert entry["alternates"] == "cycle"
    assert entry["cycle_bars"] == 2.0
    units = unit_frames(grid(120), 1, entry["cycle_bars"], entry["units"])
    for k, unit in enumerate(units):
        dark, lit = (ODD, EVEN) if k % 2 == 0 else (EVEN, ODD)
        for head in dark:
            assert all(frames.dark(head)[i] for i in unit), (k, head)
        for head in lit:
            assert [frames.raw(head)[i] for i in unit] == [base.raw(head)[i] for i in unit]
    for a, b in (EVEN, ODD):
        assert frames.dimmer(a) == frames.dimmer(b)
    whole = frames_of(grid(120), 1, 8)
    for head in HEADS:
        assert shown(frames.dark(head), whole), head
        before, after = entry["lit_share"][head]
        assert after < before
    assert_physical(sparse, plain)


@pytest.mark.parametrize("kind", RIGS)
def test_sparse_phases_on_the_variant_the_part_plays(kind: str) -> None:
    """The cycle is the played variant's, as the compiler places it (`whole_period_cycle`):
    a section naming `slow` alternates on `slow`'s cycle."""
    sparse = play([m.plan_section("s1", 1, 8, "mirror_wings", "slow", density="SPARSE")], kind)
    document = get_template("mirror_wings")
    preset = next(p for p in document.presets if p.preset_id == "slow")
    cycle = whole_period_cycle(apply_preset(document.template, preset), 4).repeat.cycle_bars
    assert density_of(sparse)["cycle_bars"] == float(Fraction(repr(cycle)))


@pytest.mark.parametrize("kind", RIGS)
def test_a_part_of_one_cycle_swaps_every_half_cycle(kind: str) -> None:
    """A part of one cycle would leave the dark half never lit: it swaps every half cycle,
    traced with why."""
    sparse = play(
        [
            m.plan_section("s1", 1, 2, "mirror_wings", density="SPARSE"),
            m.plan_section("s2", 3, 8, "target_orbit"),
        ],
        kind,
    )
    entry = density_of(sparse)
    assert entry["alternates"] == "half cycle"
    assert entry["fallback"] == [
        f"every cycle: {', '.join(ODD)} would never be lit for 3 frames running"
    ]
    frames = Frames(sparse)
    for head in HEADS:
        assert shown(frames.dark(head), frames_of(grid(120), 1, 2)), head


@pytest.mark.parametrize("kind", RIGS)
def test_a_once_template_plays_its_move_lit_on_every_head_and_alternates_its_hold(
    kind: str,
) -> None:
    sparse = play([m.plan_section("s1", 1, 8, "finite_snap_hold", density="SPARSE")], kind)
    plain = play([m.plan_section("s1", 1, 8, "finite_snap_hold")], kind)
    frames, base = Frames(sparse), Frames(plain)
    entry = density_of(sparse)
    assert entry["cycle_bars"] == 1.0
    units = unit_frames(grid(120), 1, 1.0, entry["units"])
    for head in HEADS:
        assert [frames.raw(head)[i] for i in units[0]] == [base.raw(head)[i] for i in units[0]]
    for k, unit in enumerate(units[1:], start=1):
        dark = EVEN if k % 2 else ODD
        for head in dark:
            assert all(frames.dark(head)[i] for i in unit), (k, head)


def test_sparse_on_one_mirror_pair_plays_balanced_and_repair_says_so() -> None:
    pair = ("MH1", "MH2")
    fg = m.family_rig(pair)

    def render(density: str) -> RenderingPipeline:
        pipeline = RenderingPipeline(
            choreography_plan=ChoreographyPlan(
                sections=[m.plan_section("s1", 1, 8, "mirror_wings", density=density)],
                overall_strategy="",
            ),
            beat_grid=grid(120),
            fixture_group=fg,
            job_config=m.family_job(pair),
            media_file="silence.wav",
        )
        pipeline.render()
        return pipeline

    sparse, plain = render("SPARSE"), render("BALANCED")
    assert sparse.frames == plain.frames
    entry = density_of(sparse)
    assert entry["plays"] == "BALANCED"
    assert sparse.render_record is not None
    assert any(
        "density SPARSE plays BALANCED" in d["message"] for d in sparse.render_record["diagnostics"]
    )
    section = m.plan_section("s1", 1, 8, "mirror_wings", density="SPARSE")
    repaired = repair_rig_intent(
        ChoreographyPlan(sections=[section], overall_strategy=""),
        rig_offer(fg, grid(120)),
        {},
        grid(120),
    )
    assert any(
        r.item == "density SPARSE" and "plays as BALANCED" in r.reason for r in repaired.repairs
    )


EVENTS = [
    event(2, 2, "hit"),
    event(3, 3, "color", color="red"),
    event(5, 1, "strobe_medium"),
    event(6, 1, "open"),
    event(7, 3, "gobo", gobo="dots"),
]


@pytest.mark.parametrize("template_id", ["mirror_wings", "target_orbit"])
@pytest.mark.parametrize("kind", RIGS)
def test_sparse_never_makes_a_planner_event_worse(kind: str, template_id: str) -> None:
    """Every head plays as BALANCED over each event's widened seen span: no event is lost,
    moved, revealed later or shown more briefly than at BALANCED."""
    sparse = play([m.plan_section("s1", 1, 8, template_id, events=EVENTS, density="SPARSE")], kind)
    plain = play([m.plan_section("s1", 1, 8, template_id, events=EVENTS)], kind)
    assert sparse.render_record is not None and plain.render_record is not None
    assert worse(plain, sparse) == []
    assert density_of(sparse)["plays"].startswith("half the heads dark")
    assert_physical(sparse, plain)


def test_sparse_leaves_a_head_that_cannot_go_dark_lit_and_says_so() -> None:
    fg = _no_dark_profile_rig()
    profiles = {f.fixture_id: f.config.physical_profile for f in fg.expand_fixtures()}
    lit = ContinuousTrajectory(
        unit="normalized", points=(PhysicalPoint(t_ms=0, value=1.0),), interpolation="hold"
    )
    opened = DiscreteTrajectory(events=(DiscretePoint(t_ms=0, state="open"),))
    cues = [
        m.fixture_segment(
            {ChannelName.DIMMER: lit, ChannelName.SHUTTER: opened},
            fixture_id=head,
            t0_ms=0,
            t1_ms=8000,
            section_id="s1",
        )
        for head in HEADS
    ]
    played, entry = play_sparse(
        cues,
        window=(0, 8000),
        cycle_bars=Fraction(1),
        once=False,
        at_bars=lambda bars: float(bars) * 2000,
        halves=(EVEN, ODD),
        protected=[],
        profiles=profiles,  # type: ignore[arg-type]
        darken=lambda own, spans: _dark_over_spans(own, spans, profiles, shortest_lit_ms=40),  # type: ignore[arg-type]
        snap=lambda spans: spans,
        shortest_dark_ms=0,
    )
    assert entry.get("alternates") == "cycle", entry
    assert list(entry["lit"]) == ["MH2"]
    assert next(c for c in played if c.fixture_id == "MH2") == cues[1]


@pytest.mark.parametrize("mode", MODES)
@pytest.mark.parametrize("kind", RIGS)
def test_transitions_into_and_out_of_sparse_keep_their_windows(kind: str, mode: str) -> None:
    """SPARSE is not an event: a transition into or out of it keeps its whole window; a head
    SPARSE darkens is a dark look the transition hands over to."""
    sparse = play(three("SPARSE", mode), kind, bars=12)
    plain = play(three("BALANCED", mode), kind, bars=12)
    assert windows(sparse) == windows(plain)
    for _, (start, end) in windows(sparse):
        assert abs((end - start) - 2000) <= FRAME
    assert_physical(sparse)


@pytest.mark.parametrize("level", ["SPARSE", "BUSY"])
def test_a_density_that_makes_the_song_worse_gives_way_to_balanced(
    level: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """SPARSE and BUSY are arrangement units: where `worse` finds an event worse with the
    density as planned, the section plays BALANCED's frames, traced with the event."""
    from twinklr.core.sequencer.moving_heads import pipeline as module

    judged = module.worse

    def worse(reference: RenderingPipeline, trial: RenderingPipeline) -> list[str]:
        if trial.unit_choice("density:s1") == "planned":
            return ["its hit at bar 2 beat 1 in section 's1' (lost on MH1)"]
        return judged(reference, trial)

    monkeypatch.setattr(module, "worse", worse)

    def render(density: str) -> RenderingPipeline:
        pipeline = RenderingPipeline(
            choreography_plan=ChoreographyPlan(
                sections=[m.plan_section("s1", 1, 8, "mirror_wings", density=density)],
                overall_strategy="",
            ),
            beat_grid=grid(120),
            fixture_group=rig(),
            job_config=m.family_job(HEADS),
            media_file="silence.wav",
        )
        pipeline.render()
        return pipeline

    gave_way, plain = render(level), render("BALANCED")
    assert gave_way.frames == plain.frames
    assert density_of(gave_way) == {
        "level": level,
        "gave_way": "density gave way to its hit at bar 2 beat 1 in section 's1' (lost on MH1)",
    }
    assert gave_way.arrangement_renders == 2  # the reference, and the density tried


def test_rest_is_not_an_arrangement_unit(monkeypatch: pytest.MonkeyPatch) -> None:
    """REST is dark by definition: it never gives way and takes no trial render."""
    from twinklr.core.sequencer.moving_heads import pipeline as module

    monkeypatch.setattr(module, "worse", lambda reference, trial: ["anything"])
    pipeline = RenderingPipeline(
        choreography_plan=ChoreographyPlan(
            sections=[m.plan_section("s1", 1, 8, "mirror_wings", density="REST")],
            overall_strategy="",
        ),
        beat_grid=grid(120),
        fixture_group=rig(),
        job_config=m.family_job(HEADS),
        media_file="silence.wav",
    )
    pipeline.render()
    assert pipeline.arrangement_renders == 0
    assert density_of(pipeline)["plays"] == "dark"


@pytest.mark.parametrize("template_id", ["mirror_wings", "fly_in_cascade"])
@pytest.mark.parametrize("kind", RIGS)
def test_rest_plays_every_hit_on_every_head_that_plays_it_at_balanced(
    kind: str, template_id: str
) -> None:
    """REST enters as BALANCED does (its boundary and entry decided on the BALANCED cues),
    so a hit inside it finds the same cues: on its section's first downbeat (where the
    heads reposition and it moves) and mid-section, every head that plays it at BALANCED
    plays it, lit from REST's darkness; and every head of the rig has an outcome."""

    def plan(density: str) -> list[PlanSection]:
        return [
            m.plan_section(
                "s1", 1, 4, "target_orbit", color="red", gobo="dots", events=[event(3, 1, "hit")]
            ),
            m.plan_section(
                "s2",
                5,
                8,
                template_id,
                density=density,
                events=[event(5, 1, "hit"), event(7, 3, "hit")],
            ),
        ]

    rested, plain = play(plan("REST"), kind), play(plan("BALANCED"), kind)
    assert [said for said in worse(plain, rested) if "hit" in said] == []
    assert rested.render_record is not None
    for look in rested.render_record["section_looks"]:
        for entry in look.get("events", []):
            assert set(entry["heads"]) == set(HEADS), entry


@pytest.mark.parametrize("kind", RIGS)
def test_sparse_keeps_off_a_transition_that_plays_at_balanced(kind: str) -> None:
    """The owner-rig case: an ENTRY crossfade into SPARSE on target_orbit plays on every
    head it plays on at BALANCED, the heads lit as BALANCED through its window, and the
    trace's played status is the frames' (the render without transitions keeps off the
    same window)."""
    entering = [transition("crossfade")]

    def plan(density: str) -> list[PlanSection]:
        return [
            m.plan_section("s1", 1, 4, "mirror_wings"),
            m.plan_section("s2", 5, 8, "target_orbit", density=density, transitions=entering),
        ]

    sparse, plain = play(plan("SPARSE"), kind), play(plan("BALANCED"), kind)
    assert density_of(sparse, "s2")["alternates"] == "cycle"
    ((_, (start, end)),) = windows(sparse)
    assert windows(sparse) == windows(plain)
    assert sparse.render_record is not None and plain.render_record is not None

    def played(pipeline: RenderingPipeline) -> dict[str, str]:
        assert pipeline.render_record is not None
        (entry,) = [
            t
            for look in pipeline.render_record["section_looks"]
            for t in look.get("transitions", [])
        ]
        return {h: o.get("plays", "not played")[:8] for h, o in entry["heads"].items()}

    assert played(sparse) == played(plain)
    for head in HEADS:
        a, b = Frames(sparse).raw(head), Frames(plain).raw(head)
        assert a[start // FRAME : end // FRAME] == b[start // FRAME : end // FRAME], head
    assert worse(plain, sparse) == []


@pytest.mark.parametrize("kind", RIGS)
def test_sparse_keeps_a_colour_lit_from_the_section_before(kind: str) -> None:
    """A colour change in the previous section still lit as SPARSE starts plays its whole
    lit run there: never shown more briefly, so SPARSE need not give way."""

    def plan(density: str) -> list[PlanSection]:
        return [
            m.plan_section("s1", 1, 4, "mirror_wings", events=[event(4, 1, "color", color="red")]),
            m.plan_section("s2", 5, 8, "mirror_wings", density=density),
        ]

    sparse, plain = play(plan("SPARSE"), kind), play(plan("BALANCED"), kind)
    assert worse(plain, sparse) == []
    assert "gave_way" not in density_of(sparse, "s2")
