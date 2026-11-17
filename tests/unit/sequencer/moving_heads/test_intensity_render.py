"""The planner's intensity played on the dimmer (song-intent rendering W5), asserted on
encoded frames: the identity levels render the authored bytes; DRAMATIC and INTENSE
pulse on the beat (a dip-and-return where the template holds the dimmer full), leave
the dark frames and every other channel alone, compose with dark spans and colour dips,
respect the dimmer's declared speed and latency, and cannot pulse without a dimmer axis;
under `twinklr show` the heads' focal role adjusts the section's intensity."""

from __future__ import annotations

from collections.abc import Iterator, Sequence
from itertools import pairwise
import math
from typing import Any

import pytest

from tests.support import moving_heads as m
from twinklr.core.agents.sequencer.moving_heads.models import ChoreographyPlan
from twinklr.core.config.fixtures import FixtureCapabilities, FixtureGroup
from twinklr.core.formats.xlights.sequence.fresh import EFFECT_GRID_MS
from twinklr.core.sequencer.moving_heads.export.frame_encoder import quantize_cue
from twinklr.core.sequencer.moving_heads.intensity import (
    ACCENT,
    FULL_BLEND,
    SHAPES,
    dramatic_period_beats,
    effective_intensity,
)
from twinklr.core.sequencer.moving_heads.pipeline import RenderingPipeline
from twinklr.core.sequencer.timing.beat_grid import BeatGrid

HEADS = ("MH1", "MH2", "MH3", "MH4")
FRAME = EFFECT_GRID_MS
HALF = "intensity_half_hold"
"""Test-only: one held aim, the dimmer held at half."""


RAMP = "intensity_ramp"
"""Test-only: lit over three quarters of a 4-beat sweep, ramping up from dark to full over
its first beat and down over its last."""
STRONG_PULSE = "intensity_strong_pulse"
"""Test-only: the template's own pulse, full and 0.6 on alternate beats."""
NEAR_FULL = "intensity_near_full"
"""Test-only: the dimmer held at 0.9."""


def _held(step_id: str, low: float, high: float, period: float, duty: float) -> dict[str, Any]:
    return m.hold_step(
        step_id,
        10.0,
        dimmer={"period_beats": period, "duty_cycle": duty, "low": low, "high": high},
    )


@pytest.fixture(autouse=True)
def _catalog() -> Iterator[None]:
    ramp = m.envelope_step("ramp", 10.0, 20.0, lit=(0.0, 0.75), attack=1.0, release=1.0)
    with (
        m.family_catalog(),
        m.registered_templates(
            m.loop_template_doc(HALF, [_held("hold", 0.0, 0.5, 4.0, 1.0)]),
            m.loop_template_doc(RAMP, [ramp]),
            m.loop_template_doc(STRONG_PULSE, [_held("pulse", 0.6, 1.0, 2.0, 0.5)]),
            m.loop_template_doc(NEAR_FULL, [_held("near", 0.0, 0.9, 4.0, 1.0)]),
        ),
    ):
        yield


def grid(bpm: float, bars: int = 8, beats_per_bar: int = 4) -> BeatGrid:
    """`bars` bars at `bpm`, the first beat 15 ms off the frame grid."""
    beat = 60_000 / bpm
    beats = [15.0 + i * beat for i in range(beats_per_bar * bars + 1)]
    return BeatGrid(
        bar_boundaries=beats[::beats_per_bar],
        beat_boundaries=beats,
        eighth_boundaries=BeatGrid._calculate_eighth_boundaries(beats),
        sixteenth_boundaries=BeatGrid._calculate_sixteenth_boundaries(beats),
        tempo_bpm=bpm,
        beats_per_bar=beats_per_bar,
        duration_ms=beats[-1] + 15.0,
    )


def render(
    intensity: str | None,
    *,
    template_id: str = "mirror_wings",
    beat_grid: BeatGrid | None = None,
    fixture_group: FixtureGroup | None = None,
    sections: Sequence[dict[str, Any]] | None = None,
    **pipeline_fields: Any,
) -> RenderingPipeline:
    """One section over bars 1-8 (or `sections`, each its plan fields), `intensity` set."""
    plan_sections = (
        [m.plan_section("s1", 1, 8, template_id, intensity=intensity)]
        if sections is None
        else [m.plan_section(**fields) for fields in sections]
    )
    pipeline = RenderingPipeline(
        choreography_plan=ChoreographyPlan(sections=plan_sections, overall_strategy=""),
        beat_grid=beat_grid or grid(120),
        fixture_group=fixture_group or m.family_rig(HEADS),
        job_config=m.family_job(HEADS),
        media_file="silence.wav",
        **pipeline_fields,
    )
    pipeline.render()
    return pipeline


class Heads:
    """Each head's encoded frames, read through its profile."""

    def __init__(self, pipeline: RenderingPipeline) -> None:
        fixtures = pipeline.fixture_group.expand_fixtures()
        profile = fixtures[0].config.physical_profile
        assert isinstance(profile, FixtureCapabilities)
        self.profile = profile
        self.frames = {
            head: [dict(f.channels) for f in pipeline.frames if f.fixture_id == head]
            for head in HEADS
        }
        dimmer = profile.axes.get("dimmer")
        self.offset = None if dimmer is None else dimmer.coarse_offset

    def dimmer(self, head: str) -> list[int]:
        assert self.offset is not None
        return [frame[self.offset] for frame in self.frames[head]]

    def dark(self, head: str) -> list[bool]:
        visibility = self.profile.visibility
        shutter = self.profile.discrete["shutter"]
        names = {state.value: name for name, state in shutter.states.items()}
        return [
            (visibility.dimmer_zero_extinguishes and frame.get(self.offset or 0) == 0)
            or names[frame[shutter.offset]] in visibility.extinguishing_shutter_states
            for frame in self.frames[head]
        ]

    def others(self, head: str) -> list[dict[int, int]]:
        return [{k: v for k, v in frame.items() if k != self.offset} for frame in self.frames[head]]


def lit_beats(heads: Heads, head: str, beats: Sequence[float]) -> list[float]:
    """The beats the head is lit across (two frames before to two after)."""
    dark = heads.dark(head)
    return [
        beat
        for beat in beats
        if all(
            0 <= i < len(dark) and not dark[i]
            for i in range(math.floor(beat / FRAME) - 2, math.floor(beat / FRAME) + 3)
        )
    ]


def accent_frame(beat: float, lead_ms: int = 0) -> int:
    """The frame nearest `beat - lead_ms` (as the compiler places a template's own beat
    edges): where the accent is commanded."""
    return quantize_cue(round(beat - lead_ms)).actual_ms // FRAME


def assert_same_but_dimmer(shaped: Heads, authored: Heads) -> None:
    for head in HEADS:
        assert shaped.dark(head) == authored.dark(head), f"{head}: darkness changed"
        assert shaped.others(head) == authored.others(head), f"{head}: not only the dimmer"


# --- the table ----------------------------------------------------------------------


@pytest.mark.parametrize(
    ("beats_per_bar", "period"), [(4, 2), (3, 3), (2, 2), (6, 3), (5, 5), (8, 4)]
)
def test_dramatic_accents_on_the_half_bar_or_the_bar(beats_per_bar: int, period: int) -> None:
    assert dramatic_period_beats(beats_per_bar) == period


@pytest.mark.parametrize(
    ("asked", "role", "effective"),
    [
        (None, "LEAD", "DRAMATIC"),
        ("SLOW", "LEAD", "DRAMATIC"),
        ("SMOOTH", "LEAD", "DRAMATIC"),
        ("FAST", "LEAD", "DRAMATIC"),
        ("DRAMATIC", "LEAD", "INTENSE"),
        ("INTENSE", "LEAD", "INTENSE"),
        ("DRAMATIC", "SUPPORT", "DRAMATIC"),
        (None, "SUPPORT", None),
        ("INTENSE", "REST", None),
        ("DRAMATIC", "REST", None),
        ("FAST", "REST", "FAST"),
        ("INTENSE", None, "INTENSE"),
    ],
)
def test_the_focal_role_moves_intensity_one_step(
    asked: str | None, role: str | None, effective: str | None
) -> None:
    assert effective_intensity(asked, role) == effective


# --- identity -----------------------------------------------------------------------


@pytest.mark.parametrize("level", ["SMOOTH", "SLOW", "FAST"])
@pytest.mark.parametrize("template_id", ["mirror_wings", "fly_in_cascade", HALF])
def test_identity_levels_render_the_authored_bytes(level: str, template_id: str) -> None:
    authored = render(None, template_id=template_id)
    played = render(level, template_id=template_id)

    assert played.frames == authored.frames


# --- shaped levels --------------------------------------------------------------------


@pytest.mark.parametrize("bpm", [120.0, 78.0])
def test_intense_on_a_full_family_dips_between_beats_and_returns_on_each(bpm: float) -> None:
    beat_grid = grid(bpm)
    authored = Heads(render(None, beat_grid=beat_grid))
    shaped = Heads(render("INTENSE", beat_grid=beat_grid))

    assert_same_but_dimmer(shaped, authored)
    floor = math.floor(SHAPES["INTENSE"].full_floor * 255)
    for head in HEADS:
        dimmer, dark = shaped.dimmer(head), shaped.dark(head)
        lit = [i for i, is_dark in enumerate(dark) if not is_dark]
        assert all(dimmer[i] >= floor for i in lit), head
        assert all(authored.dimmer(head)[i] == 255 for i in lit)
        beats = lit_beats(shaped, head, beat_grid.beat_boundaries)
        assert len(beats) >= 20
        for beat in beats:
            at = accent_frame(beat)
            assert dimmer[at] == 255, (head, beat)
            assert dimmer[at - 1] < 255 and dimmer[at + 1] < 255, (head, beat)


@pytest.mark.parametrize(("beats_per_bar", "period"), [(4, 2), (3, 3)])
def test_dramatic_on_a_full_family_is_shallower_over_its_longer_period(
    beats_per_bar: int, period: int
) -> None:
    beat_grid = grid(120, beats_per_bar=beats_per_bar)
    authored = Heads(render(None, beat_grid=beat_grid))
    shaped = Heads(render("DRAMATIC", beat_grid=beat_grid))
    intense = Heads(render("INTENSE", beat_grid=beat_grid))

    assert_same_but_dimmer(shaped, authored)
    floor = math.floor(SHAPES["DRAMATIC"].full_floor * 255)
    for head in HEADS:
        dimmer = shaped.dimmer(head)
        lit = [i for i, is_dark in enumerate(shaped.dark(head)) if not is_dark]
        assert min(dimmer[i] for i in lit) >= floor > min(intense.dimmer(head)[i] for i in lit)
        for index, beat in enumerate(beat_grid.beat_boundaries):
            if beat not in lit_beats(shaped, head, beat_grid.beat_boundaries):
                continue
            accented = index % period == 0
            at = accent_frame(beat)
            assert (dimmer[at] == 255 and dimmer[at - 1] < 255) is accented, (head, index)


@pytest.mark.parametrize("level", ["DRAMATIC", "INTENSE"])
def test_a_held_level_with_headroom_rises_and_never_drops_below_it(level: str) -> None:
    authored = Heads(render(None, template_id=HALF))
    shaped = Heads(render(level, template_id=HALF))

    assert_same_but_dimmer(shaped, authored)
    shape = SHAPES[level]
    for head in HEADS:
        lit = [i for i, is_dark in enumerate(shaped.dark(head)) if not is_dark]
        dimmer, base = shaped.dimmer(head), authored.dimmer(head)
        assert all(dimmer[i] >= round(base[i] * (1 + shape.floor_gain)) - 1 for i in lit)
        assert max(dimmer[i] for i in lit) >= round(
            128 * (1 + shape.floor_gain + shape.peak_gain) * 0.97
        )


# --- composition ----------------------------------------------------------------------


def test_a_dark_span_stays_dark_under_intensity() -> None:
    spans = ((2000, 3000),)
    authored = Heads(render(None, dark_spans=spans))
    shaped = Heads(render("INTENSE", dark_spans=spans))

    assert_same_but_dimmer(shaped, authored)
    for head in HEADS:
        assert all(shaped.dimmer(head)[i] == 0 for i in range(100, 150))


def test_a_colour_dip_at_a_lit_boundary_stays_dark_under_intensity() -> None:
    sections = [
        {"section_id": "s1", "start_bar": 1, "end_bar": 4, "template_id": "mirror_wings"},
        {"section_id": "s2", "start_bar": 5, "end_bar": 8, "template_id": "mirror_wings"},
    ]
    colours = [{**sections[0], "color": "red"}, {**sections[1], "color": "blue"}]
    authored = render(None, fixture_group=m.tagged_family_rig(HEADS), sections=colours)
    shaped = render(
        None,
        fixture_group=m.tagged_family_rig(HEADS),
        sections=[{**section, "intensity": "INTENSE"} for section in colours],
    )

    assert authored.render_record is not None and shaped.render_record is not None
    assert any("boundaries" in look for look in authored.render_record["section_looks"])
    assert_same_but_dimmer(Heads(shaped), Heads(authored))


# --- physical limits ------------------------------------------------------------------


def _rig_with_dimmer(**axis: Any) -> FixtureGroup:
    payload = m.family_rig(HEADS).model_dump(mode="json")
    for fixture in payload["fixtures"]:
        fixture["config"]["physical_profile"]["axes"]["dimmer"].update(axis)
    return FixtureGroup.model_validate(payload)


def test_a_slow_dimmer_gets_a_smaller_pulse_it_can_follow() -> None:
    speed = 4.0  # normalized units per second: 0.08 per frame
    rig = _rig_with_dimmer(travel_speed_per_s=speed)
    authored = Heads(render(None, fixture_group=rig))
    pipeline = render("INTENSE", fixture_group=rig)
    shaped = Heads(pipeline)

    assert_same_but_dimmer(shaped, authored)
    step = math.ceil(speed * FRAME / 1000 * 255) + 1
    for head in HEADS:
        dimmer, dark = shaped.dimmer(head), shaped.dark(head)
        steps = [
            abs(dimmer[i] - dimmer[i - 1])
            for i in range(1, len(dimmer))
            if not dark[i] and not dark[i - 1]
        ]
        assert 0 < max(steps) <= step, head
    assert pipeline.render_record is not None
    (look,) = pipeline.render_record["section_looks"]
    degraded = look["intensity"]["shape"]["degraded"]
    assert set(degraded) == set(HEADS)
    assert all(0 < scale < 1 for scale in degraded.values())


def test_a_dimmer_latency_moves_the_accent_earlier_by_it() -> None:
    beat_grid = grid(120)
    pipeline = render("INTENSE", fixture_group=_rig_with_dimmer(latency_ms=40), beat_grid=beat_grid)
    shaped = Heads(pipeline)

    for head in HEADS:
        dimmer = shaped.dimmer(head)
        for beat in lit_beats(shaped, head, beat_grid.beat_boundaries)[1:]:
            assert dimmer[accent_frame(beat, 40)] == 255
            assert dimmer[accent_frame(beat, 40) - 1] < 255
    assert pipeline.render_record is not None
    (look,) = pipeline.render_record["section_looks"]
    assert look["intensity"]["shape"]["lead_ms"] == dict.fromkeys(HEADS, 40)


def test_a_head_without_a_dimmer_axis_plays_as_authored_and_says_so() -> None:
    payload = m.family_rig(HEADS, presets=False).model_dump(mode="json")
    for fixture in payload["fixtures"]:
        profile = fixture["config"]["physical_profile"]
        profile["axes"].pop("dimmer")
        profile["visibility"]["dimmer_zero_extinguishes"] = False
    rig = FixtureGroup.model_validate(payload)
    authored = render(None, template_id="fly_in_cascade", fixture_group=rig)
    shaped = render("INTENSE", template_id="fly_in_cascade", fixture_group=rig)

    assert shaped.frames == authored.frames
    assert shaped.render_record is not None
    (look,) = shaped.render_record["section_looks"]
    assert look["intensity"]["shape"]["unavailable"] == list(HEADS)
    assert any(
        "is not shaped on MH1, MH2, MH3, MH4" in d["message"]
        for d in shaped.render_record["diagnostics"]
    )


# --- trace and the show's focal role ---------------------------------------------------


def test_the_trace_records_what_intensity_played() -> None:
    pipeline = render("DRAMATIC")

    assert pipeline.render_record is not None
    (look,) = pipeline.render_record["section_looks"]
    assert look["intensity"] == {
        "asked": "DRAMATIC",
        "effective": "DRAMATIC",
        "shape": {
            "period_beats": 2,
            "decay_beats": 1.0,
            "floor_gain": SHAPES["DRAMATIC"].floor_gain,
            "peak_gain": SHAPES["DRAMATIC"].peak_gain,
            "full_floor": SHAPES["DRAMATIC"].full_floor,
            "full_peak": SHAPES["DRAMATIC"].full_peak,
            "full_blend": list(FULL_BLEND),
            "applied": {"dip_and_return": list(HEADS)},
        },
    }
    assert "focal_roles" not in pipeline.render_record


def test_a_lead_section_plays_one_step_hotter_and_rest_as_authored() -> None:
    authored = render(None)
    lead = render(None, focal_roles={"s1": "LEAD"})
    dramatic = render("DRAMATIC")
    rest = render("INTENSE", focal_roles={"s1": "REST"})

    assert lead.frames == dramatic.frames != authored.frames
    assert rest.frames == authored.frames
    assert lead.render_record is not None
    (look,) = lead.render_record["section_looks"]
    assert look["intensity"]["focal_role"] == "LEAD"
    assert look["intensity"]["effective"] == "DRAMATIC"
    assert lead.render_record["focal_roles"] == {"s1": "LEAD"}
    assert lead.checkpoint_record()["focal_roles"] == {"s1": "LEAD"}
    support = render(None, focal_roles={"s1": "SUPPORT"})
    # Only a role that changes the section's intensity is render identity and recorded.
    assert support.fingerprint() == authored.fingerprint() != lead.fingerprint()
    assert support.render_record is not None and "focal_roles" not in support.render_record
    assert "section_looks" not in support.render_record


# --- review fix round: lit runs, run shapes, quantisation, limits ---------------------------


def lit_runs(heads: Heads, head: str) -> list[range]:
    """The head's runs of consecutive lit frames."""
    dark = heads.dark(head)
    runs, start = [], None
    for i, is_dark in enumerate([*dark, True]):
        if not is_dark and start is None:
            start = i
        elif is_dark and start is not None:
            runs.append(range(start, i))
            start = None
    return runs


def variable_grid(bars: int = 8) -> BeatGrid:
    """A 4/4 grid whose tempo drifts beat by beat between 90 and 150 BPM (the W5
    re-review's variable grid), the first beat 7 ms off the frame grid."""
    beats = [7.0]
    for i in range(4 * bars):
        beats.append(beats[-1] + 60_000 / (120 + 30 * math.sin(i / (4 * bars) * 2 * math.pi)))
    return BeatGrid(
        bar_boundaries=beats[::4],
        beat_boundaries=beats,
        eighth_boundaries=BeatGrid._calculate_eighth_boundaries(beats),
        sixteenth_boundaries=BeatGrid._calculate_sixteenth_boundaries(beats),
        tempo_bpm=120.0,
        beats_per_bar=4,
        duration_ms=beats[-1] + 15.0,
    )


GRIDS = {
    "120": lambda: grid(120),
    "78": lambda: grid(78),
    "140": lambda: grid(140),
    "170": lambda: grid(170),
    "variable": variable_grid,
}


@pytest.mark.parametrize("tempo", list(GRIDS))
@pytest.mark.parametrize("level", ["DRAMATIC", "INTENSE"])
@pytest.mark.parametrize("template_id", ["fly_in_cascade", "fly_out_cascade"])
def test_every_lit_window_of_a_cascade_comes_in_on_an_accent(
    level: str, template_id: str, tempo: str
) -> None:
    """A cascade lights each head for about a beat in four, often on a beat DRAMATIC does
    not accent: every lit window comes in full (on its first frame, or on a beat a few
    frames after it) and eases off, on every head, and never rises on its last two frames
    (no flash just before it goes dark), at any tempo."""
    beat_grid = GRIDS[tempo]()
    authored = Heads(render(None, template_id=template_id, beat_grid=beat_grid))
    shaped = Heads(render(level, template_id=template_id, beat_grid=beat_grid))

    assert_same_but_dimmer(shaped, authored)
    floor = math.floor(SHAPES[level].full_floor * 255)
    shortest = min(b - a for a, b in pairwise(beat_grid.beat_boundaries))
    near = math.floor(shortest * ACCENT.near_beat_beats / FRAME) + 1
    for head in HEADS:
        dimmer = shaped.dimmer(head)
        runs = lit_runs(shaped, head)
        assert len(runs) >= 6, head
        for run in runs:
            assert max(dimmer[i] for i in run[:near]) == 255, (head, run[0] * FRAME)
            assert min(dimmer[i] for i in run) >= floor, head
            assert dimmer[run[-1]] <= dimmer[run[-2]] <= dimmer[run[-3]], (head, run[-1] * FRAME)


def test_a_reveal_just_before_a_beat_takes_the_beat_accent() -> None:
    """A head revealed two frames before a beat comes in on that beat's accent: one hit on
    the beat, not one on the reveal and another two frames later."""
    beat_grid = grid(120)
    shaped = Heads(render("INTENSE", beat_grid=beat_grid, dark_spans=((2000, 2480),)))

    beat = accent_frame(beat_grid.beat_boundaries[5])  # 2515 ms: frame 2520
    assert beat * FRAME == 2520
    for head in HEADS:
        dimmer, dark = shaped.dimmer(head), shaped.dark(head)
        reveal = next(i for i in range(100, len(dark)) if dark[i - 1] and not dark[i])
        assert reveal * FRAME == 2480
        assert dimmer[reveal] < 255 and dimmer[reveal + 1] < 255 and dimmer[beat] == 255
        after = [dimmer[i] for i in range(beat, beat + 20)]
        assert after == sorted(after, reverse=True), head


FLICKS = "intensity_flicks"
"""Test-only: lit for a quarter beat, dark for a quarter beat, at full."""


def test_short_flicks_keep_the_beat() -> None:
    """Lit runs shorter than a beat with short gaps between follow the beat accents: the
    level is full only on the beats, not at the start of every flick."""
    beat_grid = grid(120)
    with m.registered_templates(m.loop_template_doc(FLICKS, [_held("f", 0.0, 1.0, 0.5, 0.5)])):
        authored = Heads(render(None, template_id=FLICKS, beat_grid=beat_grid))
        shaped = Heads(render("INTENSE", template_id=FLICKS, beat_grid=beat_grid))

    assert_same_but_dimmer(shaped, authored)
    beats = {accent_frame(beat) for beat in beat_grid.beat_boundaries}
    for head in HEADS:
        dimmer = shaped.dimmer(head)
        runs = lit_runs(shaped, head)
        assert len(runs) >= 40, head
        full = {i for run in runs for i in run if dimmer[i] == 255}
        assert full and full <= beats, (head, sorted(full - beats)[:5])
        assert sum(1 for run in runs if dimmer[run[0]] < 255) >= len(runs) // 3, head


SWEEP = [round(0.5 + 0.05 * i, 2) for i in range(11)]
"""Held authored levels from 0.5 to 1.0."""


@pytest.mark.parametrize("level", ["DRAMATIC", "INTENSE"])
def test_the_shaped_level_has_no_jump_as_the_authored_level_nears_full(level: str) -> None:
    """Held levels from 0.5 to 1.0: below the blend band the light never plays under the
    template, at full it plays the dip-and-return, and the mean lit level moves by at most
    0.07 per 0.05 of authored level: no jump where a single threshold used to be (W5
    re-review N3: 0.84 → 0.917 and 0.86 → 0.638 under INTENSE)."""
    docs = [
        m.loop_template_doc(f"held_{held}", [_held("h", 0.0, held, 4.0, 1.0)]) for held in SWEEP
    ]
    means: list[float] = []
    with m.registered_templates(*docs):
        for held, doc in zip(SWEEP, docs, strict=True):
            template_id = doc.template.template_id
            authored = Heads(render(None, template_id=template_id))
            shaped = Heads(render(level, template_id=template_id))
            assert_same_but_dimmer(shaped, authored)
            dimmer, base = shaped.dimmer("MH1"), authored.dimmer("MH1")
            lit = [i for run in lit_runs(shaped, "MH1") for i in run]
            if held <= FULL_BLEND[0]:
                assert all(dimmer[i] >= base[i] for i in lit), held
            means.append(sum(dimmer[i] for i in lit) / len(lit) / 255)
    assert all(abs(b - a) <= 0.07 for a, b in pairwise(means)), [round(v, 3) for v in means]
    assert SHAPES[level].full_floor <= means[-1] < means[SWEEP.index(FULL_BLEND[0])]


@pytest.mark.parametrize("level", ["DRAMATIC", "INTENSE"])
def test_a_head_revealed_after_a_dark_span_mid_beat_comes_in_full(level: str) -> None:
    spans = ((2000, 2260),)  # ends half a beat before the beat at 2515 ms
    shaped = Heads(render(level, dark_spans=spans))

    for head in HEADS:
        dimmer, dark = shaped.dimmer(head), shaped.dark(head)
        reveal = next(i for i in range(100, len(dark)) if dark[i - 1] and not dark[i])
        assert reveal * FRAME == 2260
        assert dimmer[reveal] == 255 and dimmer[reveal + 1] < 255, head


def test_a_head_revealed_after_a_colour_dip_at_170_bpm_comes_in_full() -> None:
    """At 170 BPM a colour change at a lit boundary dips dark before the section: the
    reveal on the section's downbeat is at full on its first frame, never a frame at the
    floor before the accent."""
    colours = ("red", "blue", "red")
    sections = [
        {
            "section_id": f"s{i + 1}",
            "start_bar": 4 * i + 1,
            "end_bar": 4 * i + 4,
            "template_id": "mirror_wings",
            "color": colour,
            "intensity": "INTENSE",
        }
        for i, colour in enumerate(colours)
    ]
    pipeline = render(
        None,
        beat_grid=grid(170, bars=12),
        fixture_group=m.tagged_family_rig(HEADS),
        sections=sections,
    )
    shaped = Heads(pipeline)

    assert pipeline.render_record is not None
    dips = [
        b
        for look in pipeline.render_record["section_looks"]
        for b in look.get("boundaries", [])
        if "dark_dip" in b
    ]
    assert dips
    for head in HEADS:
        dimmer, dark = shaped.dimmer(head), shaped.dark(head)
        reveals = [i for i in range(1, len(dark)) if dark[i - 1] and not dark[i]]
        assert len(reveals) >= 3, head
        assert all(dimmer[i] == 255 for i in reveals), (head, [dimmer[i] for i in reveals])


@pytest.mark.parametrize("level", ["DRAMATIC", "INTENSE"])
def test_a_ramp_to_full_keeps_its_shape(level: str) -> None:
    """A run that reaches full is shaped as a whole, as a gain on its own level: the ramp
    is never above its authored level, never below the dip floor of it, and never drops
    by the dip at the frame it reaches full."""
    authored = Heads(render(None, template_id=RAMP))
    shaped = Heads(render(level, template_id=RAMP))

    assert_same_but_dimmer(shaped, authored)
    floor = SHAPES[level].full_floor
    for head in HEADS:
        dimmer, base = shaped.dimmer(head), authored.dimmer(head)
        for run in lit_runs(shaped, head):
            for i in run:
                assert dimmer[i] <= base[i], (head, i * FRAME)
                assert dimmer[i] >= math.floor(base[i] * floor) - 1, (head, i * FRAME)
            reaches = [i for i in run[1:] if base[i] == 255 and base[i - 1] < 255]
            assert all(dimmer[i] >= dimmer[i - 1] for i in reaches), head


def test_a_template_pulse_at_full_is_not_inverted() -> None:
    """The template's own full / 0.6 pulse under INTENSE: both beats are scaled alike, so a
    0.6 beat never plays brighter than the full beat before it."""
    authored = Heads(render(None, template_id=STRONG_PULSE))
    shaped = Heads(render("INTENSE", template_id=STRONG_PULSE))

    assert_same_but_dimmer(shaped, authored)
    for head in HEADS:
        dimmer, base = shaped.dimmer(head), authored.dimmer(head)
        for run in lit_runs(shaped, head):
            for i in run:
                assert math.floor(base[i] * 0.6) - 1 <= dimmer[i] <= base[i]
            beats: list[list[int]] = []
            for i in run:
                if i == run[0] or (base[i] == 255) != (base[i - 1] == 255):
                    beats.append([])
                beats[-1].append(i)
            for bright, dim in pairwise(beats):
                if base[bright[0]] == 255 and base[dim[0]] < 255:
                    assert max(dimmer[i] for i in dim) <= max(dimmer[i] for i in bright) * 0.61


def test_a_level_just_below_full_still_pulses() -> None:
    """Held at 0.9, inside the blend band: the run pulses on the beat, peaking a little
    above its level and dipping below it between beats."""
    shaped = Heads(render("INTENSE", template_id=NEAR_FULL))

    for head in HEADS:
        dimmer = shaped.dimmer(head)
        lit = list(lit_runs(shaped, head)[0])
        assert round(0.9 * 255) < max(dimmer[i] for i in lit) < 255
        assert min(dimmer[i] for i in lit) < round(0.9 * 255 * 0.85)


def test_a_long_dimmer_latency_leads_by_under_half_a_beat_and_never_before_the_section() -> None:
    """A 300 ms latency at 120 BPM leads the accents by 249 ms (just under half the
    500 ms beat); after an as-authored section the shaped one starts full on its first
    frame."""
    sections = [
        {"section_id": "s1", "start_bar": 1, "end_bar": 2, "template_id": "mirror_wings"},
        {
            "section_id": "s2",
            "start_bar": 3,
            "end_bar": 8,
            "template_id": "mirror_wings",
            "intensity": "INTENSE",
        },
    ]
    beat_grid = grid(120)
    pipeline = render(
        None,
        beat_grid=beat_grid,
        fixture_group=_rig_with_dimmer(latency_ms=300),
        sections=sections,
    )
    shaped = Heads(pipeline)

    assert pipeline.render_record is not None
    (look,) = [look for look in pipeline.render_record["section_looks"] if "intensity" in look]
    assert look["intensity"]["shape"]["lead_ms"] == dict.fromkeys(HEADS, 249)
    start = accent_frame(beat_grid.bar_boundaries[2])
    for head in HEADS:
        dimmer = shaped.dimmer(head)
        assert dimmer[start - 1] == 255 and dimmer[start] == 255 and dimmer[start + 1] < 255
        for beat in beat_grid.beat_boundaries[9:30]:
            assert dimmer[accent_frame(beat, 249)] == 255


def test_lead_on_a_full_family_adds_movement_not_light() -> None:
    """The owner's open question (W5 review H2): on a family holding the dimmer full, a LEAD
    section plays DRAMATIC's dip-and-return, so it averages less light than SUPPORT. This
    pins today's behaviour until the owner rules."""
    support = Heads(render(None, focal_roles={"s1": "SUPPORT"}))
    lead = Heads(render(None, focal_roles={"s1": "LEAD"}))

    assert_same_but_dimmer(lead, support)
    for head in HEADS:
        lit = [i for run in lit_runs(support, head) for i in run]
        mean_lead = sum(lead.dimmer(head)[i] for i in lit) / len(lit)
        mean_support = sum(support.dimmer(head)[i] for i in lit) / len(lit)
        assert 0.75 < mean_lead / mean_support < 0.85, (head, mean_lead / mean_support)
