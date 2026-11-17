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
from twinklr.core.agents.sequencer.moving_heads.models import ChoreographyPlan, PlanSection
from twinklr.core.agents.sequencer.moving_heads.rig_repair import repair_rig_intent
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
        assert all(
            o["plays"].startswith("the head is dark from the boundary")
            for o in snap["heads"].values()
        )
    closing = by_section["chorus_2|B"][-1]
    assert closing["edge"] == "EXIT" and closing["mode"] == "blackout"
    end = closing["window_ms"][1] // FRAME
    assert all(frames.dark(h)[end - 1] for h in HEADS)
