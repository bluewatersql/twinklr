"""W8: the planner's section transitions, read from the encoded frames.

Every mode at a boundary the heads must reposition across (`finite_snap_hold` into
`mirror_wings`, the parity rows' pair, 120 BPM), against no transition; both edges and
their precedence; the song's first ENTRY and last EXIT against the heads at rest; a colour
change across a lit transition; events, intensity and a show's rest inside a window;
pickups, 3/4 and a variable grid; per-channel strategies; fallbacks. Bytes are read through
the rig's profile (`test_events_render.Frames`), not the renderer's helpers.
"""

from __future__ import annotations

from collections.abc import Iterator, Sequence
import math
import random
from typing import Any

import pytest

from tests.support import moving_heads as m
from tests.unit.sequencer.moving_heads.test_events_render import (
    FRAME,
    HEADS,
    Frames,
    assert_wheels_turn_dark,
    beat_frame,
    event,
    frame_of,
    grid,
    looks,
    render,
    rig,
)
from twinklr.core.agents.sequencer.moving_heads.models import (
    ChoreographyPlan,
    PlanEvent,
    PlanSection,
)
from twinklr.core.agents.sequencer.moving_heads.rig_repair import repair_rig_intent
from twinklr.core.config.fixtures import FixtureGroup
from twinklr.core.sequencer.models.transition import PlanTransition
from twinklr.core.sequencer.moving_heads.song_intent import rig_offer
from twinklr.core.sequencer.moving_heads.transitions import CROSSFADE_FLOOR, describe_transitions
from twinklr.core.sequencer.timing.beat_grid import BeatGrid

MODES = ("snap", "crossfade", "morph", "sweep", "fade_via_black", "blackout")


@pytest.fixture(autouse=True)
def _catalog() -> Iterator[None]:
    with m.family_catalog():
        yield


def transition(
    edge: str,
    mode: str,
    length: str = "BAR",
    *,
    curve: str = "linear",
    split: str = "QUARTER",
    channels: Sequence[tuple[str, str]] = (),
) -> dict[str, Any]:
    return {
        "edge": edge,
        "mode": mode,
        "length": length,
        "curve": curve,
        "split": split,
        "channels": [{"channel": c, "strategy": s} for c, s in channels],
    }


def pair(
    entry: dict[str, Any] | None = None,
    exit_: dict[str, Any] | None = None,
    *,
    first: str = "finite_snap_hold",
    second: str = "mirror_wings",
    **second_fields: Any,
) -> list[PlanSection]:
    """Two sections over bars 1-4 and 5-8: `first` (its EXIT `exit_`), then `second` (its
    ENTRY `entry`)."""
    return [
        m.plan_section("s1", 1, 4, first, transitions=[exit_] if exit_ else []),
        m.plan_section("s2", 5, 8, second, transitions=[entry] if entry else [], **second_fields),
    ]


def transitions_of(pipeline: Any) -> list[dict[str, Any]]:
    return [t for look in looks(pipeline).values() for t in look.get("transitions", [])]


def window_frames(entry: dict[str, Any]) -> range:
    a, b = entry["window_ms"]
    return range(a // FRAME, b // FRAME)


def pan(frames: Frames, head: str, name: str = "pan") -> list[int]:
    axis = frames.profile.axes[name]  # type: ignore[index]
    return [
        f[axis.coarse_offset] << 8 | f[axis.fine_offset]
        if axis.fine_offset is not None
        else f[axis.coarse_offset]
        for f in frames.raw(head)
    ]


def aim(frames: Frames, head: str) -> list[tuple[int, int]]:
    return list(zip(pan(frames, head), pan(frames, head, "tilt"), strict=True))


def lit_steps_within_speed(frames: Frames, head: str, window: range) -> bool:
    axis = frames.profile.axes["pan"]
    low, high = axis.word_range
    per_word = (axis.physical_max - axis.physical_min) / (high - low)
    step = (axis.travel_speed_per_s or 0) * FRAME / 1000 + per_word
    words, dark = pan(frames, head), frames.dark(head)
    return all(
        abs(words[i] - words[i - 1]) * per_word <= step
        for i in window
        if not dark[i] and not dark[i - 1]
    )


# --- every mode at one boundary ----------------------------------------------------------


def test_without_a_transition_the_heads_enter_dark_after_the_boundary() -> None:
    """The anchor: the incoming section's dark entry window right after the boundary."""
    frames = Frames(render(pair()))
    b = frame_of(grid(120).bar_boundaries[4])

    assert all(frames.dark(h)[b] for h in HEADS)
    assert not any(frames.dark(h)[b - 1] for h in HEADS)


def test_snap_goes_dark_before_the_boundary_and_is_in_place_lit_on_its_frame() -> None:
    pipeline = render(pair(transition("ENTRY", "snap")))
    frames = Frames(pipeline)
    b = frame_of(grid(120).bar_boundaries[4])
    (entry,) = transitions_of(pipeline)

    for head in HEADS:
        dark = frames.dark(head)
        start, end = entry["heads"][head]["dark_ms"]
        assert end == b * FRAME and start < end
        assert all(dark[i] for i in range(start // FRAME, b))
        assert not dark[b] and not dark[start // FRAME - 1]


def test_crossfade_hands_the_light_over_at_the_boundary_never_dark() -> None:
    """A quarter of the bar before the boundary to three quarters after: the dimmer eases
    down to half the lower look's level on the boundary and up again; never dark; the aim
    moves within the head's speed and is the incoming section's from the window's end."""
    pipeline = render(pair(transition("ENTRY", "crossfade")))
    plain = Frames(render(pair()))
    frames = Frames(pipeline)
    (entry,) = transitions_of(pipeline)
    b = frame_of(grid(120).bar_boundaries[4])
    window = window_frames(entry)

    assert entry["window_ms"] == [(b - 25) * FRAME, (b + 75) * FRAME]
    for head in HEADS:
        dimmer = frames.dimmer(head)
        assert not any(frames.dark(head)[i] for i in window)
        assert min(dimmer[i] for i in window) == pytest.approx(255 * CROSSFADE_FLOOR, abs=2)
        assert dimmer[b - 1] == min(dimmer[i] for i in window) or dimmer[b] == min(
            dimmer[i] for i in window
        )
        down = [dimmer[i] for i in range(window.start, b)]
        up = [dimmer[i] for i in range(b, window.stop)]
        assert down == sorted(down, reverse=True) and up == sorted(up)
        assert lit_steps_within_speed(frames, head, window)
        after = range(window.stop, window.stop + 50)
        assert [pan(frames, head)[i] for i in after] == [pan(plain, head)[i] for i in after]


def test_morph_eases_every_channel_from_the_window_start_and_sweep_holds_then_travels() -> None:
    """Both centred on the boundary, halfway at a quarter of the window: MORPH's aim moves
    from its first frame; SWEEP holds the outgoing aim to the split point, then travels."""
    morph = render(pair(transition("ENTRY", "morph")))
    sweep = render(pair(transition("ENTRY", "sweep")))
    (m_entry,), (s_entry,) = transitions_of(morph), transitions_of(sweep)
    b = frame_of(grid(120).bar_boundaries[4])
    m_frames, s_frames = Frames(morph), Frames(sweep)

    assert m_entry["window_ms"] == s_entry["window_ms"] == [(b - 50) * FRAME, (b + 50) * FRAME]
    split = s_entry["split_ms"] // FRAME
    assert split == b - 25
    for head in HEADS:
        held = aim(s_frames, head)
        assert len({held[i] for i in range(b - 50, split)}) == 1
        assert held[split + 10] != held[split - 1]
        moving = aim(m_frames, head)
        assert moving[b - 40] != moving[b - 51]
        assert not any(s_frames.dark(head)[i] for i in window_frames(s_entry))
        assert not any(m_frames.dark(head)[i] for i in window_frames(m_entry))
        assert lit_steps_within_speed(m_frames, head, window_frames(m_entry))
        assert lit_steps_within_speed(s_frames, head, window_frames(s_entry))


def test_fade_via_black_fades_to_dark_at_the_boundary_and_up_after_the_change() -> None:
    pipeline = render(pair(transition("ENTRY", "fade_via_black")))
    frames = Frames(pipeline)
    (entry,) = transitions_of(pipeline)
    b = frame_of(grid(120).bar_boundaries[4])
    window = window_frames(entry)

    for head in HEADS:
        dimmer, dark = frames.dimmer(head), frames.dark(head)
        start, end = (t // FRAME for t in entry["heads"][head]["dark_ms"])
        assert start == b and all(dark[i] for i in range(start, end))
        down = [dimmer[i] for i in range(window.start, b)]
        up = [dimmer[i] for i in range(end, window.stop)]
        assert down == sorted(down, reverse=True) and len({v for v in down if 0 < v < 255}) >= 2
        assert up == sorted(up) and len({v for v in up if 0 < v < 255}) >= 2


def test_blackout_is_dark_over_the_whole_window_and_cuts_in_at_its_end() -> None:
    pipeline = render(pair(transition("ENTRY", "blackout")))
    frames = Frames(pipeline)
    (entry,) = transitions_of(pipeline)
    window = window_frames(entry)

    for head in HEADS:
        dark = frames.dark(head)
        assert all(dark[i] for i in window)
        assert not dark[window.start - 1] and not dark[window.stop]


def test_every_mode_is_distinct_from_the_others_and_from_no_transition() -> None:
    """MH1's bytes over the two bars around the boundary differ for every pair of modes,
    and each from the render without a transition."""
    b = frame_of(grid(120).bar_boundaries[4])
    span = range(b - 60, b + 100)
    bytes_of = {
        mode: [Frames(render(pair(transition("ENTRY", mode)))).raw("MH1")[i] for i in span]
        for mode in MODES
    }
    bytes_of["none"] = [Frames(render(pair())).raw("MH1")[i] for i in span]

    names = sorted(bytes_of)
    for i, a in enumerate(names):
        for other in names[i + 1 :]:
            assert bytes_of[a] != bytes_of[other], (a, other)


# --- edges --------------------------------------------------------------------------------


def test_an_exit_plays_the_same_change_as_an_entry_and_an_entry_replaces_it() -> None:
    """The EXIT of the section before shapes the same boundary as the ENTRY of the one
    after: the same bytes. With both, the ENTRY plays and the trace says it replaced the
    EXIT."""
    crossfade = transition("ENTRY", "crossfade")
    as_exit = Frames(render(pair(None, {**crossfade, "edge": "EXIT"})))
    as_entry = Frames(render(pair(crossfade)))
    both = render(pair(crossfade, transition("EXIT", "blackout")))

    assert as_exit.raw("MH1") == as_entry.raw("MH1")
    assert Frames(both).raw("MH1") == as_entry.raw("MH1")
    (entry,) = transitions_of(both)
    assert entry["edge"] == "ENTRY" and "'s EXIT (blackout over BAR" in entry["replaces"]


@pytest.mark.parametrize("mode", ["crossfade", "morph", "fade_via_black"])
def test_the_first_entry_comes_up_from_the_heads_rest_inside_the_section(mode: str) -> None:
    """The song's first section: no light before it; the light comes up from dark over the
    window (from the head's rest), reaching the section's own level by its end."""
    sections = [m.plan_section("s1", 1, 8, "mirror_wings", transitions=[transition("ENTRY", mode)])]
    pipeline = render(sections)
    frames = Frames(pipeline)
    (entry,) = transitions_of(pipeline)
    window = window_frames(entry)

    assert entry["against"].startswith("the head at rest")
    for head in HEADS:
        dimmer = frames.dimmer(head)
        assert all(dimmer[i] == 0 for i in range(window.start))
        lit = [dimmer[i] for i in window if dimmer[i]]
        assert lit[0] < 128 and dimmer[window.stop] == 255


def test_the_last_exit_comes_to_rest_dark_by_the_sections_end() -> None:
    """FADE_VIA_BLACK on the last section: the light fades out over the window, dark at
    the end of the section's cues; nothing lights after."""
    sections = [
        m.plan_section(
            "s1", 1, 8, "mirror_wings", transitions=[transition("EXIT", "fade_via_black")]
        )
    ]
    pipeline = render(sections)
    frames = Frames(pipeline)
    (entry,) = transitions_of(pipeline)
    window = window_frames(entry)

    for head in HEADS:
        dimmer = frames.dimmer(head)
        down = [dimmer[i] for i in window if i < window.stop]
        assert down == sorted(down, reverse=True) and down[-1] <= 10
        assert all(v == 0 for v in dimmer[window.stop :])


# --- composition ---------------------------------------------------------------------------


def test_a_colour_change_across_a_crossfade_dips_dark_at_the_split_point_for_the_turn() -> None:
    """Red into blue on owner-like timings: the wheel turns in a dark cut at the boundary
    (the crossfade's split point), in place of the boundary's dip; lit around it."""
    pipeline = render(
        [
            m.plan_section("s1", 1, 4, "mirror_wings", color="red"),
            m.plan_section(
                "s2",
                5,
                8,
                "mirror_wings",
                color="blue",
                transitions=[transition("ENTRY", "crossfade")],
            ),
        ],
        fixture_group=rig(close=20, settle=150),
    )
    frames = Frames(pipeline)
    (entry,) = transitions_of(pipeline)
    look = looks(pipeline)["s2"]

    assert_wheels_turn_dark(frames)
    for head in HEADS:
        start, end = (t // FRAME for t in entry["heads"][head]["dark_ms"])
        assert entry["heads"][head]["wheels_turn"] == {"color": ["red", "blue"]}
        dark = frames.dark(head)
        assert all(dark[i] for i in range(start, end))
        assert not dark[start - 1] and not dark[end]
        assert frames.state(head, "color")[start - 1] == "red"
        assert frames.state(head, "color")[end] == "blue"
    assert all("in_transition" in b for b in look["boundaries"])


def test_an_event_in_the_window_plays_and_the_window_yields_a_hit_plays_on_it() -> None:
    """A `closed` on the incoming section's beat 5.3 ends the crossfade's window there; a
    hit on 5.2 inside it plays on the transition's level."""
    pipeline = render(
        pair(
            transition("ENTRY", "crossfade"),
            events=[event(5, 2, "hit"), event(5, 3, "closed"), event(6, 1, "open")],
        )
    )
    frames = Frames(pipeline)
    (entry,) = transitions_of(pipeline)
    g = grid(120)
    closed = beat_frame(g, 5, 3)
    hit = next(e for e in looks(pipeline)["s2"]["events"] if e["action"] == "hit")

    assert entry["window_ms"][1] <= closed * FRAME
    assert any("closed at bar 5 beat 3" in why for why in entry["clamped"])
    for head in HEADS:
        assert frames.dark(head)[closed]
        assert hit["heads"][head]["played_ms"] == beat_frame(g, 5, 2) * FRAME
        assert frames.dimmer(head)[beat_frame(g, 5, 2)] == 255


def test_intensity_resumes_after_the_transition_on_an_accent_and_it_starts_at_the_outgoing_level() -> (
    None
):
    """INTENSE into DRAMATIC with a morph: the transition starts at the level the outgoing
    section plays as shaped (no jump), and the incoming section's first frame after it is an
    accent at the top."""
    pipeline = render(
        [
            m.plan_section("s1", 1, 4, "mirror_wings", intensity="INTENSE"),
            m.plan_section(
                "s2",
                5,
                8,
                "mirror_wings",
                intensity="DRAMATIC",
                transitions=[transition("ENTRY", "morph", split="HALF")],
            ),
        ]
    )
    frames = Frames(pipeline)
    (entry,) = transitions_of(pipeline)
    window = window_frames(entry)

    for head in HEADS:
        dimmer = frames.dimmer(head)
        assert abs(dimmer[window.start] - dimmer[window.start - 1]) <= 4
        assert dimmer[window.stop] == 255


def test_a_show_rest_inside_the_window_is_dark() -> None:
    b = grid(120).bar_boundaries[4]
    rest = (round(b) + 200, round(b) + 600)
    frames = Frames(render(pair(transition("ENTRY", "crossfade")), dark_spans=(rest,)))

    for head in HEADS:
        assert all(frames.dark(head)[i] for i in range(frame_of(rest[0]) + 1, frame_of(rest[1])))


@pytest.mark.parametrize(
    ("beat_grid", "beats_before"),
    [
        (m.pickup_grid(500.0, 8, pickup=2), 1),
        (m.pickup_grid(500.0, 8, pickup=1, beats_per_bar=3), 0.75),
    ],
    ids=["pickup2_4/4", "pickup1_3/4"],
)
def test_the_window_counts_beats_from_the_bars_downbeat(
    beat_grid: BeatGrid, beats_before: float
) -> None:
    """A crossfade of a bar split a quarter: a quarter of the bar's beats before the
    downbeat of bar 5, counted on the bar grid (a pickup shifts nothing; a 3/4 bar is three
    beats)."""
    pipeline = render(pair(transition("ENTRY", "crossfade")), beat_grid=beat_grid)
    (entry,) = transitions_of(pipeline)
    downbeat = beat_grid.bar_boundaries[4]

    assert entry["boundary_ms"] == frame_of(downbeat) * FRAME
    assert entry["window_ms"][0] == frame_of(downbeat - beats_before * 500) * FRAME
    bar = beat_grid.beats_per_bar * 500
    assert entry["window_ms"][1] == frame_of(downbeat + bar - beats_before * 500) * FRAME


def test_on_a_variable_grid_the_window_follows_the_detected_beats() -> None:
    beat_grid = m.bars_grid(*[(560.0, 420.0, 600.0, 380.0)[i % 4] for i in range(8)])
    pipeline = render(pair(transition("ENTRY", "morph")), beat_grid=beat_grid)
    (entry,) = transitions_of(pipeline)
    beats = beat_grid.beat_boundaries
    index = beat_grid.beat_index(5, 1)
    assert index is not None

    assert entry["window_ms"] == [
        frame_of(beats[index - 2]) * FRAME,
        frame_of(beats[index + 2]) * FRAME,
    ]


# --- strategies and fallbacks ----------------------------------------------------------------


def test_an_aim_snap_strategy_moves_the_aim_in_a_dark_cut_at_the_split_point() -> None:
    """Pan and tilt `snap` in a crossfade: a head whose aim changes across the boundary
    moves in a dark cut at the split point (the boundary), its light handing over around
    it; one whose aim does not has no cut."""
    snapped = transition("ENTRY", "crossfade", channels=[("pan", "snap"), ("tilt", "snap")])
    pipeline = render(pair(snapped))
    frames = Frames(pipeline)
    (entry,) = transitions_of(pipeline)

    cut = [h for h in HEADS if "dark_ms" in entry["heads"][h]]
    assert cut
    for head in cut:
        start, end = (t // FRAME for t in entry["heads"][head]["dark_ms"])
        assert all(frames.dark(head)[i] for i in range(start, end))
        assert aim(frames, head)[start - 1] != aim(frames, head)[end]
        assert "moves" in entry["heads"][head]["plays"]


def test_a_wheel_strategy_that_blends_plays_as_snap_and_says_so() -> None:
    pipeline = render(pair(transition("ENTRY", "morph", channels=[("color", "smooth")])))
    (entry,) = transitions_of(pipeline)

    for outcome in entry["heads"].values():
        assert outcome["strategies_played_otherwise"] == [
            "color smooth: a wheel cannot blend; it plays as snap"
        ]


def test_a_lit_move_faster_than_the_head_travels_moves_in_a_dark_cut_instead() -> None:
    """On heads travelling 110°/s a beat-long morph cannot carry the aim lit: it moves in a
    dark cut at the split point, recorded, read dark from the bytes; over a bar it moves
    lit."""
    payload = m.family_rig(HEADS).model_dump(mode="json")
    for fixture in payload["fixtures"]:
        for name in ("pan", "tilt"):
            fixture["config"]["physical_profile"]["axes"][name]["travel_speed_per_s"] = 110.0
    from twinklr.core.config.fixtures import FixtureGroup

    slow = FixtureGroup.model_validate(payload)
    beat = render(pair(transition("ENTRY", "morph", "BEAT")), fixture_group=slow)
    bar = render(pair(transition("ENTRY", "morph", "BAR")), fixture_group=slow)
    (entry,), (lit,) = transitions_of(beat), transitions_of(bar)
    frames = Frames(beat)

    for head in HEADS:
        outcome = entry["heads"][head]
        assert "faster than the head travels (110 degree/s)" in outcome["fallback"]
        start, end = (t // FRAME for t in outcome["dark_ms"])
        assert all(frames.dark(head)[i] for i in range(start, end))
        assert "fallback" not in lit["heads"][head] and "dark_ms" not in lit["heads"][head]
        assert lit_steps_within_speed(Frames(bar), head, window_frames(lit))


def test_a_transition_longer_than_its_parts_is_shortened_by_repair() -> None:
    """Two two-bar sections: an EIGHT_BARS crossfade cannot fit; repair shortens it to the
    longest length whose placement fits (TWO_BARS split a quarter: half a bar before, a
    bar and a half after)."""
    beat_grid = grid(120, bars=4)
    sections = [
        m.plan_section("s1", 1, 2, "finite_snap_hold"),
        m.plan_section(
            "s2", 3, 4, "mirror_wings", transitions=[transition("ENTRY", "crossfade", "EIGHT_BARS")]
        ),
    ]
    repaired = repair_rig_intent(
        ChoreographyPlan(sections=sections, overall_strategy=""),
        rig_offer(rig(), beat_grid),
        {},
        beat_grid,
    )

    (record,) = [r for r in repaired.repairs if r.item.startswith("entry transition")]
    assert record.action.value == "adjusted" and "shortened to TWO_BARS" in record.reason
    assert repaired.sections[1].entry is not None
    assert repaired.sections[1].entry.length.value == "TWO_BARS"


@pytest.mark.parametrize(("bpm", "plays"), [(120, True), (240, False)])
def test_repair_predicts_a_window_yielding_to_an_event_seen_before_it(
    bpm: int, plays: bool
) -> None:
    """A colour change on the outgoing section's last beat, bound to a lyric late in that
    beat, must be seen until a quarter beat after the lyric, past the boundary: a BEAT
    crossfade split three quarters starts on the boundary. At 120 BPM a quarter beat is
    left and it plays; at 240 BPM less than four frames are, and it plays on no head.
    Repair says the same."""
    beat_grid = grid(bpm, bars=4)
    at = beat_grid.beat_time_ms(2, 4)
    assert at is not None
    late = int(at + 0.9 * 60_000 / bpm)
    sections = [
        m.plan_section(
            "s1",
            1,
            2,
            "mirror_wings",
            events=[event(2, 4, "color", color="blue", moment_cue_id="c", cue_ms=late)],
        ),
        m.plan_section(
            "s2",
            3,
            4,
            "mirror_wings",
            color="blue",
            transitions=[transition("ENTRY", "crossfade", "BEAT", split="THREE_QUARTERS")],
        ),
    ]
    repaired = repair_rig_intent(
        ChoreographyPlan(sections=sections, overall_strategy=""),
        rig_offer(rig(), beat_grid),
        {},
        beat_grid,
    )
    said = [r.reason for r in repaired.repairs if r.item.startswith("entry transition")]
    pipeline = render(sections, beat_grid=beat_grid)
    (entry,) = transitions_of(pipeline)

    assert any(
        "the window yields: it starts after the part it leaves plays its color" in why
        for why in said
    )
    assert any("color at bar 2 beat 4" in why for why in entry["clamped"])
    assert entry["window_ms"][0] == entry["boundary_ms"]
    if plays:
        assert not any("does not play" in why for why in said)
        assert all("not_played" not in o for o in entry["heads"].values())
    else:
        assert any("it does not play" in why for why in said)
        assert all("not_played" in o for o in entry["heads"].values())


def test_repair_records_a_snap_on_the_first_entry_as_the_plain_cut() -> None:
    beat_grid = grid(120, bars=4)
    sections = [
        m.plan_section("s1", 1, 4, "mirror_wings", transitions=[transition("ENTRY", "snap")])
    ]
    repaired = repair_rig_intent(
        ChoreographyPlan(sections=sections, overall_strategy=""),
        rig_offer(rig(), beat_grid),
        {},
        beat_grid,
    )
    (entry,) = transitions_of(render(sections, beat_grid=beat_grid))

    assert any("plays as the plain cut" in r.reason for r in repaired.repairs)
    assert all(o["plays"].startswith("nothing: the plain cut") for o in entry["heads"].values())


def test_the_trace_reads_as_a_line() -> None:
    pipeline = render(pair(transition("ENTRY", "fade_via_black")))
    (line,) = describe_transitions(transitions_of(pipeline))

    assert line.startswith("transition ENTRY fade_via_black over BAR (curve linear, split QUARTER)")
    assert "fades to dark at the boundary, changes in the dark, fades up" in line
    assert math.isfinite(len(line))


def test_a_multi_part_sections_entry_plays_in_its_first_part_and_exit_in_its_last() -> None:
    """A section of two parts (`mirror_wings` bars 5-6, `finite_snap_hold` bars 7-8)
    between two others: its ENTRY's window ends inside its first part, its EXIT's starts
    inside its last; the parts' own boundary has no transition."""
    middle = m.plan_section(
        "s2",
        5,
        8,
        "mirror_wings",
        transitions=[transition("ENTRY", "crossfade"), transition("EXIT", "fade_via_black")],
    )
    middle = middle.model_copy(
        update={
            "parts": [
                middle.parts[0],
                middle.parts[0].model_copy(
                    update={"start_bar": 7, "template_id": "finite_snap_hold"}
                ),
            ]
        }
    )
    beat_grid = grid(120, bars=12)
    sections = [
        m.plan_section("s1", 1, 4, "finite_snap_hold"),
        middle,
        m.plan_section("s3", 9, 12, "mirror_wings"),
    ]
    pipeline = render(sections, beat_grid=beat_grid)
    bars = beat_grid.bar_boundaries
    by_part = {look["section_id"]: look.get("transitions", []) for look in looks(pipeline).values()}

    (entry,) = by_part["s2|A"]
    (exit_,) = by_part["s2|B"]
    assert entry["edge"] == "ENTRY" and entry["window_ms"][1] <= frame_of(bars[6]) * FRAME
    assert exit_["edge"] == "EXIT" and exit_["window_ms"][0] >= frame_of(bars[6]) * FRAME
    assert exit_["boundary_ms"] == frame_of(bars[8]) * FRAME


def test_the_last_exit_of_a_section_cut_at_the_song_end_ends_with_its_cues() -> None:
    """The plan's last section runs past the detected grid: its cues end where the grid
    does, and its EXIT's window ends there."""
    beat_grid = grid(120, bars=8)
    sections = [
        m.plan_section("s1", 1, 4, "finite_snap_hold"),
        m.plan_section("s2", 5, 10, "mirror_wings", transitions=[transition("EXIT", "blackout")]),
    ]
    pipeline = render(sections, beat_grid=beat_grid)
    (entry,) = transitions_of(pipeline)
    frames = Frames(pipeline)
    lit_until = max(i for h in HEADS for i, dark in enumerate(frames.dark(h)) if not dark)

    assert entry["window_ms"][1] == entry["boundary_ms"] <= frame_of(beat_grid.duration_ms) * FRAME
    assert lit_until < entry["window_ms"][0] // FRAME


@pytest.mark.parametrize("strategy", ["fade_via_black", "sequence"])
def test_a_wheel_strategy_shapes_the_edges_of_its_dark_cut(strategy: str) -> None:
    """A crossfade across red into blue with the colour's own strategy: `fade_via_black`
    fades the light into the cut and up out of it; `sequence` closes the shutter before the
    cut with the dimmer still up. Either way the wheel turns dark."""
    pipeline = render(
        [
            m.plan_section("s1", 1, 4, "mirror_wings", color="red"),
            m.plan_section(
                "s2",
                5,
                8,
                "mirror_wings",
                color="blue",
                transitions=[transition("ENTRY", "crossfade", channels=[("color", strategy)])],
            ),
        ],
        fixture_group=rig(close=20, settle=150),
    )
    frames = Frames(pipeline)
    (entry,) = transitions_of(pipeline)
    window = window_frames(entry)
    assert_wheels_turn_dark(frames)

    for head in HEADS:
        start, _ = (t // FRAME for t in entry["heads"][head]["dark_ms"])
        dimmer, shutter = frames.dimmer(head), frames.state(head, "shutter")
        if strategy == "fade_via_black":
            down = [dimmer[i] for i in range(window.start, start)]
            assert down == sorted(down, reverse=True) and down[-1] <= 25
            assert all(state != "closed" for state in shutter[window.start : start])
        else:
            assert shutter[start - 1] == "closed" and dimmer[start - 1] > 0


REALISTIC_TRANSITIONS = {
    "intro": [transition("ENTRY", "crossfade", "TWO_BARS", curve="ease_in_sine", split="HALF")],
    "verse_1": [transition("ENTRY", "morph", "BAR", curve="ease_in_out_sine", split="HALF")],
    "verse_2": [transition("ENTRY", "crossfade", "HALF_BAR", curve="ease_out_quad")],
    "chorus_1": [transition("ENTRY", "snap", "BEAT", split="HALF")],
    "break": [transition("ENTRY", "snap", "BEAT", split="HALF")],
    "chorus_2": [
        transition("ENTRY", "crossfade", "BEAT", curve="ease_out_quad"),
        transition("EXIT", "blackout", "BEAT", split="HALF"),
    ],
}
"""The transitions the owner's test song's plan chose (shape only), on the synthetic
`REALISTIC` fixture."""


def test_the_realistic_plan_plays_its_transitions_honestly() -> None:
    """The test song's shape at 78.3 BPM with two pickup beats, on an owner-like rig, with
    the transitions its plan chose: every transition is traced on every head, every wheel
    byte change is dark, a crossfade across a colour change cuts dark at its split point,
    the snaps into the cascades play nothing (the cascades enter dark), and the song ends
    in the blackout."""
    from tests.unit.sequencer.moving_heads.test_events_render import (
        owner_like_rig,
        realistic_plan,
    )

    beat_grid = m.pickup_grid(60_000 / 78.3, 62, pickup=2)
    plan = realistic_plan(beat_grid)
    plan = plan.model_copy(
        update={
            "sections": [
                s.model_copy(
                    update={
                        "transitions": [
                            PlanTransition.model_validate(t)
                            for t in REALISTIC_TRANSITIONS[s.section_id]
                        ]
                    }
                )
                for s in plan.sections
            ]
        }
    )
    pipeline = render(plan.sections, beat_grid=beat_grid, fixture_group=owner_like_rig())
    frames = Frames(pipeline)
    by_section = {
        look["section_id"]: look.get("transitions", []) for look in looks(pipeline).values()
    }

    assert_wheels_turn_dark(frames)
    traced = [t for ts in by_section.values() for t in ts]
    assert len(traced) == 7
    assert all(set(t["heads"]) == set(HEADS) for t in traced)
    (verse_1,) = by_section["verse_1"]
    assert all("color turns" in o["plays"] for o in verse_1["heads"].values())
    for snap in (by_section["chorus_1"][0], by_section["break"][0]):
        assert all(o["plays"].startswith("nothing: the plain cut") for o in snap["heads"].values())
    closing = by_section["chorus_2|B"][-1]
    assert closing["edge"] == "EXIT" and closing["mode"] == "blackout"
    end = closing["window_ms"][1] // FRAME
    assert all(frames.dark(h)[end - 1] for h in HEADS)
    # The NEUTRAL colour on 61.4, bound to its lyric 40 ms after the beat, is seen for half
    # a beat after its reveal (later than a quarter beat after the lyric) before the
    # blackout begins: the window starts there, on the frame grid.
    colour = next(e for e in looks(pipeline)["chorus_2|B"]["events"] if e["action"] == "color")
    beat = 60_000 / 78.3
    for head in HEADS:
        reveal = colour["heads"][head]["reveal_ms"]
        seen = max(reveal + beat / 2, colour["cue_ms"] + beat / 4)
        assert closing["window_ms"][0] == math.ceil(seen / FRAME) * FRAME
        states, dark = frames.state(head, "color"), frames.dark(head)
        shown = range(reveal // FRAME, closing["window_ms"][0] // FRAME)
        assert all(not dark[i] and states[i] == "white" for i in shown)
        assert all(dark[i] for i in window_frames(closing))
    # The hit on 53.1 is the crossfade's first frame: the dark cut its colour change needs
    # would cover it, so no head plays the transition and the hit plays on every head.
    (entry,) = by_section["chorus_2|A"]
    hit = next(e for e in looks(pipeline)["chorus_2|A"]["events"] if e["action"] == "hit")
    for head in HEADS:
        assert "would cover the hit at bar 53 beat 1" in entry["heads"][head]["not_played"]
        assert hit["heads"][head]["played_ms"] == hit["frame_ms"]
        assert frames.dimmer(head)[hit["frame_ms"] // FRAME] == 255
    assert pipeline.render_record is not None
    warnings = [d["message"] for d in pipeline.render_record["diagnostics"]]
    assert any("transition ENTRY snap played nothing on MH1" in w for w in warnings)
    assert any("transition ENTRY crossfade not played on MH1" in w for w in warnings)


# --- fix round: events inside windows, the played rule, edges --------------------------


def test_a_colour_event_inside_a_window_off_the_frame_grid_renders_on_the_grid() -> None:
    """At 120 BPM a colour event on 5.2 inside a crossfade's window clamps it half a beat
    before its beat, off the 20 ms grid: the clamp lands on the grid, the change turns
    dark and is shown."""
    pipeline = render(
        pair(
            transition("ENTRY", "crossfade", split="HALF"),
            first="mirror_wings",
            events=[event(5, 2, "color", color="blue")],
        )
    )
    frames = Frames(pipeline)
    (entry,) = transitions_of(pipeline)

    assert all(ms % FRAME == 0 for ms in entry["window_ms"])
    assert any("color at bar 5 beat 2" in why for why in entry["clamped"])
    assert set(entry["heads"]) == set(HEADS)
    assert_wheels_turn_dark(frames)
    assert all("blue" in frames.state(h, "color") for h in HEADS)


@pytest.mark.parametrize(
    ("first", "second"),
    [("fly_out_cascade", "fly_in_cascade"), ("mirror_wings", "fly_in_cascade")],
)
def test_blackout_is_dark_over_its_whole_window_where_a_head_has_no_cue(
    first: str, second: str
) -> None:
    """The cascades leave heads without a cue around the boundary: a blackout is still dark
    over its whole window on every head, as a show's rest is, and counts as played."""
    pipeline = render(pair(transition("ENTRY", "blackout", "TWO_BARS"), first=first, second=second))
    frames = Frames(pipeline)
    (entry,) = transitions_of(pipeline)

    for head in HEADS:
        assert all(frames.dark(head)[i] for i in window_frames(entry))
        assert entry["heads"][head]["plays"] == "dark over the whole window"
        assert "curve_played" not in entry["heads"][head]


def test_a_transition_that_changes_no_frame_is_traced_as_playing_nothing() -> None:
    """A snap into a template its heads enter dark changes nothing on them: the trace says
    `nothing` and why, and the section's warning counts it."""
    pipeline = render(pair(transition("ENTRY", "snap"), second="fly_in_cascade"))
    plain = render(pair(second="fly_in_cascade"))
    (entry,) = transitions_of(pipeline)
    nothing = [h for h, o in entry["heads"].items() if o["plays"].startswith("nothing: ")]

    assert nothing
    for head in nothing:
        assert Frames(pipeline).raw(head) == Frames(plain).raw(head)
    assert pipeline.render_record is not None
    assert any(
        "transition ENTRY snap played nothing" in d["message"]
        for d in pipeline.render_record["diagnostics"]
    )


def test_snap_turns_the_wheels_held_at_its_dark_cut() -> None:
    """`masked_wheel_flick` red into `mirror_wings` blue under a BAR snap: the flick changes
    the outgoing colour inside the snap's window, so the snap turns each wheel from the
    colour the head holds at its dark cut, never lit, and plays on every head."""
    sections = [
        m.plan_section("s1", 1, 4, "masked_wheel_flick", color="red"),
        m.plan_section(
            "s2", 5, 8, "mirror_wings", color="blue", transitions=[transition("ENTRY", "snap")]
        ),
    ]
    pipeline = render(sections)
    frames = Frames(pipeline)
    (entry,) = transitions_of(pipeline)

    assert_wheels_turn_dark(frames)
    for head, outcome in entry["heads"].items():
        assert "not_played" not in outcome, head
        before, after = outcome["wheels_turn"]["color"]
        cut = outcome["dark_ms"][0] // FRAME
        assert frames.state(head, "color")[cut - 1] == before
        assert after == "blue"


def test_a_crossfade_clamped_to_one_side_eases_its_level_without_a_jump() -> None:
    """A strobe on 4.4 starts the crossfade's window at the boundary (its split point on
    the window's edge): the level eases from the outgoing look to the incoming one, with no
    lit-to-lit jump at either edge."""
    sections = pair(
        transition("ENTRY", "crossfade", "TWO_BARS", split="HALF"),
        first="mirror_wings",
        second="target_orbit",
    )
    sections[0] = sections[0].model_copy(
        update={"events": [PlanEvent.model_validate(event(4, 4, "strobe_fast"))]}
    )
    pipeline = render(sections, fixture_group=rig(strobes=True))
    frames = Frames(pipeline)
    (entry,) = transitions_of(pipeline)

    assert entry["window_ms"][0] == entry["boundary_ms"]
    played = [h for h, o in entry["heads"].items() if "clamped to one side" in o.get("plays", "")]
    assert played
    for head in played:
        a, b = entry["heads"][head].get("window_ms", entry["window_ms"])
        level, dark = frames.dimmer(head), frames.dark(head)
        for i in (a // FRAME, b // FRAME):
            if not dark[i] and not dark[i - 1]:
                assert abs(level[i] - level[i - 1]) <= 100


FUZZ_TEMPLATES = (
    "fly_out_cascade",
    "fly_in_cascade",
    "target_orbit",
    "mirror_wings",
    "finite_snap_hold",
    "masked_wheel_flick",
)
FUZZ_ACTIONS = ("closed", "strobe_fast", "pulse", "hit", "color", "gobo", "hit", "color")


def _fuzz_grid(rnd: random.Random) -> BeatGrid:
    choice = rnd.randrange(4)
    if choice == 0:
        return grid(120, 14)
    if choice == 1:
        return m.pickup_grid(60_000 / 78.3, 14, pickup=2)
    if choice == 2:
        return m.pickup_grid(60_000 / 129, 14, pickup=1, beats_per_bar=3)
    return m.bars_grid(*(60_000 / rnd.uniform(96, 150) for _ in range(14 * 4)))


def _fuzz_plan(rnd: random.Random, beat_grid: BeatGrid) -> list[PlanSection]:
    """Random valid sections over the grid: templates, parts, intensity, both edges'
    transitions (any mode, length, curve, split), and events near the boundaries."""
    per_bar, bars = beat_grid.beats_per_bar, len(beat_grid.bar_boundaries) - 1
    sections: list[PlanSection] = []
    start = 1
    while start <= bars:
        end = min(bars, start + rnd.choice((1, 2, 3)))
        transitions = [
            transition(
                edge,
                rnd.choice(MODES),
                rnd.choice(("BEAT", "HALF_BAR", "BAR", "TWO_BARS")),
                curve=rnd.choice(("linear", "ease_in_out_sine", "s_curve", "ease_out_quad")),
                split=rnd.choice(("QUARTER", "HALF", "THREE_QUARTERS")),
            )
            for edge in ("ENTRY", "EXIT")
            if rnd.random() < 0.6
        ]
        events = []
        for _ in range(rnd.choice((0, 1, 2, 3))):
            action = rnd.choice(FUZZ_ACTIONS)
            bar = rnd.choice((start, end))
            beat = (
                rnd.choice((1, 2, per_bar)) if bar == start else rnd.choice((per_bar - 1, per_bar))
            )
            fields: dict[str, Any] = {}
            if action == "color":
                fields["color"] = rnd.choice(("red", "blue", "white"))
            if action == "gobo":
                fields["gobo"] = rnd.choice(("dots", "stars"))
            events.append(event(bar, max(1, beat), action, **fields))
        kwargs: dict[str, Any] = {
            "intensity": rnd.choice((None, "SLOW", "SMOOTH", "FAST", "DRAMATIC", "INTENSE")),
            "color": rnd.choice((None, "red", "blue")),
        }
        template = rnd.choice(FUZZ_TEMPLATES)
        try:
            section = m.plan_section(
                f"s{len(sections) + 1}", start, end, template,
                transitions=transitions, events=events, **kwargs,
            )  # fmt: skip
        except ValueError:
            section = m.plan_section(
                f"s{len(sections) + 1}", start, end, template, transitions=transitions, **kwargs
            )
        if end > start and rnd.random() < 0.3:
            section = section.model_copy(
                update={
                    "parts": [
                        section.parts[0],
                        section.parts[0].model_copy(
                            update={"start_bar": end, "template_id": rnd.choice(FUZZ_TEMPLATES)}
                        ),
                    ]
                }
            )
        sections.append(section)
        start = end + 1
    return sections


@pytest.mark.parametrize("seed", range(12))
def test_smoke_random_plans_with_events_inside_transition_windows(seed: int) -> None:
    """Smoke test, not a regression pin: seeded random plans (events near the boundaries,
    every mode, intensity, parts and a show's rest) render without raising, no wheel
    changes lit, every transition is traced on every head with what it plays or why not,
    every window lies on the frame grid, and no transition loses a hit. The targeted
    tests above pin each behaviour; these only sweep for surprises."""
    rnd = random.Random(seed)
    beat_grid = _fuzz_grid(rnd)
    sections = _fuzz_plan(rnd, beat_grid)
    rest: tuple[tuple[int, int], ...] = ()
    if rnd.random() < 0.3:
        at = round(beat_grid.bar_boundaries[rnd.randrange(1, 5)])
        rest = ((at - 300, at + 400),)
    pipeline = render(
        sections,
        beat_grid=beat_grid,
        fixture_group=rig(close=20, settle=150, strobes=True),
        dark_spans=rest,
    )

    assert_wheels_turn_dark(Frames(pipeline))
    for entry in transitions_of(pipeline):
        assert all(ms % FRAME == 0 for ms in entry["window_ms"])
        assert set(entry["heads"]) == set(HEADS)
        for outcome in entry["heads"].values():
            assert ("plays" in outcome) != ("not_played" in outcome)
    # No transition loses a hit: one that plays on a head without them plays with them.
    free = pipeline.transition_free
    assert free is not None or not any(s.transitions for s in sections)
    if free is not None:
        for key, by_head in free.hit_frames.items():
            assert set(by_head) <= set(pipeline.hit_frames.get(key, {})), key


# --- fix round 2: every visible event seen, no hit lost, dark modes yield, short sides ---


def test_an_open_before_a_blackout_is_seen_for_half_a_beat() -> None:
    """A `closed` on 4.1 and an `open` on bar 4's last beat, then an ENTRY blackout split
    half a bar: the light the `open` brings back stays on for half a beat before the
    blackout begins (it was lit for one frame)."""
    g = grid(120)
    sections = pair(transition("ENTRY", "blackout", split="HALF"), first="mirror_wings")
    sections[0] = sections[0].model_copy(
        update={
            "events": [
                PlanEvent.model_validate(event(4, 1, "closed")),
                PlanEvent.model_validate(event(4, 4, "open")),
            ]
        }
    )
    pipeline = render(sections, beat_grid=g)
    frames = Frames(pipeline)
    (entry,) = transitions_of(pipeline)
    opened = beat_frame(g, 4, 4)

    assert entry["window_ms"][0] >= opened * FRAME + 250
    assert any("open at bar 4 beat 4" in why for why in entry["clamped"])
    for head in HEADS:
        dark = frames.dark(head)
        assert not any(dark[i] for i in range(opened, entry["window_ms"][0] // FRAME))
        assert all(dark[i] for i in window_frames(entry))


def test_no_head_loses_a_hit_to_a_transition_and_its_reason_is_true() -> None:
    """170 BPM, `target_orbit` into `zoom_wave` with a hit on 5.2 and an ENTRY
    fade_via_black: without the transition every head is dark on 5.2 and the hit moves to
    5.3 on all four. With it, two heads fade up lit on 5.2: the hit still plays on every
    head that plays it without the transition (moved where all of them show it), and no
    head gives up the transition for a hit its darkness does not cover."""
    g = grid(170)
    sections = [
        m.plan_section("s1", 1, 4, "target_orbit"),
        m.plan_section(
            "s2",
            5,
            8,
            "zoom_wave",
            events=[event(5, 2, "hit")],
            transitions=[transition("ENTRY", "fade_via_black", split="HALF")],
        ),
    ]
    payload = m.zoom_rig(HEADS).model_dump(mode="json")
    for fixture in payload["fixtures"]:
        profile = fixture["config"]["physical_profile"]
        profile["visibility"].update(close_latency_ms=20, open_latency_ms=20)
        for wheel in ("color", "gobo"):
            for state in profile["discrete"].get(wheel, {}).get("states", {}).values():
                state["settle_ms"] = 150
    pipeline = render(
        sections,
        beat_grid=g,
        fixture_group=FixtureGroup.model_validate(payload),
        job_config=m.zoom_job(HEADS),
    )
    free = pipeline.transition_free
    assert free is not None
    (entry,) = transitions_of(pipeline)
    hit = next(e for e in looks(pipeline)["s2"]["events"] if e["action"] == "hit")

    assert set(free.hit_frames[("s2", 0)]) == set(HEADS)
    assert set(pipeline.hit_frames[("s2", 0)]) == set(HEADS)
    for head in HEADS:
        assert "moved" in hit["heads"][head]
        outcome = entry["heads"][head]
        if "not_played" in outcome and "would cover the hit" in outcome["not_played"]:
            a, b = (int(x) for x in outcome["not_played"].split("(")[1].split(" ms")[0].split("-"))
            assert a <= free.hit_frames[("s2", 0)][head] < b


def test_a_dark_mode_ends_before_an_incoming_hit_instead_of_being_dropped() -> None:
    """An ENTRY blackout over a BAR (split half) with a hit on 5.2: the window ends before
    the hit (it was dropped on every head), and the hit plays."""
    g = grid(120)
    pipeline = render(
        pair(transition("ENTRY", "blackout", split="HALF"), events=[event(5, 2, "hit")]),
        beat_grid=g,
    )
    frames = Frames(pipeline)
    (entry,) = transitions_of(pipeline)
    hit = next(e for e in looks(pipeline)["s2"]["events"] if e["action"] == "hit")
    at = beat_frame(g, 5, 2)

    assert entry["window_ms"][1] <= at * FRAME
    assert any("hit at bar 5 beat 2" in why for why in entry["clamped"])
    for head in HEADS:
        assert "not_played" not in entry["heads"][head]
        assert all(frames.dark(head)[i] for i in window_frames(entry))
        assert "played_ms" in hit["heads"][head]


def test_a_fade_side_too_short_to_fade_cuts_and_says_so() -> None:
    """170 BPM, a hit on 4.4 bound to a lyric 0.6 beat after it, then an ENTRY
    fade_via_black over a BAR split half: the window starts two frames before the boundary,
    too short a fade-out; the light cuts to dark at the boundary, never a two-frame fade."""
    g = grid(170)
    at = g.beat_time_ms(4, 4)
    assert at is not None
    late = int(at + 0.6 * 60_000 / 170)
    sections = pair(transition("ENTRY", "fade_via_black", split="HALF"), first="mirror_wings")
    sections[0] = sections[0].model_copy(
        update={
            "events": [
                PlanEvent.model_validate(
                    event(4, 4, "hit", moment_cue_id="c", cue_ms=late, cue_emphasis="MED")
                )
            ],
            "moment_cues": ["c"],
        }
    )
    pipeline = render(sections, beat_grid=g)
    frames = Frames(pipeline)
    (entry,) = transitions_of(pipeline)
    boundary = entry["boundary_ms"] // FRAME

    assert 0 < entry["boundary_ms"] - entry["window_ms"][0] < 4 * FRAME
    for head, outcome in entry["heads"].items():
        if "not_played" in outcome:
            continue
        assert outcome["plays"].startswith("cuts to dark at the boundary")
        level, dark = frames.dimmer(head), frames.dark(head)
        before = range(entry["window_ms"][0] // FRAME, boundary)
        assert len({level[i] for i in before if not dark[i]}) <= 1
        assert dark[boundary]


def test_the_second_render_logs_nothing_and_leaves_the_logger_alone(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """A render with transitions renders again without them; that render's warnings are
    held (never logged twice) and the module logger is never disabled."""
    import logging

    from twinklr.core.sequencer.moving_heads import pipeline as module

    with caplog.at_level(logging.WARNING):
        render(pair())
    alone = [r.getMessage() for r in caplog.records]
    caplog.clear()
    with caplog.at_level(logging.WARNING):
        render(pair(transition("ENTRY", "crossfade")))
    assert [r.getMessage() for r in caplog.records] == alone
    assert not module.logger.disabled


AGREEMENT = [
    (bpm, action, cue, mode)
    for bpm in (120, 170)
    for action in ("hit", "color", "open")
    for cue in (None, 0.9)
    for mode in MODES
    if not (action == "open" and cue is not None)
]


@pytest.mark.parametrize(("bpm", "action", "cue", "mode"), AGREEMENT)
def test_repair_and_render_agree_on_what_a_transition_yields_to(
    bpm: int, action: str, cue: float | None, mode: str
) -> None:
    """An event on the outgoing section's last beat (a hit, a colour change or an `open`
    after a `closed`, bound or not to a lyric late in the beat) and a BEAT transition of
    every mode: repair and render read the same placement (`window_for` over
    `events.yield_spans`), so they agree on whether the window yields to the event and on
    whether too little is left to play. Where the render then plays on no head for a
    head's own darkness need, repair has said that it may."""
    g = grid(bpm, bars=4)
    at = g.beat_time_ms(2, 4)
    assert at is not None
    fields: dict[str, Any] = {"color": "blue"} if action == "color" else {}
    if cue is not None:
        fields.update(moment_cue_id="c", cue_ms=int(at + cue * 60_000 / bpm))
    events = [event(2, 4, action, **fields)]
    if action == "open":
        events.insert(0, event(2, 1, "closed"))
    sections = [
        m.plan_section("s1", 1, 2, "mirror_wings", events=events),
        m.plan_section(
            "s2", 3, 4, "finite_snap_hold", transitions=[transition("ENTRY", mode, "BEAT")]
        ),
    ]
    repaired = repair_rig_intent(
        ChoreographyPlan(sections=sections, overall_strategy=""),
        rig_offer(rig(), g),
        {},
        g,
    )
    said = " ".join(r.reason for r in repaired.repairs if r.item.startswith("entry transition"))
    (entry,) = transitions_of(render(repaired.sections, beat_grid=g))

    clamped = any(f"{action} at bar 2 beat 4" in why for why in entry.get("clamped", []))
    assert clamped == (f"plays its {action} at bar 2 beat 4" in said)
    assert (entry.get("not_played") is not None) == ("it does not play" in said)
    heads_np = [o for o in entry["heads"].values() if "not_played" in o]
    if heads_np and entry.get("not_played") is None:
        assert "plays no transition" in said  # warned covers every head that skips
    if mode in ("blackout", "fade_via_black"):
        assert "plays no transition" not in said  # darkness is their whole look


# --- fix round 3: repair's song end, its darkness caveat, hits still lost ----------------


def _review_zoom_rig() -> FixtureGroup:
    """The zoom rig with the review's timings: close and open latency 20 ms, every wheel
    state settling in 150 ms, colours and gobos tagged by name."""
    payload = m.zoom_rig(HEADS).model_dump(mode="json")
    for fixture in payload["fixtures"]:
        profile = fixture["config"]["physical_profile"]
        profile["visibility"].update(close_latency_ms=20, open_latency_ms=20)
        for name, state in profile["discrete"]["color"]["states"].items():
            state["hex"] = name
        for name, state in profile["discrete"]["gobo"]["states"].items():
            state["pattern"] = {"star": "stars"}.get(name, name)
        for wheel in ("color", "gobo"):
            for state in profile["discrete"][wheel]["states"].values():
                state["settle_ms"] = 150
    return FixtureGroup.model_validate(payload)


def test_repair_places_the_songs_last_exit_where_the_render_does() -> None:
    """78.3 BPM with two pickup beats, a colour change on 8.3 and an EXIT blackout over a
    BEAT on the song's last section: repair's window is the render's (the closing boundary
    on the covered beat grid, not the song's last frame past it), so it does not size the
    blackout from the whole last part."""
    from twinklr.core.agents.sequencer.moving_heads.rig_repair import played_window

    g = m.pickup_grid(60_000 / 78.3, 8, pickup=2)
    sections = [
        m.plan_section("s1", 1, 4, "mirror_wings"),
        m.plan_section(
            "s2",
            5,
            8,
            "mirror_wings",
            events=[event(8, 3, "color", color="blue")],
            transitions=[transition("EXIT", "blackout", "BEAT", split="HALF")],
        ),
    ]
    window = played_window(sections[1].exit, sections[1], None, g)  # type: ignore[arg-type]
    repaired = repair_rig_intent(
        ChoreographyPlan(sections=sections, overall_strategy=""), rig_offer(rig(), g), {}, g
    )
    said = " ".join(r.reason for r in repaired.repairs if r.item.startswith("exit transition"))
    (entry,) = transitions_of(render(sections, beat_grid=g))

    assert window is not None
    assert [window.start_ms, window.end_ms] == entry["window_ms"]
    assert window.boundary_ms == entry["boundary_ms"]
    assert "plays no transition" not in said and "it does not play" not in said


def test_hits_a_transition_still_loses_after_the_last_pass_are_traced_and_warned(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A sweep into `mirror_wings` with a hit on 4.1 and two gobo changes loses the hit on
    every head in the first pass and needs a second. With one pass allowed, the loss is
    traced (`hits_lost_to_transitions`) and warned; with the default, nothing is lost."""
    from twinklr.core.sequencer.moving_heads import pipeline as module

    sections = [
        m.plan_section("s1", 2, 3, "zoom_wave", events=[event(3, 4, "closed")]),
        m.plan_section(
            "s2",
            4,
            4,
            "mirror_wings",
            events=[
                event(4, 2, "gobo", gobo="stars"),
                event(4, 3, "gobo", gobo="dots"),
                event(4, 1, "hit"),
            ],
            transitions=[transition("ENTRY", "sweep", "HALF_BAR", split="THIRD")],
        ),
    ]
    fields = {"fixture_group": _review_zoom_rig(), "job_config": m.zoom_job(HEADS)}
    whole = render(sections, beat_grid=grid(120), **fields)
    assert whole.render_record is not None
    assert "hits_lost_to_transitions" not in whole.render_record
    free = whole.transition_free
    assert free is not None
    assert set(free.hit_frames[("s2", 2)]) <= set(whole.hit_frames.get(("s2", 2), {}))

    monkeypatch.setattr(module, "TRANSITION_PASSES", 1)
    once = render(sections, beat_grid=grid(120), **fields)
    assert once.render_record is not None
    lost = once.render_record["hits_lost_to_transitions"]
    assert {entry["fixture_id"] for entry in lost} == set(HEADS)
    assert all("hit at bar 4 beat 1" in entry["reason"] for entry in lost)
    assert any(
        "still lose a hit to a transition" in d["message"]
        for d in once.render_record["diagnostics"]
    )


def test_repair_says_where_a_lit_move_may_fall_back_to_a_dark_cut() -> None:
    """On 300-degree heads, across lit modes, lengths, tempos and template pairs with
    different poses, every head the render moves in a dark cut instead of lit (traced
    `fallback`) is one repair said may: the window is shorter than the slowest head's
    whole-range travel at the easing's steepest slope. Where repair says nothing, no head
    falls back."""
    payload = rig().model_dump(mode="json")
    for fixture in payload["fixtures"]:
        for axis in ("pan", "tilt"):
            fixture["config"]["physical_profile"]["axes"][axis]["travel_speed_per_s"] = 300.0
    slow = FixtureGroup.model_validate(payload)
    fell_back = 0
    for bpm in (120, 170):
        g = grid(bpm, bars=4)
        for mode in ("crossfade", "morph", "sweep"):
            for length in ("BEAT", "HALF_BAR", "BAR"):
                for first, second in (
                    ("finite_snap_hold", "mirror_wings"),
                    ("target_orbit", "fly_in_cascade"),
                ):
                    sections = [
                        m.plan_section("s1", 1, 2, first),
                        m.plan_section(
                            "s2", 3, 4, second, transitions=[transition("ENTRY", mode, length)]
                        ),
                    ]
                    repaired = repair_rig_intent(
                        ChoreographyPlan(sections=sections, overall_strategy=""),
                        rig_offer(slow, g),
                        {},
                        g,
                    )
                    said = " ".join(
                        r.reason for r in repaired.repairs if r.item.startswith("entry transition")
                    )
                    (entry,) = transitions_of(
                        render(repaired.sections, beat_grid=g, fixture_group=slow)
                    )
                    if any("fallback" in o for o in entry["heads"].values()):
                        fell_back += 1
                        assert "its lit move has" in said, (bpm, mode, length, first)
    assert fell_back  # the sweep reaches the case it guards


def test_the_offer_bounds_a_dark_change_over_every_axis_the_heads_move() -> None:
    """The darkness bound repair warns by is the render's own `worst_case_entry_ms` over the
    whole pan, tilt and zoom range: slowing the zoom alone raises it."""
    g = grid(120, bars=4)
    fast = rig_offer(m.zoom_rig(HEADS), g).dark_change_ms
    payload = m.zoom_rig(HEADS).model_dump(mode="json")
    for fixture in payload["fixtures"]:
        fixture["config"]["physical_profile"]["axes"]["zoom"]["travel_speed_per_s"] = 5.0
    slow = rig_offer(FixtureGroup.model_validate(payload), g).dark_change_ms

    assert fast is not None and slow is not None and slow > fast
