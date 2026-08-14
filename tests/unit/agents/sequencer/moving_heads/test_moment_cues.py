"""Cross-model lyric MomentCue identity, integrity, and grid binding."""

import pytest

from twinklr.core.agents.audio.lyrics.models import LyricContextModel, MomentCue
from twinklr.core.agents.audio.profile.models import SongSectionRef
from twinklr.core.agents.sequencer.moving_heads.models import (
    ChoreographyPlan,
    GoboEvent,
    MomentCueReference,
    PlanSection,
    ShutterEvent,
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
    return SongSectionRef(
        section_id=section_id,
        name=name,
        start_ms=start_ms,
        end_ms=end_ms,
    )


def _lyrics(
    *,
    cue_id: str = "chorus-home",
    timestamp_ms: int = 1_500,
    section_id: str = "chorus_1",
) -> LyricContextModel:
    return LyricContextModel(
        has_lyrics=True,
        vocal_coverage_pct=0.25,
        moment_cues=[
            MomentCue(
                cue_id=cue_id,
                timestamp_ms=timestamp_ms,
                section_id=section_id,
                emphasis="HIGH",
                text="light the way home",
                visual_hint="Open a white fan from center on home.",
            )
        ],
    )


def _plan(
    cue_id: str,
    *,
    section_name: str = "chorus_1",
    start_bar: int = 1,
    end_bar: int = 2,
    include_gobo: bool = False,
) -> ChoreographyPlan:
    return ChoreographyPlan(
        sections=[
            PlanSection(
                section_name=section_name,
                start_bar=start_bar,
                end_bar=end_bar,
                template_id="sweep_lr_fan_hold",
                moment_cues=[MomentCueReference(cue_id=cue_id)],
                shutter_events=[
                    ShutterEvent(
                        bar=start_bar,
                        beat=1,
                        pattern="strobe_fast",
                        moment_cue_id=cue_id,
                    )
                ],
                gobo_events=(
                    [
                        GoboEvent(
                            bar=start_bar,
                            beat=1,
                            pattern="stars",
                            moment_cue_id=cue_id,
                        )
                    ]
                    if include_gobo
                    else []
                ),
            )
        ],
        overall_strategy="Accentuate the lyric hook.",
    )


def _bind(
    plan: ChoreographyPlan,
    lyrics: LyricContextModel,
    *,
    sections: list[SongSectionRef] | None = None,
) -> ChoreographyPlan:
    return bind_lyric_moment_cues(
        plan,
        lyrics,
        BeatGrid.from_tempo(tempo_bpm=120, total_bars=2),
        sections or [_section()],
    )


def test_unknown_lyric_moment_cue_reference_is_rejected() -> None:
    with pytest.raises(ValueError, match="unknown lyric MomentCue id 'missing'"):
        _bind(_plan("missing"), _lyrics())


def test_shutter_and_gobo_resolve_to_exact_grid_beat() -> None:
    bound = _bind(_plan("chorus-home", include_gobo=True), _lyrics())

    assert (bound.sections[0].shutter_events[0].bar, bound.sections[0].shutter_events[0].beat) == (
        1,
        4,
    )
    assert (bound.sections[0].gobo_events[0].bar, bound.sections[0].gobo_events[0].beat) == (
        1,
        4,
    )


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
    bound = _bind(
        _plan("chorus-home", end_bar=2),
        _lyrics(timestamp_ms=timestamp_ms),
    )

    event = bound.sections[0].shutter_events[0]
    assert (event.bar, event.beat) == expected


def test_exact_section_boundary_belongs_to_following_unique_section_id() -> None:
    sections = [
        _section("chorus_1", start_ms=0, end_ms=2_000),
        _section("chorus_2", start_ms=2_000, end_ms=4_000),
    ]
    bound = _bind(
        _plan("second-hit", section_name="chorus_2", start_bar=2, end_bar=2),
        _lyrics(cue_id="second-hit", timestamp_ms=2_000, section_id="chorus_2"),
        sections=sections,
    )

    event = bound.sections[0].shutter_events[0]
    assert bound.sections[0].section_name == "chorus_2"
    assert (event.bar, event.beat) == (2, 1)


def test_repeated_section_name_is_ambiguous_but_unique_id_binds() -> None:
    sections = [
        _section("chorus_1", start_ms=0, end_ms=2_000),
        _section("chorus_2", start_ms=2_000, end_ms=4_000),
    ]
    with pytest.raises(ValueError, match=r"ambiguous.*chorus_1, chorus_2"):
        _bind(
            _plan("second-hit", section_name="chorus", start_bar=2, end_bar=2),
            _lyrics(cue_id="second-hit", timestamp_ms=2_500, section_id="chorus_2"),
            sections=sections,
        )


def test_cue_outside_declared_section_is_rejected_before_endpoint_clamping() -> None:
    sections = [
        _section("chorus_1", start_ms=0, end_ms=2_000),
        _section("chorus_2", start_ms=2_000, end_ms=4_000),
    ]
    with pytest.raises(ValueError, match="outside section 'chorus_1'"):
        _bind(
            _plan("late", section_name="chorus_1"),
            _lyrics(cue_id="late", timestamp_ms=4_500, section_id="chorus_1"),
            sections=sections,
        )


def test_grid_resolved_event_outside_plan_bar_range_is_rejected() -> None:
    with pytest.raises(ValueError, match="resolves to bar 2, outside section"):
        _bind(
            _plan("late", start_bar=1, end_bar=1),
            _lyrics(cue_id="late", timestamp_ms=2_000),
        )
