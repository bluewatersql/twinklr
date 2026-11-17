"""Section-id canonicalisation, repair and lyric-cue binding of a planner response."""

from typing import Any

import pytest

from tests.support.moving_heads import plan_section
from twinklr.core.agents.audio.lyrics.models import LyricContextModel, MomentCue
from twinklr.core.agents.audio.profile.models import SongSectionRef
from twinklr.core.agents.sequencer.moving_heads.models import (
    ChoreographyPlan,
    PlanRepair,
    RepairAction,
)
from twinklr.core.agents.sequencer.moving_heads.moment_cues import bind_lyric_moment_cues
from twinklr.core.sequencer.timing.beat_grid import BeatGrid


def _section(
    section_id: str = "chorus_1",
    *,
    name: str = "chorus",
    start_ms: int = 0,
    end_ms: int = 4_000,
) -> SongSectionRef:
    return SongSectionRef(section_id=section_id, name=name, start_ms=start_ms, end_ms=end_ms)


def _cue(
    cue_id: str = "chorus-home", timestamp_ms: int = 1_500, section_id: str = "chorus_1"
) -> MomentCue:
    return MomentCue(
        cue_id=cue_id,
        timestamp_ms=timestamp_ms,
        section_id=section_id,
        emphasis="HIGH",
        text="light the way home",
        visual_hint="Open a white fan from center on home.",
    )


def _lyrics(*cues: MomentCue) -> LyricContextModel:
    return LyricContextModel(
        has_lyrics=True, vocal_coverage_pct=0.25, moment_cues=list(cues) or [_cue()]
    )


def _event(
    bar: int, beat: int, action: str, cue_id: str | None = None, **fields: Any
) -> dict[str, Any]:
    return {
        "bar": bar,
        "beat": beat,
        "moment_cue_id": cue_id,
        "action": action,
        "color": None,
        "gobo": None,
        **fields,
    }


def _plan(
    *,
    section_id: str = "chorus_1",
    start_bar: int = 1,
    end_bar: int = 2,
    moment_cues: tuple[str, ...] = ("chorus-home",),
    events: list[dict[str, Any]] | None = None,
) -> ChoreographyPlan:
    if events is None:
        events = [
            _event(start_bar, 1, action, "chorus-home")
            for action in ("strobe_fast", "hit", "closed")
        ] + [
            _event(start_bar, 1, "gobo", "chorus-home", gobo="stars"),
            _event(start_bar, 1, "color", "chorus-home", color="PALETTE_ACCENT"),
        ]
    return ChoreographyPlan(
        sections=[
            plan_section(
                section_id,
                start_bar,
                end_bar,
                "sweep_lr_fan_hold",
                moment_cues=list(moment_cues),
                events=events,
            )
        ],
        overall_strategy="Accentuate the lyric hook.",
    )


def _bind(
    plan: ChoreographyPlan,
    lyrics: LyricContextModel | None = None,
    *,
    sections: list[SongSectionRef] | None = None,
    grid: BeatGrid | None = None,
) -> ChoreographyPlan:
    return bind_lyric_moment_cues(
        plan,
        lyrics if lyrics is not None else _lyrics(),
        grid if grid is not None else BeatGrid.from_tempo(tempo_bpm=120, total_bars=2),
        sections or [_section()],
    )


def _repairs(plan: ChoreographyPlan) -> list[tuple[str, RepairAction]]:
    return [(repair.item, repair.action) for repair in plan.repairs]


# --- binding ------------------------------------------------------------------------------


def test_every_event_action_bound_to_a_cue_moves_to_its_snapped_beat() -> None:
    bound = _bind(_plan())

    assert {(e.action.value, e.bar, e.beat) for e in bound.sections[0].events} == {
        (action, 1, 4) for action in ("strobe_fast", "hit", "closed", "gobo", "color")
    }
    assert bound.repairs == []


@pytest.mark.parametrize(
    ("timestamp_ms", "expected"),
    [
        (0, (1, 1)),
        (1_250, (1, 3)),  # Equidistant ties resolve to the earlier beat.
        (3_500, (2, 4)),
    ],
)
def test_first_last_and_tied_cues_have_pinned_resolution(
    timestamp_ms: int, expected: tuple[int, int]
) -> None:
    bound = _bind(_plan(), _lyrics(_cue(timestamp_ms=timestamp_ms)))

    event = bound.sections[0].events[0]
    assert (event.bar, event.beat) == expected


def test_exact_section_boundary_belongs_to_following_unique_section_id() -> None:
    sections = [
        _section("chorus_1", start_ms=0, end_ms=2_000),
        _section("chorus_2", start_ms=2_000, end_ms=4_000),
    ]
    bound = _bind(
        _plan(
            section_id="chorus_2",
            start_bar=2,
            end_bar=2,
            moment_cues=("second-hit",),
            events=[_event(2, 1, "hit", "second-hit")],
        ),
        _lyrics(_cue("second-hit", 2_000, "chorus_2")),
        sections=sections,
    )

    event = bound.sections[0].events[0]
    assert bound.sections[0].section_id == "chorus_2"
    assert (event.bar, event.beat) == (2, 1)


# --- structural refusals ------------------------------------------------------------------


def test_repeated_section_name_is_ambiguous_but_unique_id_binds() -> None:
    sections = [
        _section("chorus_1", start_ms=0, end_ms=2_000),
        _section("chorus_2", start_ms=2_000, end_ms=4_000),
    ]
    with pytest.raises(ValueError, match=r"ambiguous.*chorus_1, chorus_2"):
        _bind(_plan(section_id="chorus", start_bar=2, end_bar=2), sections=sections)


def test_an_unknown_section_is_refused() -> None:
    with pytest.raises(ValueError, match="does not match any"):
        _bind(_plan(section_id="bridge_9"))


def test_a_display_name_naming_one_section_is_canonicalised() -> None:
    bound = _bind(_plan(section_id="chorus"))

    assert bound.sections[0].section_id == "chorus_1"


# --- repairs ------------------------------------------------------------------------------


def test_an_unknown_cue_is_dropped_and_its_events_keep_their_own_beat() -> None:
    bound = _bind(_plan(moment_cues=("missing",), events=[_event(2, 3, "hit", "missing")]))

    (section,) = bound.sections
    assert section.moment_cues == []
    assert [(e.bar, e.beat, e.moment_cue_id) for e in section.events] == [(2, 3, None)]
    assert _repairs(bound) == [
        ("moment cue 'missing'", RepairAction.DROPPED),
        ("hit event at bar 2 beat 3", RepairAction.ADJUSTED),
    ]
    assert "no lyric moment cue has id 'missing'" in bound.repairs[0].reason


def test_a_cue_of_another_section_is_dropped() -> None:
    sections = [
        _section("chorus_1", start_ms=0, end_ms=2_000),
        _section("chorus_2", start_ms=2_000, end_ms=4_000),
    ]
    bound = _bind(
        _plan(events=[]),
        _lyrics(_cue("chorus-home", 2_500, "chorus_2")),
        sections=sections,
    )

    assert bound.sections[0].moment_cues == []
    assert bound.repairs == [
        PlanRepair(
            section_id="chorus_1",
            item="moment cue 'chorus-home'",
            action=RepairAction.DROPPED,
            reason="lyric moment cue 'chorus-home' belongs to section 'chorus_2'",
        )
    ]


def test_a_cue_outside_its_own_section_is_dropped_before_any_snapping() -> None:
    sections = [
        _section("chorus_1", start_ms=0, end_ms=2_000),
        _section("chorus_2", start_ms=2_000, end_ms=4_000),
    ]
    bound = _bind(_plan(), _lyrics(_cue(timestamp_ms=4_500)), sections=sections)

    assert bound.sections[0].moment_cues == []
    assert all(event.moment_cue_id is None for event in bound.sections[0].events)
    assert "outside its section 'chorus_1'" in bound.repairs[0].reason


def test_an_event_on_an_unlisted_cue_of_the_section_adds_the_reference() -> None:
    bound = _bind(_plan(moment_cues=(), events=[_event(1, 1, "hit", "chorus-home")]))

    (section,) = bound.sections
    assert section.moment_cues == ["chorus-home"]
    assert (section.events[0].bar, section.events[0].beat) == (1, 4)
    assert _repairs(bound) == [("moment cue 'chorus-home'", RepairAction.ADJUSTED)]


def test_an_event_whose_cue_snaps_outside_the_section_is_dropped() -> None:
    bound = _bind(
        _plan(start_bar=1, end_bar=1, events=[_event(1, 1, "hit", "chorus-home")]),
        _lyrics(_cue(timestamp_ms=2_000)),
    )

    (section,) = bound.sections
    assert section.events == []
    assert _repairs(bound) == [
        ("hit event at bar 1 beat 1", RepairAction.DROPPED),
        ("moment cue 'chorus-home'", RepairAction.RECORDED),
    ]
    assert "snaps to bar 2" in bound.repairs[0].reason


def test_an_event_outside_the_section_or_its_bar_is_dropped() -> None:
    bound = _bind(
        _plan(
            moment_cues=(),
            events=[_event(3, 1, "closed"), _event(2, 5, "open"), _event(2, 4, "pulse")],
        )
    )

    assert [(e.bar, e.beat) for e in bound.sections[0].events] == [(2, 4)]
    assert _repairs(bound) == [
        ("closed event at bar 3 beat 1", RepairAction.DROPPED),
        ("open event at bar 2 beat 5", RepairAction.DROPPED),
    ]


def test_a_referenced_cue_no_event_lands_on_is_recorded_not_synthesised() -> None:
    bound = _bind(_plan(events=[]))

    assert bound.sections[0].moment_cues == ["chorus-home"]
    assert bound.sections[0].events == []
    assert _repairs(bound) == [("moment cue 'chorus-home'", RepairAction.RECORDED)]


def test_a_cue_bound_event_without_a_beat_grid_keeps_its_own_beat() -> None:
    plan = _plan(events=[_event(2, 2, "hit", "chorus-home")])
    empty = BeatGrid.from_tempo(tempo_bpm=120, total_bars=2).model_copy(
        update={"beat_boundaries": []}
    )

    bound = _bind(plan, grid=empty)

    assert [(e.bar, e.beat, e.moment_cue_id) for e in bound.sections[0].events] == [(2, 2, None)]
    assert "no beat grid" in bound.repairs[0].reason


def test_repairs_replace_those_of_an_earlier_normalisation() -> None:
    once = _bind(_plan(events=[]))

    assert _bind(once).repairs == once.repairs
