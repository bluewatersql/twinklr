"""The planner's timed events played on the frames (song-intent rendering W6/W7), asserted
on encoded frames with a reader independent of the renderer's helpers: which frames are
commanded dark, which wheel byte and dimmer word each frame carries, compared with the
same plan rendered without its events.

- closed / open: dark from the beat's frame to the next shutter event or the section end;
- strobes: an on/off on musical time (or the fixture's own tagged strobe), dark first, more
  flashes for faster speeds, slowed where the darkness path cannot follow, recorded;
- pulse: revealed on every beat, dark for the second half;
- hit: the dimmer's top on the beat's frame, a pre-dip into it at full level, a rise above
  a lower level, one accent with intensity, lit from a dimmer dark phase, moved off a
  show's rest, the lyric cue's emphasis;
- colour and gobo events: every wheel byte change inside a dark window covering the close
  latency before it and the settle after it, the reveal on the beat, the darkness added
  only inside the bounded lead, held to the next event or the section's end, a late turn
  or a drop recorded;
- nothing outside the section changes, and the trace records every event and lyric cue.
"""

from __future__ import annotations

from collections.abc import Iterator, Sequence
from itertools import pairwise
import math
from typing import Any

import pytest

from tests.support import moving_heads as m
from twinklr.core.agents.audio.lyrics.models import LyricContextModel, MomentCue
from twinklr.core.agents.audio.profile.models import SongSectionRef
from twinklr.core.agents.sequencer.moving_heads.models import ChoreographyPlan, PlanSection
from twinklr.core.agents.sequencer.moving_heads.moment_cues import bind_lyric_moment_cues
from twinklr.core.agents.sequencer.moving_heads.rig_repair import repair_rig_intent
from twinklr.core.config.fixtures import FixtureCapabilities, FixtureGroup
from twinklr.core.formats.xlights.sequence.fresh import EFFECT_GRID_MS
from twinklr.core.sequencer.moving_heads.events import (
    HIT_FLOOR,
    HITS,
    STROBE_FLASHES_PER_BEAT,
    describe_lyric_cue,
)
from twinklr.core.sequencer.moving_heads.pipeline import RenderingPipeline
from twinklr.core.sequencer.moving_heads.song_intent import rig_offer
from twinklr.core.sequencer.timing.beat_grid import BeatGrid

HEADS = ("MH1", "MH2", "MH3", "MH4")
FRAME = EFFECT_GRID_MS
HALF = "events_half_hold"
"""Test-only: one held aim, the dimmer held at half."""


@pytest.fixture(autouse=True)
def _catalog() -> Iterator[None]:
    half = m.hold_step(
        "hold", 10.0, dimmer={"period_beats": 4.0, "duty_cycle": 1.0, "low": 0.0, "high": 0.5}
    )
    with m.family_catalog(), m.registered_templates(m.loop_template_doc(HALF, [half])):
        yield


def grid(bpm: float, bars: int = 8) -> BeatGrid:
    """`bars` 4/4 bars at `bpm`, the first beat 15 ms off the frame grid."""
    return m.bars_grid(*([60_000 / bpm] * bars))


def rig(
    *,
    close: int = 0,
    settle: int | None = None,
    strobes: bool = False,
    shutter_only: bool = False,
    dimmer_speed: float | None = None,
) -> FixtureGroup:
    """`m.tagged_family_rig` (white, red, blue; open, dots, stars), with a close and open
    latency, every wheel state's settle, shutter states tagged slow/medium/fast, darkness
    through the shutter only, or a dimmer speed."""
    payload = m.tagged_family_rig(HEADS).model_dump(mode="json")
    for fixture in payload["fixtures"]:
        profile = fixture["config"]["physical_profile"]
        profile["visibility"].update(close_latency_ms=close, open_latency_ms=close)
        if settle is not None:
            for wheel in ("color", "gobo"):
                for state in profile["discrete"][wheel]["states"].values():
                    state["settle_ms"] = settle
        if strobes:
            states = profile["discrete"]["shutter"]["states"]
            for speed, low in (("slow", 100), ("medium", 140), ("fast", 180)):
                states[f"strobe_{speed}"] = {
                    "range_min": low,
                    "range_max": low + 39,
                    "value": low + 10,
                    "settle_ms": 0,
                    "strobe": speed,
                }
        if shutter_only:
            profile["visibility"]["dimmer_zero_extinguishes"] = False
        if dimmer_speed is not None:
            profile["axes"]["dimmer"]["travel_speed_per_s"] = dimmer_speed
    return FixtureGroup.model_validate(payload)


def event(bar: int, beat: int, action: str, **fields: Any) -> dict[str, Any]:
    return {
        "bar": bar,
        "beat": beat,
        "moment_cue_id": None,
        "action": action,
        "color": None,
        "gobo": None,
        **fields,
    }


def section(
    events: Sequence[dict[str, Any]],
    *,
    template_id: str = "mirror_wings",
    bars: tuple[int, int] = (1, 8),
    **fields: Any,
) -> PlanSection:
    return m.plan_section("s1", bars[0], bars[1], template_id, events=list(events), **fields)


def render(
    sections: Sequence[PlanSection],
    *,
    beat_grid: BeatGrid | None = None,
    fixture_group: FixtureGroup | None = None,
    **fields: Any,
) -> RenderingPipeline:
    pipeline = RenderingPipeline(
        choreography_plan=ChoreographyPlan(sections=list(sections), overall_strategy=""),
        beat_grid=beat_grid or grid(120),
        fixture_group=fixture_group or rig(),
        job_config=fields.pop("job_config", None) or m.family_job(HEADS),
        media_file="silence.wav",
        **fields,
    )
    pipeline.render()
    return pipeline


def without_events(sections: Sequence[PlanSection]) -> list[PlanSection]:
    return [s.model_copy(update={"events": [], "moment_cues": []}) for s in sections]


class Frames:
    """Each head's encoded frames, read through the rig's profile (not the renderer's
    helpers)."""

    def __init__(self, pipeline: RenderingPipeline) -> None:
        profile = pipeline.fixture_group.expand_fixtures()[0].config.physical_profile
        assert isinstance(profile, FixtureCapabilities)
        self.profile = profile
        self.by_head = {
            head: [
                dict(f.channels)
                for f in sorted(pipeline.frames, key=lambda f: f.time_ms)
                if f.fixture_id == head
            ]
            for head in HEADS
        }

    def dimmer(self, head: str) -> list[int]:
        offset = self.profile.axes["dimmer"].coarse_offset
        return [frame[offset] for frame in self.by_head[head]]

    def state(self, head: str, wheel: str) -> list[str]:
        capability = self.profile.discrete[wheel]
        names = {state.value: name for name, state in capability.states.items()}
        return [names[frame[capability.offset]] for frame in self.by_head[head]]

    def dark(self, head: str) -> list[bool]:
        visibility = self.profile.visibility
        shutter = self.state(head, "shutter")
        dimmer = self.dimmer(head)
        return [
            (visibility.dimmer_zero_extinguishes and level == 0)
            or state in visibility.extinguishing_shutter_states
            for level, state in zip(dimmer, shutter, strict=True)
        ]

    def raw(self, head: str) -> list[dict[int, int]]:
        return self.by_head[head]


def frame_of(time_ms: float) -> int:
    """The frame index nearest `time_ms` (ties later)."""
    return math.floor(time_ms / FRAME + 0.5)


def beat_frame(beat_grid: BeatGrid, bar: int, beat: int) -> int:
    """The frame nearest beat `beat` of bar `bar`, counted from the bar's downbeat (read
    from the grid's lists here, not through `BeatGrid.beat_index`)."""
    first = next(
        i
        for i, b in enumerate(beat_grid.beat_boundaries)
        if b >= beat_grid.bar_boundaries[bar - 1] - 1
    )
    return frame_of(beat_grid.beat_boundaries[first + beat - 1])


def assert_wheels_turn_dark(frames: Frames) -> None:
    """Every colour and gobo byte change lies inside a dark window that starts at least the
    close latency before it and lasts through the new state's settle."""
    close = math.ceil((frames.profile.visibility.close_latency_ms or 0) / FRAME)
    for head in HEADS:
        dark = frames.dark(head)
        for wheel in ("color", "gobo"):
            states = frames.state(head, wheel)
            capability = frames.profile.discrete[wheel]
            for i in range(1, len(states)):
                if states[i] == states[i - 1]:
                    continue
                settle = math.ceil((capability.states[states[i]].settle_ms or 0) / FRAME)
                window = range(max(0, i - close), min(len(dark), i + max(1, settle)))
                assert all(dark[j] for j in window), (
                    f"{head} {wheel} {states[i - 1]} → {states[i]} at {i * FRAME} ms not dark "
                    f"over {window.start * FRAME}-{window.stop * FRAME} ms"
                )


def assert_same_outside(frames: Frames, plain: Frames, start: int, end: int) -> None:
    """Every frame outside `[start, end)` (frame indices) is as without the events."""
    for head in HEADS:
        a, b = frames.raw(head), plain.raw(head)
        assert a[:start] == b[:start], head
        assert a[end:] == b[end:], head


def looks(pipeline: RenderingPipeline) -> dict[str, dict[str, Any]]:
    assert pipeline.render_record is not None
    return {look["section_id"]: look for look in pipeline.render_record.get("section_looks", [])}


def dark_runs(dark: Sequence[bool], window: range) -> int:
    return sum(1 for i in window if dark[i] and not dark[i - 1])


# --- closed / open --------------------------------------------------------------------------


def test_closed_darkens_from_its_beat_until_open() -> None:
    plan = [section([event(3, 1, "closed"), event(4, 3, "open")])]
    frames, plain = Frames(render(plan)), Frames(render(without_events(plan)))
    beat_grid = grid(120)
    closed, opened = beat_frame(beat_grid, 3, 1), beat_frame(beat_grid, 4, 3)

    assert_same_outside(frames, plain, closed, opened)
    for head in HEADS:
        dark = frames.dark(head)
        assert all(dark[i] for i in range(closed, opened)), head
        assert not dark[closed - 1] and not dark[opened], head


def test_closed_without_open_holds_to_the_section_end_only() -> None:
    plan = [
        section([event(3, 1, "closed")], bars=(1, 4)),
        m.plan_section("s2", 5, 8, "mirror_wings"),
    ]
    pipeline = render(plan)
    frames, plain = Frames(pipeline), Frames(render(without_events(plan)))
    beat_grid = grid(120)
    closed, end = beat_frame(beat_grid, 3, 1), frame_of(beat_grid.bar_boundaries[4])

    for head in HEADS:
        dark, plain_dark = frames.dark(head), plain.dark(head)
        assert all(dark[i] for i in range(closed, end)), head
        assert dark[end + 10 :] == plain_dark[end + 10 :], head  # the next section as before
    (entry,) = looks(pipeline)["s1"]["events"]
    assert entry["heads"]["MH1"] == {
        "from_ms": closed * FRAME,
        "to_ms": end * FRAME,
        "plays": "dark",
    }


# --- strobes and pulse ---------------------------------------------------------------------


@pytest.mark.parametrize("bpm", [120.0, 78.0])
def test_a_strobe_flashes_on_musical_time_dark_first_faster_for_faster_speeds(bpm: float) -> None:
    beat_grid = grid(bpm)
    start, stop = beat_frame(beat_grid, 3, 1), beat_frame(beat_grid, 5, 1)
    counts = {}
    for action in STROBE_FLASHES_PER_BEAT:
        plan = [section([event(3, 1, action), event(5, 1, "open")])]
        frames = Frames(render(plan, beat_grid=beat_grid))
        plain = Frames(render(without_events(plan), beat_grid=beat_grid))
        assert_same_outside(frames, plain, start, stop)
        dark = frames.dark("MH1")
        assert dark[start] and not dark[start - 1], action  # the first dark frame is the beat's
        assert not dark[stop], action  # open ends it
        counts[action] = dark_runs(dark, range(start, stop))
        # Eight beats from bar 3: the asked flashes per beat, whole flashes on the frame grid.
        assert counts[action] == 8 * STROBE_FLASHES_PER_BEAT[action], (action, counts[action])
        for head in HEADS:
            assert frames.dark(head) == dark
    assert counts["strobe_fast"] > counts["strobe_medium"] > counts["strobe_slow"]


def test_a_rig_with_tagged_strobe_states_strobes_itself() -> None:
    beat_grid = grid(120)
    plan = [section([event(3, 1, "strobe_medium"), event(4, 1, "open")])]
    pipeline = render(plan, fixture_group=rig(strobes=True))
    frames = Frames(pipeline)
    plain = Frames(render(without_events(plan), fixture_group=rig(strobes=True)))
    start, stop = beat_frame(beat_grid, 3, 1), beat_frame(beat_grid, 4, 1)

    for head in HEADS:
        shutter = frames.state(head, "shutter")
        assert {shutter[i] for i in range(start, stop)} == {"strobe_medium"}, head
        assert shutter[start - 1] == "open" and shutter[stop] == "open"
        assert frames.dimmer(head) == plain.dimmer(head)  # the fixture strobes, not the dimmer
    (entry, _) = looks(pipeline)["s1"]["events"]
    assert "the fixture's own strobe" in entry["heads"]["MH1"]["plays"]


def test_a_shutter_only_rig_strobes_within_its_latency_and_records_the_slower_rate() -> None:
    """Darkness only through the shutter, 40 ms close and open latency: a thirty-second
    strobe (31 ms phases at 120 BPM) plays as sixteenths (62.5 ms), every shutter change
    holding its latency plus settle."""
    beat_grid = grid(120)
    shutter_rig = rig(close=40, shutter_only=True)
    plan = [section([event(3, 1, "strobe_fast"), event(4, 1, "open")])]
    pipeline = render(plan, fixture_group=shutter_rig)
    frames = Frames(pipeline)

    start, stop = beat_frame(beat_grid, 3, 1), beat_frame(beat_grid, 4, 1)
    for head in HEADS:
        shutter = frames.state(head, "shutter")
        changes = [i for i in range(start, stop + 1) if shutter[i] != shutter[i - 1]]
        assert all((b - a) * FRAME >= 40 for a, b in pairwise(changes)), head
        assert dark_runs(frames.dark(head), range(start, stop)) == 4 * 4, head
    (entry, _) = looks(pipeline)["s1"]["events"]
    assert entry["heads"]["MH1"]["flashes_per_beat"] == 4
    assert "degraded" in entry["heads"]["MH1"]
    assert pipeline.render_record is not None
    assert any("played slower" in d["message"] for d in pipeline.render_record["diagnostics"])


def test_a_slow_dimmer_strobes_at_the_rate_it_can_follow() -> None:
    """A dimmer travelling 8 units/s needs 140 ms each way: at 120 BPM even eighths
    (125 ms) are too fast, so every strobe plays one flash a beat."""
    beat_grid = grid(120)
    pipeline = render([section([event(3, 1, "strobe_slow")])], fixture_group=rig(dimmer_speed=8.0))
    (entry,) = looks(pipeline)["s1"]["events"]
    assert entry["heads"]["MH1"]["flashes_per_beat"] == 1
    dark = Frames(pipeline).dark("MH1")
    start = beat_frame(beat_grid, 3, 1)
    assert dark_runs(dark, range(start, start + 100)) == 4  # one a beat over 2 s


def test_pulse_reveals_on_every_beat_and_darkens_for_the_second_half() -> None:
    beat_grid = grid(120)
    plan = [section([event(3, 1, "pulse"), event(5, 1, "open")])]
    frames = Frames(render(plan, beat_grid=beat_grid))
    start, stop = beat_frame(beat_grid, 3, 1), beat_frame(beat_grid, 5, 1)

    for head in HEADS:
        dark = frames.dark(head)
        reveals = [i for i in range(start + 1, stop) if dark[i - 1] and not dark[i]]
        beats = [frame_of(b) for b in beat_grid.beat_boundaries[9:16]]
        assert reveals == beats, (head, reveals, beats)
        for beat in [frame_of(b) for b in beat_grid.beat_boundaries[8:16]]:
            assert not dark[beat] and dark[beat + 13] and not dark[beat + 11], head


# --- hits --------------------------------------------------------------------------------


def hit_window(beat_grid: BeatGrid, bar: int, beat: int, emphasis: str = "MED") -> range:
    at = beat_frame(beat_grid, bar, beat)
    shape = HITS[emphasis]
    before = math.ceil(beat_grid.beat_boundaries[1] - beat_grid.beat_boundaries[0]) / 4 / FRAME
    after = shape.decay_beats * (beat_grid.beat_boundaries[1] - beat_grid.beat_boundaries[0])
    return range(at - math.ceil(before) - 1, at + math.ceil(after / FRAME) + 1)


def visible_frames(frames: Frames, plain: Frames, head: str, at: int, emphasis: str) -> int:
    """How many frames around a hit at frame `at` differ from the render without it by at
    least the emphasis' contrast of full, or by all the room the level without it leaves
    above the floor where that is less, read from the bytes."""
    contrast, floor = HITS[emphasis].contrast, HIT_FLOOR * 255
    a, b = frames.dimmer(head), plain.dimmer(head)

    def needed(level: int) -> float:
        return max(1, min(contrast * 255, max(0.0, level - floor)) - 1)

    return sum(
        1 for i in range(max(0, at - 30), min(len(a), at + 60)) if abs(a[i] - b[i]) >= needed(b[i])
    )


@pytest.mark.parametrize("emphasis", ["LOW", "MED", "HIGH"])
def test_a_hit_with_room_before_its_beat_dips_into_it_and_snaps_to_full(emphasis: str) -> None:
    """At full level with the head lit before the beat: the last `visible_frames` frames
    before it held `contrast` below the level, then that many frames at full."""
    beat_grid = grid(120)
    plan = [section([event(3, 1, "hit", cue_emphasis=emphasis)])]
    frames, plain = Frames(render(plan)), Frames(render(without_events(plan)))
    at = beat_frame(beat_grid, 3, 1)
    window = hit_window(beat_grid, 3, 1, emphasis)
    shape = HITS[emphasis]
    held = round(255 * (1 - shape.contrast))

    assert_same_outside(frames, plain, window.start, window.stop + shape.visible_frames)
    for head in HEADS:
        dimmer = frames.dimmer(head)
        assert frames.dark(head) == plain.dark(head)
        assert all(abs(dimmer[i] - held) <= 1 for i in range(at - shape.visible_frames, at))
        assert all(dimmer[i] == 255 for i in range(at, at + shape.visible_frames))
        assert visible_frames(frames, plain, head, at, emphasis) >= shape.visible_frames


def test_a_hit_on_a_reveal_flashes_and_ducks_below_the_section_level() -> None:
    """A cascade head revealed on the hit's beat (dark before it, at full already in the
    render without the hit): a flash of `visible_frames` frames, then as many frames
    `contrast` below the level it plays, recovering; visibly different."""
    beat_grid = grid(120)
    plain = Frames(render([section([], template_id="fly_out_cascade")]))
    head, bar, beat = next(
        (h, bar, b)
        for bar in range(2, 8)
        for b in range(1, 5)
        for h in HEADS
        if plain.dark(h)[beat_frame(beat_grid, bar, b) - 1]
        and not plain.dark(h)[beat_frame(beat_grid, bar, b)]
    )
    pipeline = render([section([event(bar, beat, "hit")], template_id="fly_out_cascade")])
    frames = Frames(pipeline)
    at = beat_frame(beat_grid, bar, beat)
    shape = HITS["MED"]

    (entry,) = looks(pipeline)["s1"]["events"]
    assert entry["heads"][head]["shape"] == "flash_and_duck"
    dimmer, base = frames.dimmer(head), plain.dimmer(head)
    assert all(dimmer[i] == 255 for i in range(at, at + shape.visible_frames))
    ducked = range(at + shape.visible_frames, at + 2 * shape.visible_frames)
    assert all(base[i] - dimmer[i] >= round(shape.contrast * 255) - 1 for i in ducked)
    assert visible_frames(frames, plain, head, at, "MED") >= shape.visible_frames
    assert frames.dark(head) == plain.dark(head)


def test_a_stronger_cue_cuts_deeper_into_the_beat_and_rings_longer() -> None:
    """On a level below full the hit rises to full on the beat and eases back: HIGH holds
    more frames visibly apart from the render without it than LOW, and dips deeper."""
    beat_grid = grid(120)
    at = beat_frame(beat_grid, 3, 1)
    seen, dips = {}, {}
    plain = Frames(render([section([], template_id=HALF)]))
    for emphasis in ("LOW", "HIGH"):
        hit = event(3, 1, "hit", cue_emphasis=emphasis)
        half = Frames(render([section([hit], template_id=HALF)]))
        dimmer = half.dimmer("MH1")
        assert dimmer[at] == 255
        seen[emphasis] = visible_frames(half, plain, "MH1", at, emphasis)
        dips[emphasis] = dimmer[at - 1]
    assert seen["HIGH"] > seen["LOW"] >= HITS["LOW"].visible_frames
    assert dips["HIGH"] < dips["LOW"] < 128


GRIDS = {
    "78.3": lambda: grid(78.3),
    "120": lambda: grid(120),
    "170": lambda: grid(170),
    "variable": lambda: m.bars_grid(*[(560.0, 420.0, 600.0, 380.0)[i % 4] for i in range(8)]),
}


@pytest.mark.parametrize("level", [None, "DRAMATIC"])
@pytest.mark.parametrize("tempo", list(GRIDS))
@pytest.mark.parametrize(
    "template_id", ["fly_out_cascade", "fly_in_cascade", "masked_wheel_flick", "mirror_wings"]
)
def test_every_played_hit_differs_visibly_from_the_render_without_it(
    template_id: str, tempo: str, level: str | None
) -> None:
    """Four HIGH hits a bar and more apart: on every head the trace counts as played, at
    least `visible_frames` frames differ from the render without the hits by the contrast
    (capped), read from the bytes; a head the trace says did not play shows no change
    there (the review's case: hits on reveals byte-identical to no hit)."""
    beat_grid = GRIDS[tempo]()
    hits = [event(b, k, "hit", cue_emphasis="HIGH") for b, k in ((2, 1), (3, 2), (5, 3), (7, 4))]
    plan = [section(hits, template_id=template_id, intensity=level)]
    pipeline = render(plan, beat_grid=beat_grid)
    frames, plain = Frames(pipeline), Frames(render(without_events(plan), beat_grid=beat_grid))
    played = 0
    for entry in looks(pipeline)["s1"]["events"]:
        for head, outcome in entry["heads"].items():
            if "played_ms" not in outcome:
                assert "not_played" in outcome, outcome
                continue
            played += 1
            at = outcome["played_ms"] // FRAME
            assert visible_frames(frames, plain, head, at, "HIGH") >= HITS["HIGH"].visible_frames
    assert played


def test_a_moved_hit_goes_later_to_the_beat_most_heads_show_and_says_so() -> None:
    """A show's rest over the hit's beat: the hit moves to the next beat (later), every
    head plays it there, and the trace says where and which way."""
    beat_grid = grid(120)
    rest = (round(beat_grid.beat_boundaries[8]) - 100, round(beat_grid.beat_boundaries[9]) - 100)
    pipeline = render([section([event(3, 1, "hit")])], dark_spans=(rest,))
    (entry,) = looks(pipeline)["s1"]["events"]
    for head in HEADS:
        moved = entry["heads"][head]["moved"]
        assert (moved["direction"], moved["bar"], moved["beat"], moved["heads_lit"]) == (
            "later",
            3,
            2,
            4,
        )


def test_a_hit_moves_earlier_only_where_no_later_beat_serves() -> None:
    """A rest over the section's last beats: nothing later within the section, so the hit
    moves to the nearest earlier beat, recorded as earlier."""
    beat_grid = grid(120)
    rest = (round(beat_grid.beat_boundaries[13]) - 100, 8100)
    pipeline = render(
        [section([event(4, 3, "hit")], bars=(1, 4))],
        beat_grid=beat_grid,
        dark_spans=(rest,),
    )
    (entry,) = looks(pipeline)["s1"]["events"]
    moved = entry["heads"]["MH1"]["moved"]
    assert moved["direction"] == "earlier" and (moved["bar"], moved["beat"]) == (4, 1)


@pytest.mark.parametrize("level", ["DRAMATIC", "INTENSE"])
def test_a_hit_on_an_intensity_accent_is_one_accent(level: str) -> None:
    """The hit reads the level intensity plays: on an accented beat it is the one peak of
    that beat (the frames after it fall to the next beat), and nothing outside its window
    differs from intensity alone."""
    beat_grid = grid(120)
    plan = [section([event(3, 1, "hit")], intensity=level)]
    frames, plain = Frames(render(plan)), Frames(render(without_events(plan)))
    at = beat_frame(beat_grid, 3, 1)
    window = hit_window(beat_grid, 3, 1)

    assert_same_outside(frames, plain, window.start, window.stop)
    for head in HEADS:
        dimmer = frames.dimmer(head)
        assert dimmer[at] == 255 and plain.dimmer(head)[at] == 255
        after = dimmer[at : at + 24]
        assert after == sorted(after, reverse=True), after
        assert all(
            a >= b
            for a, b in zip(
                dimmer[at : window.stop], plain.dimmer(head)[at : window.stop], strict=True
            )
        )


def test_a_hit_in_a_closed_span_lights_the_head_for_it_and_returns_to_dark() -> None:
    beat_grid = grid(120)
    plan = [section([event(3, 1, "closed"), event(3, 3, "hit"), event(5, 1, "open")])]
    pipeline = render(plan)
    frames = Frames(pipeline)
    closed, at, opened = (beat_frame(beat_grid, *b) for b in ((3, 1), (3, 3), (5, 1)))

    for head in HEADS:
        dimmer, dark = frames.dimmer(head), frames.dark(head)
        assert all(dark[i] for i in range(closed, at)), head
        assert dimmer[at] == 255
        lit = [i for i in range(at, opened) if not dark[i]]
        assert lit == list(range(at, lit[-1] + 1)) and len(lit) >= 5, lit
        assert all(dark[i] for i in range(lit[-1] + 1, opened))
    hit = looks(pipeline)["s1"]["events"][1]
    assert hit["heads"]["MH1"]["how"] == "lit_from_dark"


def test_a_hit_on_a_show_rest_moves_and_is_recorded() -> None:
    beat_grid = grid(120)
    rest = (round(beat_grid.beat_boundaries[8]) - 100, round(beat_grid.beat_boundaries[9]) - 100)
    pipeline = render([section([event(3, 1, "hit")])], dark_spans=(rest,))
    frames = Frames(pipeline)
    moved = beat_frame(beat_grid, 3, 2)

    for head in HEADS:
        assert frames.dimmer(head)[moved] == 255
        assert frames.dark(head)[beat_frame(beat_grid, 3, 1)]
    assert pipeline.render_record is not None
    assert any(
        "moved to another beat" in d["message"] for d in pipeline.render_record["diagnostics"]
    )


def test_a_hit_plays_on_the_heads_a_cascade_lights_on_its_beat() -> None:
    """A cascade lights one pair of heads at a time: a hit on a beat where some are lit
    plays there on those, as one moment, and is recorded as not played on the others."""
    beat_grid = grid(120)
    plain = Frames(render([section([], template_id="fly_out_cascade")]))
    lit_beat = next(
        (bar, beat)
        for bar in range(2, 8)
        for beat in range(1, 5)
        if 0 < sum(not plain.dark(h)[beat_frame(beat_grid, bar, beat)] for h in HEADS) < 4
    )
    pipeline = render([section([event(*lit_beat, "hit")], template_id="fly_out_cascade")])
    at = beat_frame(beat_grid, *lit_beat)
    (entry,) = looks(pipeline)["s1"]["events"]
    for head in HEADS:
        if plain.dark(head)[at]:
            assert "not_played" in entry["heads"][head]
        else:
            assert entry["heads"][head]["played_ms"] == at * FRAME
            assert Frames(pipeline).dimmer(head)[at] == 255


def cue_plan(action: str, **fields: Any) -> tuple[ChoreographyPlan, BeatGrid]:
    """A plan whose event at bar 1 beat 1 is bound to a HIGH lyric cue at 2690 ms."""
    beat_grid = grid(120)
    plan = ChoreographyPlan(
        sections=[
            section(
                [event(1, 1, action, moment_cue_id="hook", **fields)],
                bars=(1, 4),
                moment_cues=["hook"],
            )
        ],
        overall_strategy="",
    )
    lyrics = LyricContextModel(
        has_lyrics=True,
        vocal_coverage_pct=0.25,
        moment_cues=[
            MomentCue(
                cue_id="hook",
                timestamp_ms=2690,
                section_id="s1",
                emphasis="HIGH",
                text="light the way",
                visual_hint="Accent the hook.",
            )
        ],
    )
    song = [SongSectionRef(section_id="s1", name="s1", start_ms=0, end_ms=8015)]
    return bind_lyric_moment_cues(plan, lyrics, beat_grid, song), beat_grid


def test_a_cue_bound_hit_lands_on_the_cue_beat_with_its_emphasis_and_is_traced() -> None:
    plan, beat_grid = cue_plan("hit")
    (bound,) = plan.sections[0].events
    assert (bound.bar, bound.beat, bound.cue_emphasis) == (2, 2, "HIGH")
    pipeline = render(plan.sections, beat_grid=beat_grid)
    at = beat_frame(beat_grid, 2, 2)

    for head in HEADS:
        assert Frames(pipeline).dimmer(head)[at] == 255
    (entry,) = looks(pipeline)["s1"]["events"]
    assert (
        entry["emphasis"] == "HIGH" and entry["heads"]["MH1"]["contrast"] == HITS["HIGH"].contrast
    )
    assert pipeline.render_record is not None
    (cue,) = pipeline.render_record["lyric_cues"]
    assert cue["cue_id"] == "hook" and cue["emphasis"] == "HIGH"
    assert cue["events"][0]["played"] == dict.fromkeys(HEADS, at * FRAME)


def test_a_referenced_cue_without_an_event_is_recorded() -> None:
    pipeline = render([section([], moment_cues=["lonely"])])
    assert pipeline.render_record is not None
    assert pipeline.render_record["lyric_cues"] == [
        {
            "cue_id": "lonely",
            "section_id": "s1",
            "not_played": "no event lands on it (the planner was told)",
        }
    ]


# --- colour and gobo events ------------------------------------------------------------------


@pytest.mark.parametrize("bpm", [120.0, 78.0])
@pytest.mark.parametrize(
    ("action", "wheel", "value", "state"),
    [
        ("color", "color", "red", "red"),
        ("gobo", "gobo", "dots", "dots"),
    ],
)
def test_a_wheel_event_reveals_on_its_beat_after_a_bounded_dark_lead(
    bpm: float, action: str, wheel: str, value: str, state: str
) -> None:
    """Owner-like timings (close latency 20 ms, every state settling in 150 ms): the head
    goes dark at most half a beat before the beat, the wheel turns in the dark, and the
    head comes back on the beat's frame in the new state, held to the section's end."""
    beat_grid = grid(bpm)
    timings = rig(close=20, settle=150)
    plan = [section([event(3, 1, action, **{action: value})])]
    frames = Frames(render(plan, beat_grid=beat_grid, fixture_group=timings))
    plain = Frames(render(without_events(plan), beat_grid=beat_grid, fixture_group=timings))
    at = beat_frame(beat_grid, 3, 1)
    half = (beat_grid.beat_boundaries[1] - beat_grid.beat_boundaries[0]) / 2
    lead = math.ceil((20 + 150 + half) / FRAME)

    assert_wheels_turn_dark(frames)
    for head in HEADS:
        states, dark, plain_dark = frames.state(head, wheel), frames.dark(head), plain.dark(head)
        assert not dark[at] and states[at] == state, head
        assert all(states[i] == state for i in range(at, len(states)) if not dark[i])
        assert all(states[i] != state for i in range(at) if not dark[i])
        changed = [i for i, (a, b) in enumerate(zip(dark, plain_dark, strict=True)) if a != b]
        assert changed and at - lead <= min(changed) and max(changed) < at, (head, changed)


def test_successive_colour_events_each_reveal_on_their_beat() -> None:
    beat_grid = grid(120)
    plan = [section([event(3, 1, "color", color="red"), event(3, 3, "color", color="blue")])]
    frames = Frames(render(plan))
    first, second = beat_frame(beat_grid, 3, 1), beat_frame(beat_grid, 3, 3)

    assert_wheels_turn_dark(frames)
    for head in HEADS:
        states, dark = frames.state(head, "color"), frames.dark(head)
        assert states[first] == "red" and not dark[first]
        assert states[second] == "blue" and not dark[second]
        assert all(states[i] == "red" for i in range(first, second) if not dark[i])


def test_a_colour_event_inside_a_closed_span_rides_its_darkness() -> None:
    beat_grid = grid(120)
    plan = [
        section([event(3, 1, "closed"), event(3, 3, "color", color="blue"), event(3, 3, "open")])
    ]
    pipeline = render(plan)
    frames = Frames(pipeline)
    at = beat_frame(beat_grid, 3, 3)

    assert_wheels_turn_dark(frames)
    colour = looks(pipeline)["s1"]["events"][1]
    assert colour["heads"]["MH1"]["dark_dip"]["added_ms"] == 0
    for head in HEADS:
        assert frames.state(head, "color")[at] == "blue" and not frames.dark(head)[at]


def test_a_colour_event_that_cannot_dip_turns_in_the_next_dark_window_late_and_says_so() -> None:
    """At 170 BPM (half beat 176 ms) a 300 ms settle cannot dip before the beat: on
    `masked_wheel_flick` the turn waits for its next mask, recorded late; on `mirror_wings`,
    which has no dark window, it does not play, recorded."""
    beat_grid = grid(170)
    slow = rig(close=20, settle=300)
    flick = render(
        [section([event(2, 2, "color", color="blue")], template_id="masked_wheel_flick")],
        beat_grid=beat_grid,
        fixture_group=slow,
    )
    wings = render(
        [section([event(2, 2, "color", color="red")])], beat_grid=beat_grid, fixture_group=slow
    )

    assert_wheels_turn_dark(Frames(flick))
    assert_wheels_turn_dark(Frames(wings))
    outcomes = looks(flick)["s1"]["events"][0]["heads"]
    assert any("deferred" in o or "late" in o for o in outcomes.values()), outcomes
    (entry,) = looks(wings)["s1"]["events"]
    assert all("not_played" in o for o in entry["heads"].values())
    assert wings.render_record is not None
    assert any("not played" in d["message"] for d in wings.render_record["diagnostics"])


def test_a_colour_event_on_a_flick_takes_over_the_flick() -> None:
    """`masked_wheel_flick` turns each head to its flick colour mid-cycle: a colour event
    landing as the flick starts plays the event's colour from the beat on every head, and
    the template's later flicks play as authored."""
    beat_grid = grid(120)
    plan = [
        section(
            [event(3, 4, "color", color="white")], template_id="masked_wheel_flick", color="red"
        )
    ]
    pipeline = render(plan)
    frames = Frames(pipeline)
    at = beat_frame(beat_grid, 3, 4)  # the second cycle's flick starts on its fourth beat

    assert_wheels_turn_dark(frames)
    for head in HEADS:
        states, dark = frames.state(head, "color"), frames.dark(head)
        assert states[at] == "white" and not dark[at], head
        assert {states[i] for i in range(at, at + 25) if not dark[i]} == {"white"}, head
        later = {states[i] for i in range(at, len(states)) if not dark[i]}
        assert later - {"white"} <= {"red", "blue"}  # the template's later flicks


def test_a_wheel_change_shown_only_in_short_lit_runs_still_turns_and_shows() -> None:
    """A gobo event on a cascade's dark beat, where a strobe then lights the head in
    flashes of a frame or two: the wheel still turns and every lit frame shows the new
    gobo (the three-frame rule only counts showing it within a beat, for moving it)."""
    plan = [
        m.plan_section(
            "e0",
            1,
            4,
            "fly_out_cascade",
            color="red",
            events=[
                event(2, 1, "hit"),
                event(2, 3, "color", color="blue"),
                event(3, 2, "closed"),
                event(3, 4, "open"),
                event(4, 2, "gobo", gobo="stars"),
                event(4, 3, "strobe_fast"),
                event(4, 4, "hit"),
            ],
        )
    ]
    pipeline = render(plan, beat_grid=grid(120, 6), fixture_group=rig(close=20, settle=150))
    frames = Frames(pipeline)
    gobo = next(e for e in looks(pipeline)["e0"]["events"] if e["action"] == "gobo")
    end = frame_of(grid(120, 6).bar_boundaries[4])

    assert_wheels_turn_dark(frames)
    short = [h for h in HEADS if gobo["heads"][h]["shown_ms"] is None]
    assert short  # some head is lit only in short runs after the event
    for head in HEADS:
        outcome = gobo["heads"][head]
        assert "not_played" not in outcome and outcome["reveal_ms"] is not None
        states, dark = frames.state(head, "gobo"), frames.dark(head)
        lit = [states[i] for i in range(outcome["reveal_ms"] // FRAME, end) if not dark[i]]
        assert lit and set(lit) == {outcome["state"]}, head


def two_parts(events: Sequence[dict[str, Any]]) -> PlanSection:
    """One section over bars 1-8 in two parts of `mirror_wings` (bars 1-4 and 5-8)."""
    one = section(events)
    return one.model_copy(
        update={"parts": [one.parts[0], one.parts[0].model_copy(update={"start_bar": 5})]}
    )


def test_events_carry_across_the_parts_of_a_section() -> None:
    """A closed event in the first part keeps the second dark to the section's end; a
    colour event in the first part holds through the second."""
    beat_grid = grid(120)
    part_b = frame_of(beat_grid.bar_boundaries[4])
    closed = Frames(render([two_parts([event(3, 1, "closed")])]))
    blue = Frames(render([two_parts([event(2, 1, "color", color="blue")])]))
    end = frame_of(beat_grid.bar_boundaries[8])

    for head in HEADS:
        dark = closed.dark(head)
        assert all(dark[i] for i in range(beat_frame(beat_grid, 3, 1), end)), head
        states, lit = blue.state(head, "color"), [not d for d in blue.dark(head)]
        assert {states[i] for i in range(part_b, end) if lit[i]} == {"blue"}, head


# --- trace and diagnostics --------------------------------------------------------------------


def test_event_sections_no_longer_report_events_as_not_rendered() -> None:
    pipeline = render([section([event(2, 1, "hit"), event(3, 1, "gobo", gobo="dots")])])
    assert pipeline.render_record is not None
    assert not [
        d for d in pipeline.render_record["diagnostics"] if "not rendered yet" in d["message"]
    ]


# --- a realistic plan ------------------------------------------------------------------------

OWNER_COLOURS = {
    "white": "#FFFFFF",
    "red": "#FF0000",
    "orange": "#FF8000",
    "amber": "#FFBF00",
    "yellow": "#FFFF00",
    "green": "#00FF00",
    "cyan": "#00FFFF",
    "blue": "#0000FF",
    "purple": "#8000FF",
    "magenta": "#FF00FF",
    "pink": "#FF80C0",
}


def owner_like_rig() -> FixtureGroup:
    """The family rig as the owner's test song was planned on (synthetic): a colour wheel
    of eleven tagged colours, a gobo wheel showing only `open`, no strobe states, close
    and open latency 20 ms, every wheel state settling in 150 ms."""
    payload = m.family_rig(HEADS).model_dump(mode="json")
    for fixture in payload["fixtures"]:
        profile = fixture["config"]["physical_profile"]
        profile["visibility"].update(close_latency_ms=20, open_latency_ms=20)
        profile["discrete"]["color"]["states"] = {
            name: {
                "range_min": 10 * i,
                "range_max": 10 * i + 9,
                "value": 10 * i,
                "settle_ms": 150,
                "hex": hex_,
            }
            for i, (name, hex_) in enumerate(OWNER_COLOURS.items())
        }
        profile["discrete"]["gobo"]["states"] = {
            "open": {
                "range_min": 0,
                "range_max": 7,
                "value": 0,
                "settle_ms": 150,
                "pattern": "open",
            }
        }
    return FixtureGroup.model_validate(payload)


REALISTIC = [
    ("intro", 1, 10, [(1, "target_orbit")], "SLOW", "PALETTE_WARM",
     [(7, 3, "closed", None, None), (8, 2, "hit", None, "intro-cue")]),
    ("verse_1", 11, 20, [(11, "masked_wheel_flick")], "SMOOTH", "PALETTE_PRIMARY",
     [(15, 4, "color", "PALETTE_WARM", "verse1-cue"), (18, 1, "pulse", None, None)]),
    ("verse_2", 21, 31, [(21, "target_orbit")], "FAST", "PALETTE_WARM",
     [(21, 1, "hit", None, None), (30, 1, "color", "PALETTE_PRIMARY", "verse2-cue")]),
    ("chorus_1", 32, 42, [(32, "fly_out_cascade")], "DRAMATIC", "PALETTE_PRIMARY",
     [(32, 1, "hit", None, None), (36, 1, "hit", None, None), (40, 1, "hit", None, None)]),
    ("break", 43, 52, [(43, "fly_in_cascade")], "DRAMATIC", "PALETTE_ACCENT",
     [(44, 1, "hit", None, "break-cue-1"), (46, 1, "hit", None, "break-cue-2"),
      (45, 3, "hit", None, None), (49, 1, "color", "PALETTE_WARM", None),
      (52, 1, "strobe_medium", None, None)]),
    ("chorus_2", 53, 61, [(53, "mirror_wings"), (59, "finite_snap_hold")], "INTENSE",
     "PALETTE_PRIMARY",
     [(53, 1, "hit", None, None), (60, 2, "hit", None, "chorus2-cue-1"),
      (61, 4, "color", "PALETTE_NEUTRAL", "chorus2-cue-2")]),
]  # fmt: skip
"""The shape of the plan the owner's test song produced (section, bars, parts, intensity,
colour, events with their lyric cues): synthetic, built from the brief's summary."""
CUE_EMPHASIS = {
    "intro-cue": "HIGH",
    "verse1-cue": "MED",
    "verse2-cue": "HIGH",
    "break-cue-1": "HIGH",
    "break-cue-2": "HIGH",
    "chorus2-cue-1": "HIGH",
    "chorus2-cue-2": "MED",
}


def realistic_plan(beat_grid: BeatGrid) -> ChoreographyPlan:
    """`REALISTIC` as a plan, its lyric cues 40 ms after their beats, bound by the binder."""
    sections, cues, song = [], [], []
    bars = beat_grid.bar_boundaries
    for section_id, first, last, parts, intensity, colour, events in REALISTIC:
        song.append(
            SongSectionRef(
                section_id=section_id,
                name=section_id,
                start_ms=int(bars[first - 1]),
                end_ms=int(bars[last]),
            )
        )
        planned = []
        for bar, beat, action, value, cue_id in events:
            planned.append(event(bar, beat, action, moment_cue_id=cue_id, color=value))
            if cue_id is not None:
                at = beat_grid.beat_time_ms(bar, beat)
                assert at is not None
                cues.append(
                    MomentCue(
                        cue_id=cue_id,
                        timestamp_ms=int(at) + 40,
                        section_id=section_id,
                        emphasis=CUE_EMPHASIS[cue_id],
                        text="la la",
                        visual_hint="Accent the line.",
                    )
                )
        plan_section = m.plan_section(
            section_id,
            first,
            last,
            parts[0][1],
            intensity=intensity,
            color=colour,
            gobo="open",
            moment_cues=sorted({e["moment_cue_id"] for e in planned} - {None}),
            events=planned,
        )
        plan_section = plan_section.model_copy(
            update={
                "parts": [
                    plan_section.parts[0].model_copy(update={"start_bar": s, "template_id": t})
                    for s, t in parts
                ]
            }
        )
        sections.append(plan_section)
    lyrics = LyricContextModel(has_lyrics=True, vocal_coverage_pct=0.5, moment_cues=cues)
    plan = ChoreographyPlan(sections=sections, overall_strategy="")
    return bind_lyric_moment_cues(plan, lyrics, beat_grid, song)


def test_the_realistic_plan_plays_every_event_honestly_and_traces_every_cue() -> None:
    """The owner's test song's plan shape at 78.3 BPM on an owner-like rig: every wheel
    byte change is dark through close latency and settle, every event is traced on every
    head (played, moved or not played with a reason), every lyric cue is traced, and the
    events the brief names play as designed."""
    beat_grid = m.pickup_grid(60_000 / 78.3, 62, pickup=2)  # two pickup beats, as the song
    pipeline = render(
        realistic_plan(beat_grid).sections, beat_grid=beat_grid, fixture_group=owner_like_rig()
    )
    frames = Frames(pipeline)
    by_section = looks(pipeline)

    assert_wheels_turn_dark(frames)
    entries = [e for look in by_section.values() for e in look.get("events", [])]
    assert len(entries) == sum(len(s[6]) for s in REALISTIC)
    for entry in entries:
        assert set(entry["heads"]) == set(HEADS), entry
        for outcome in entry["heads"].values():
            assert ("not_played" in outcome) != any(
                k in outcome for k in ("played_ms", "reveal_ms", "plays")
            ), (entry["action"], entry["bar"], entry["beat"], outcome)

    def at(section_id: str, bar: int, beat: int) -> dict[str, Any]:
        return next(
            e for e in by_section[section_id]["events"] if (e["bar"], e["beat"]) == (bar, beat)
        )

    intro_hit = at("intro", 8, 2)
    assert intro_hit["emphasis"] == "HIGH"
    assert {o["how"] for o in intro_hit["heads"].values()} == {"lit_from_dark"}
    for section_id, bar, beat, state in (
        ("verse_1", 15, 4, "orange"),
        ("verse_2", 30, 1, "red"),
        ("chorus_2|B", 61, 4, "white"),
    ):
        frame = beat_frame(beat_grid, bar, beat)
        for head in HEADS:
            assert frames.state(head, "color")[frame] == state, (section_id, head)
            assert not frames.dark(head)[frame], (section_id, head)
        assert all(
            o["reveal_ms"] == frame * FRAME for o in at(section_id, bar, beat)["heads"].values()
        )
    strobe = at("break", 52, 1)
    assert {o["flashes_per_beat"] for o in strobe["heads"].values()} == {4}
    assert pipeline.render_record is not None
    cues = {c["cue_id"]: c for c in pipeline.render_record["lyric_cues"]}
    assert set(cues) == set(CUE_EMPHASIS)
    assert all(c["emphasis"] == CUE_EMPHASIS[i] for i, c in cues.items())
    assert all(c["events"][0]["played"] for c in cues.values())


def test_the_realistic_plan_darkens_only_where_an_event_says_and_lights_only_for_a_hit() -> None:
    """Against the same plan without events, read from the plan, not the trace: every
    newly dark frame lies in a closed, strobe or pulse event's span (its beat to the next
    shutter event or its section's end) or in the bounded lead before a colour event's
    beat (close latency + settle + half a beat); every newly lit frame follows a hit's
    beat by at most its decay (or lies in the beat before a section, where a colour the
    events already turned needs no boundary dip)."""
    beat_grid = m.pickup_grid(60_000 / 78.3, 62, pickup=2)  # two pickup beats, as the song
    plan = realistic_plan(beat_grid)
    rig_ = owner_like_rig()
    frames = Frames(render(plan.sections, beat_grid=beat_grid, fixture_group=rig_))
    plain = Frames(render(without_events(plan.sections), beat_grid=beat_grid, fixture_group=rig_))
    beat = 60_000 / 78.3
    bars = beat_grid.bar_boundaries

    darkened: set[int] = set()
    lit_for: set[int] = set()
    for _, first, last, _, _, _, events in REALISTIC:
        end = frame_of(bars[last])
        shutter = sorted(
            (beat_frame(beat_grid, bar, b), action)
            for bar, b, action, _, _ in events
            if action in ("closed", "open", "pulse") or action.startswith("strobe_")
        )
        ends = [*shutter[1:], (end, "")][: len(shutter)]
        for (start, action), following in zip(shutter, ends, strict=True):
            if action != "open":
                darkened.update(range(start, following[0]))
        for bar, b, action, _, _ in events:
            at = beat_frame(beat_grid, bar, b)
            if action == "color":
                darkened.update(range(at - math.ceil((20 + 160 + beat / 2) / FRAME), at))
            if action == "hit":
                # A moved hit lands within a bar of its beat, and rings at most 0.75 beat.
                lit_for.update(
                    range(at - math.ceil(4 * beat / FRAME), at + math.ceil(4.75 * beat / FRAME))
                )
        lit_for.update(
            range(frame_of(bars[first - 1]) - math.ceil(beat / FRAME), frame_of(bars[first - 1]))
        )
    for head in HEADS:
        dark, before = frames.dark(head), plain.dark(head)
        newly_dark = {i for i, (a, b) in enumerate(zip(dark, before, strict=True)) if a and not b}
        newly_lit = {i for i, (a, b) in enumerate(zip(dark, before, strict=True)) if b and not a}
        assert newly_dark <= darkened, (head, sorted(newly_dark - darkened)[:5])
        assert newly_lit <= lit_for, (head, sorted(newly_lit - lit_for)[:5])


def test_a_palette_role_colour_event_makes_its_palette_render_identity() -> None:
    """A section as authored whose colour event names a palette role takes the stop from
    the section's macro palette: the palette decides the bytes, so it is render identity
    and recorded, as a section colour's is."""
    from twinklr.core.sequencer.moving_heads.song_intent import SectionPalette

    first = {"s1": SectionPalette(palette_id="a", stops=("#FF0000", "#0000FF"))}
    second = {"s1": SectionPalette(palette_id="b", stops=("#0000FF", "#FF0000"))}
    plan = [section([event(3, 1, "color", color="PALETTE_PRIMARY")])]
    red, blue = render(plan, palettes=first), render(plan, palettes=second)

    assert red.fingerprint() != blue.fingerprint()
    assert red.frames != blue.frames
    assert red.render_record is not None
    assert red.render_record["palettes"] == {"s1": first["s1"].model_dump(mode="json")}


def test_a_colour_event_whose_gap_is_too_short_for_the_turn_does_not_play_and_never_refuses() -> (
    None
):
    """A template that repositions dark in 160 ms gaps: a colour event on the cue after a
    gap would have the transaction pass turn the wheel there too, which a 300 ms settle
    does not fit, and no dark window is long enough: it does not play (recorded), and the
    render plays every cue under the strict policy."""
    sweep = m.envelope_step("env", 10.0, 40.0, lit=(0.0, 0.92), period_beats=4.0)
    with m.registered_templates(m.loop_template_doc("events_tight_gaps", [sweep])):
        pipeline = render(
            [section([event(5, 1, "color", color="red")], template_id="events_tight_gaps")],
            fixture_group=rig(settle=300),
            job_config=m.family_job(HEADS, reposition_fallback="error", on_unplayable="error"),
        )

    (entry,) = looks(pipeline)["s1"]["events"]
    assert all(
        "the gap before the head's next cue is too short" in o["not_played"]
        for o in entry["heads"].values()
    )
    assert_wheels_turn_dark(Frames(pipeline))


def test_a_colour_event_the_part_never_shows_lit_is_recorded_and_the_render_goes_on() -> None:
    """In 3/4, a gobo change on the first beat of a `fly_in_cascade` part where every head
    is dark: moved a beat later, where two heads show it within a beat; the two heads that
    never show it before the section ends do not play it; the events after it still play
    (the byte matrix's waltz case)."""
    beat_grid = BeatGrid(
        bar_boundaries=[15.0 + 1500.0 * i for i in range(11)],
        beat_boundaries=[15.0 + 500.0 * i for i in range(31)],
        eighth_boundaries=BeatGrid._calculate_eighth_boundaries(
            [15.0 + 500.0 * i for i in range(31)]
        ),
        sixteenth_boundaries=BeatGrid._calculate_sixteenth_boundaries(
            [15.0 + 500.0 * i for i in range(31)]
        ),
        tempo_bpm=120.0,
        beats_per_bar=3,
        duration_ms=15015.0,
    )
    one = section(
        [
            event(1, 2, "strobe_fast"),
            event(1, 3, "open"),
            event(2, 1, "hit"),
            event(2, 3, "color", color="red"),
            event(3, 1, "gobo", gobo="dots"),
            event(4, 1, "closed"),
            event(4, 2, "hit"),
            event(4, 3, "pulse"),
        ],
        template_id="finite_snap_hold",
        bars=(1, 4),
    )
    one = one.model_copy(
        update={
            "parts": [
                one.parts[0],
                one.parts[0].model_copy(update={"start_bar": 3, "template_id": "fly_in_cascade"}),
            ]
        }
    )
    pipeline = render([one], beat_grid=beat_grid)

    assert_wheels_turn_dark(Frames(pipeline))
    events_ = [e for look in looks(pipeline).values() for e in look["events"]]
    assert len(events_) == 8
    (gobo,) = [e for e in events_ if e["action"] == "gobo"]
    assert {o["moved"]["direction"] for o in gobo["heads"].values()} == {"later"}
    assert any(
        o.get("not_played") == "the head never shows it lit before the section's end"
        for o in gobo["heads"].values()
    ), gobo["heads"]


# --- fix round 1: the bar grid, crashes, bounds, records ---------------------------------------


@pytest.mark.parametrize("pickup", [1, 2, 3])
@pytest.mark.parametrize("beats_per_bar", [4, 3])
def test_an_event_on_beat_one_lands_on_the_first_frame_of_its_bar_after_a_pickup(
    pickup: int, beats_per_bar: int
) -> None:
    """Pickup beats before bar 1 belong to no bar: `closed` at n.1 goes dark on the frame
    nearest bar n's downbeat, `hit` at a second section's downbeat plays (not dropped),
    and both trace that bar and beat."""
    beat_grid = m.pickup_grid(500.0, 8, pickup=pickup, beats_per_bar=beats_per_bar)
    plan = [
        section([event(3, 1, "closed"), event(3, 3, "open")], bars=(1, 4)),
        m.plan_section("s2", 5, 8, "mirror_wings", events=[event(5, 1, "hit")]),
    ]
    pipeline = render(plan, beat_grid=beat_grid)
    frames = Frames(pipeline)
    closed = frame_of(beat_grid.bar_boundaries[2])
    opened = frame_of(beat_grid.beat_boundaries[pickup + 2 * beats_per_bar + 2])

    for head in HEADS:
        dark = frames.dark(head)
        assert dark[closed] and not dark[closed - 1], head
        assert all(dark[i] for i in range(closed, opened)) and not dark[opened], head
    hit = looks(pipeline)["s2"]["events"][0]
    downbeat = frame_of(beat_grid.bar_boundaries[4])
    assert {o["played_ms"] for o in hit["heads"].values()} == {downbeat * FRAME}
    assert (hit["bar"], hit["beat"]) == (5, 1)


@pytest.mark.parametrize("pickup", [1, 2, 3])
@pytest.mark.parametrize("beats_per_bar", [4, 3])
def test_a_cue_just_before_a_section_end_binds_inside_it_at_its_nearest_beat(
    pickup: int, beats_per_bar: int
) -> None:
    """A lyric cue 60 ms after the section's last beat binds to that beat, numbered on the
    bar grid; the render plays it there."""
    beat_grid = m.pickup_grid(500.0, 8, pickup=pickup, beats_per_bar=beats_per_bar)
    last = pickup + 4 * beats_per_bar - 1  # the last beat of bar 4
    cue_ms = int(beat_grid.beat_boundaries[last]) + 60
    plan = ChoreographyPlan(
        sections=[
            section([event(1, 1, "hit", moment_cue_id="end")], bars=(1, 4), moment_cues=["end"]),
            m.plan_section("s2", 5, 8, "mirror_wings"),
        ],
        overall_strategy="",
    )
    lyrics = LyricContextModel(
        has_lyrics=True,
        vocal_coverage_pct=0.25,
        moment_cues=[
            MomentCue(
                cue_id="end",
                timestamp_ms=cue_ms,
                section_id="s1",
                emphasis="HIGH",
                text="the end",
                visual_hint="Accent the line.",
            )
        ],
    )
    end = int(beat_grid.bar_boundaries[4])
    song = [
        SongSectionRef(section_id="s1", name="s1", start_ms=0, end_ms=end),
        SongSectionRef(section_id="s2", name="s2", start_ms=end, end_ms=int(beat_grid.duration_ms)),
    ]
    bound = bind_lyric_moment_cues(plan, lyrics, beat_grid, song)
    (hit,) = bound.sections[0].events

    assert (hit.bar, hit.beat, hit.cue_ms) == (4, beats_per_bar, cue_ms)
    pipeline = render(bound.sections, beat_grid=beat_grid)
    (entry,) = looks(pipeline)["s1"]["events"]
    at = frame_of(beat_grid.beat_boundaries[last]) * FRAME
    assert {o["played_ms"] for o in entry["heads"].values()} == {at}
    assert pipeline.render_record is not None
    (cue,) = pipeline.render_record["lyric_cues"]
    assert cue["events"][0]["offset_ms"] == dict.fromkeys(HEADS, at - cue_ms)
    assert f"({at - cue_ms:+d} ms from the lyric at {cue_ms} ms)" in describe_lyric_cue(cue)


def test_an_event_that_cannot_be_placed_is_traced_warned_and_repaired() -> None:
    """An event in a bar past the beat grid, on a beat its bar does not have, or outside
    its section: a trace entry saying why, a per-section warning; the binder records the
    bar past the grid and moves a beat its bar lacks for the planner."""
    beat_grid = grid(120, bars=8)
    plan = [
        section(
            [event(9, 1, "hit"), event(3, 5, "hit"), event(4, 1, "closed")],
            bars=(1, 3),
        )
    ]
    pipeline = render(plan, beat_grid=beat_grid)
    entries = looks(pipeline)["s1"]["events"]
    reasons = sorted(e["not_played"] for e in entries if "not_played" in e)
    assert reasons == [
        "bar 3 has 4 detected beats, not 5",
        "bar 4 lies outside its section (bars 1-3)",
        "bar 9 lies outside its section (bars 1-3)",
    ]
    assert pipeline.render_record is not None
    assert any(
        "not played on every head" in d["message"] for d in pipeline.render_record["diagnostics"]
    )
    song = [SongSectionRef(section_id="s1", name="s1", start_ms=0, end_ms=16015)]
    whole = ChoreographyPlan(
        sections=[section([event(8, 2, "hit"), event(3, 5, "hit")], bars=(1, 9))],
        overall_strategy="",
    )
    repaired = bind_lyric_moment_cues(whole, None, beat_grid, song)
    said = {r.item: (r.action.value, r.reason) for r in repaired.repairs}
    assert said["hit event at bar 3 beat 5"][1] == "bar 3 has 4 detected beats: moved to beat 4"
    past = ChoreographyPlan(
        sections=[section([event(10, 1, "hit")], bars=(1, 10))], overall_strategy=""
    )
    (record,) = bind_lyric_moment_cues(past, None, beat_grid, song).repairs
    assert record.reason.startswith("bar 10 lies beyond the detected beat grid")


@pytest.mark.parametrize(
    ("template_id", "bpm", "beats_per_bar", "events"),
    [
        ("fly_out_cascade", 170, 4, [(3, 3, "color"), (4, 1, "closed")]),
        ("fly_in_cascade", 170, 4, [(3, 4, "color")]),
        ("fly_in_cascade", 180, 4, [(3, 4, "color")]),
        ("fly_in_cascade", 170, 3, [(3, 3, "color")]),
    ],
)
def test_a_colour_event_at_a_fast_tempo_never_crashes_the_render(
    template_id: str, bpm: float, beats_per_bar: int, events: list[tuple[int, int, str]]
) -> None:
    """The review's crash (an unguarded `next` past the head's last cue): the render
    finishes, every event is traced, every wheel turn is dark."""
    beat_grid = m.pickup_grid(60_000 / bpm, 8, pickup=0, beats_per_bar=beats_per_bar)
    planned = [event(b, k, a, **({"color": "red"} if a == "color" else {})) for b, k, a in events]
    pipeline = render(
        [section(planned, template_id=template_id)],
        beat_grid=beat_grid,
        fixture_group=rig(close=20, settle=150),
    )

    assert len(looks(pipeline)["s1"]["events"]) == len(events)
    assert_wheels_turn_dark(Frames(pipeline))


def test_a_colour_event_that_cannot_dip_is_late_by_at_most_a_beat_else_not_played() -> None:
    """At 170 BPM on owner-like timings over `mirror_wings` (no dark window), a colour
    change on 3.1 cannot dip (180 ms > 176 ms) and a later `closed` would reveal it bars
    late: not played, said so; the hit inside the `closed` still lights; repair predicts
    it with the render's own test."""
    beat_grid = grid(170)
    timings = rig(close=20, settle=150)
    events = [event(3, 1, "color", color="red"), event(6, 1, "closed"), event(7, 2, "hit")]
    plan = [section(events)]
    pipeline = render(plan, beat_grid=beat_grid, fixture_group=timings)
    colour, _, hit = looks(pipeline)["s1"]["events"]

    assert all("within 1 beat" in o["not_played"] for o in colour["heads"].values())
    assert all(o["how"] == "lit_from_dark" for o in hit["heads"].values())
    offer = rig_offer(timings, beat_grid)
    repaired = repair_rig_intent(
        ChoreographyPlan(sections=plan, overall_strategy=""), offer, {}, beat_grid
    )
    (record,) = [r for r in repaired.repairs if r.item.startswith("event at bar 3 beat 1")]
    assert "does not fit half the beat before it (176 ms)" in record.reason
    assert "it does not play" in record.reason


def test_a_strobe_slows_only_on_the_beats_it_cannot_follow_and_repair_agrees() -> None:
    """Four bars at 96 BPM then four at 140 on a shutter rig with 45 ms latency: sixteenths
    fit the slow bars and not the fast ones; the render plays 4 then 2 flashes a beat, the
    trace and the repair count the same slowed beats."""
    beat_grid = m.bars_grid(*([625.0] * 4 + [428.6] * 4))
    shutter = rig(close=45, shutter_only=True)
    plan = [section([event(2, 1, "strobe_medium")])]
    pipeline = render(plan, beat_grid=beat_grid, fixture_group=shutter)
    frames = Frames(pipeline)
    slow_bar = range(frame_of(beat_grid.bar_boundaries[1]), frame_of(beat_grid.bar_boundaries[2]))
    fast_bar = range(frame_of(beat_grid.bar_boundaries[5]), frame_of(beat_grid.bar_boundaries[6]))

    assert dark_runs(frames.dark("MH1"), slow_bar) == 16
    assert dark_runs(frames.dark("MH1"), fast_bar) == 8
    (entry,) = looks(pipeline)["s1"]["events"]
    degraded = entry["heads"]["MH1"]["degraded"]
    repaired = repair_rig_intent(
        ChoreographyPlan(sections=plan, overall_strategy=""),
        rig_offer(shutter, beat_grid),
        {},
        beat_grid,
    )
    (record,) = repaired.repairs
    assert "on 16 of 28 beats" in degraded and "on 16 of its 28 beats" in record.reason


def test_closed_and_open_on_one_beat_and_an_open_with_nothing_to_end_are_traced() -> None:
    pipeline = render([section([event(3, 1, "closed"), event(3, 1, "open"), event(4, 1, "open")])])
    closed, opened, extra = looks(pipeline)["s1"]["events"]

    assert closed["heads"]["MH1"] == {"not_played": "another shutter event on its beat replaces it"}
    assert opened["heads"]["MH1"]["plays"] == "the template's own shutter and level"
    assert extra["heads"]["MH1"]["not_played"].startswith("nothing to open")


# --- fix round 2 --------------------------------------------------------------------------


def first_lit_with(
    frames: Frames, head: str, wheel: str, state: str, from_frame: int
) -> int | None:
    """The first frame from `from_frame` the head shows `state` lit for three frames running,
    read from the bytes."""
    dark, states = frames.dark(head), frames.state(head, wheel)
    for i in range(from_frame, len(dark) - 2):
        if all(not dark[i + k] and states[i + k] == state for k in range(3)):
            return i
    return None


def cascade_repair(plan: list[PlanSection], template_id: str, beat_grid: BeatGrid) -> list[str]:
    from twinklr.core.sequencer.moving_heads.pipeline import admit_templates

    offer = admit_templates(
        [template_id],
        beat_grid=beat_grid,
        fixture_group=rig(close=20, settle=150),
        initial_states=m.family_job(HEADS).moving_heads.initial_states,
        failure_mode="strict",
    ).offer
    repaired = repair_rig_intent(
        ChoreographyPlan(sections=plan, overall_strategy=""), offer, {}, beat_grid
    )
    return [r.reason for r in repaired.repairs]


@pytest.mark.parametrize(
    ("template_id", "planned", "moved"),
    [("fly_in_cascade", (3, 1), (3, 3)), ("fly_out_cascade", (3, 4), (4, 2))],
)
def test_a_colour_event_no_head_shows_within_a_beat_moves_to_where_the_most_heads_do(
    template_id: str, planned: tuple[int, int], moved: tuple[int, int]
) -> None:
    """The review's case (120 BPM): every head is dark on the planned beat and its next
    reveal is two or three beats away. The event moves later, on every head, to the beat
    within a bar where the most heads show it within a beat; read from the bytes, no head
    shows blue before that beat and every head shows it lit within a beat of it. The
    repair predicts the same beat."""
    beat_grid = grid(120)
    plan = [section([event(*planned, "color", color="blue")], template_id=template_id)]
    pipeline = render(plan, fixture_group=rig(close=20, settle=150))
    frames = Frames(pipeline)
    (entry,) = looks(pipeline)["s1"]["events"]
    at = beat_frame(beat_grid, *moved)

    for head, outcome in entry["heads"].items():
        assert (outcome["moved"]["bar"], outcome["moved"]["beat"]) == moved
        assert outcome["moved"]["direction"] == "later"
        shown = first_lit_with(frames, head, "color", "blue", 0)
        assert shown is not None and at - 2 <= shown <= at + 26, (head, shown, at)
    assert_wheels_turn_dark(frames)
    assert any(
        f"it moves later to bar {moved[0]} beat {moved[1]}" in reason
        for reason in cascade_repair(plan, template_id, beat_grid)
    )


def test_a_colour_event_some_head_shows_on_time_plays_and_the_dark_heads_show_it_later() -> None:
    """`fly_in_cascade` 3.3: MH1 and MH4 lit on the beat show blue on it; MH2 and MH3,
    dark there, show it from their next reveal (traced late, read from the bytes); the
    repair names the late heads."""
    beat_grid = grid(120)
    plan = [section([event(3, 3, "color", color="blue")], template_id="fly_in_cascade")]
    pipeline = render(plan, fixture_group=rig(close=20, settle=150))
    frames = Frames(pipeline)
    (entry,) = looks(pipeline)["s1"]["events"]
    at = beat_frame(beat_grid, 3, 3)

    for head in ("MH1", "MH4"):
        assert "moved" not in entry["heads"][head] and "late" not in entry["heads"][head]
        assert first_lit_with(frames, head, "color", "blue", 0) == at
    for head in ("MH2", "MH3"):
        late = entry["heads"][head]["late"]["late_ms"]
        assert first_lit_with(frames, head, "color", "blue", 0) == at + late // FRAME
    reasons = cascade_repair(plan, "fly_in_cascade", beat_grid)
    assert any(r.startswith("it shows after its beat on MH2") and "MH3" in r for r in reasons)


def test_a_colour_event_no_head_shows_before_the_section_ends_does_not_play() -> None:
    """A `closed` from 3.1 to the section's end: a colour on 4.1 is never shown, nor on any
    beat within a bar: not played on every head (traced, and predicted by the repair), and
    the bytes never show it lit."""
    plan = [section([event(3, 1, "closed"), event(4, 1, "color", color="blue")])]
    pipeline = render(plan, fixture_group=rig(close=20, settle=150))
    frames = Frames(pipeline)
    colour = looks(pipeline)["s1"]["events"][1]

    assert all("not_played" in o for o in colour["heads"].values())
    assert all(first_lit_with(frames, h, "color", "blue", 0) is None for h in HEADS)
    assert any("it does not play" in r for r in cascade_repair(plan, "mirror_wings", grid(120)))


def test_a_cue_bound_hit_moves_to_the_beat_nearest_its_lyric_and_says_where() -> None:
    """`fly_in_cascade` 3.1 is dark on every head; the lyric is 30 ms after it. A cue-bound
    hit moves to the lit beat nearest the lyric (an unbound one to the beat the most heads
    show, a later one first); the lyric cue's line names the beat it played on and its
    signed offset from the lyric; the repair predicts the same beat."""
    beat_grid = grid(120)
    cue_ms = int(beat_grid.beat_time_ms(3, 1) or 0) + 30
    hit = event(3, 1, "hit", moment_cue_id="c", cue_ms=cue_ms, cue_emphasis="HIGH")
    plan = [section([hit], template_id="fly_in_cascade", moment_cues=["c"])]
    pipeline = render(plan)
    (entry,) = looks(pipeline)["s1"]["events"]
    moved = {
        (o["moved"]["bar"], o["moved"]["beat"]) for o in entry["heads"].values() if "moved" in o
    }
    unbound = looks(render([section([event(3, 1, "hit")], template_id="fly_in_cascade")]))
    unbound_moved = {
        (o["moved"]["bar"], o["moved"]["beat"])
        for o in unbound["s1"]["events"][0]["heads"].values()
        if "moved" in o
    }

    # 3.2 is dark on every head; the lit beats nearest are 2.4 (530 ms before the lyric)
    # and 3.3 (970 ms after), which an unbound hit takes (two heads, a later one first).
    ((bar, beat),) = moved
    assert (bar, beat) == (2, 4) and unbound_moved == {(3, 3)}
    assert {o["moved"]["direction"] for o in entry["heads"].values() if "moved" in o} == {"earlier"}
    assert pipeline.render_record is not None
    (cue,) = pipeline.render_record["lyric_cues"]
    line = describe_lyric_cue(cue)
    assert f"hit planned at bar 3 beat 1, played at bar {bar} beat {beat}" in line
    offset = cue["events"][0]["offset_ms"]["MH2"]
    assert f"({offset:+d} ms from the lyric" in line and offset < 0
    reasons = cascade_repair(plan, "fly_in_cascade", beat_grid)
    assert any(f"to bar {bar} beat {beat}" in r and "nearest its lyric" in r for r in reasons)


def test_a_hit_inside_a_strobe_is_traced_on_both() -> None:
    """78.3 BPM, `strobe_slow` from 3.1, a HIGH hit on 3.3: the hit lights frames the strobe
    holds dark (kept for the owner's view); the hit's trace says how many, and the strobe's
    says which hit lights them; the bytes agree."""
    beat_grid = grid(78.3)
    strobe = [event(3, 1, "strobe_slow"), event(4, 1, "open")]
    hit = event(3, 3, "hit", cue_emphasis="HIGH")
    pipeline = render([section([*strobe, hit])], beat_grid=beat_grid)
    plain = Frames(render([section(strobe)], beat_grid=beat_grid))
    frames = Frames(pipeline)
    entries = looks(pipeline)["s1"]["events"]
    (strobe_entry,) = [e for e in entries if e["action"] == "strobe_slow"]
    (hit_entry,) = [e for e in entries if e["action"] == "hit"]

    relit = sum(
        1
        for i, (a, b) in enumerate(zip(frames.dark("MH1"), plain.dark("MH1"), strict=True))
        if b and not a
    )
    said = hit_entry["heads"]["MH1"]["lights_flash_dark"]
    assert said == [f"{relit} frame(s) the strobe_slow at bar 3 beat 1 holds dark"]
    assert strobe_entry["heads"]["MH1"]["lit_by_hits"][0].endswith(
        f"(bar 3 beat 3) lights {relit} of its dark frames"
    )
