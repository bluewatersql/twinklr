"""Golden A/B proof that a lyric cue changes the emitted artifact at grid time."""

from tests.golden.harness import RIGS, build_fixture_group
from twinklr.core.agents.audio.lyrics.models import LyricContextModel, MomentCue
from twinklr.core.agents.audio.profile.models import SongSectionRef
from twinklr.core.agents.sequencer.moving_heads.models import (
    ChoreographyPlan,
    MomentCueReference,
    PlanSection,
    ShutterEvent,
)
from twinklr.core.agents.sequencer.moving_heads.moment_cues import bind_lyric_moment_cues
from twinklr.core.config.models import JobConfig
from twinklr.core.sequencer.models.enum import ChannelName
from twinklr.core.sequencer.moving_heads.pipeline import RenderingPipeline
from twinklr.core.sequencer.timing.beat_grid import BeatGrid


def _render(plan: ChoreographyPlan, grid: BeatGrid):
    return RenderingPipeline(
        choreography_plan=plan,
        beat_grid=grid,
        fixture_group=build_fixture_group(RIGS["mh4_shutter_in_window"]),
        job_config=JobConfig(),
    ).render()


def test_lyric_moment_cue_adds_event_at_grid_resolved_timestamp() -> None:
    grid = BeatGrid.from_tempo(tempo_bpm=120, total_bars=4)
    baseline = ChoreographyPlan(
        sections=[
            PlanSection(
                section_name="chorus_1",
                start_bar=1,
                end_bar=4,
                template_id="sweep_lr_fan_hold",
            )
        ]
    )
    cue_plan = ChoreographyPlan(
        sections=[
            PlanSection(
                section_name="chorus_1",
                start_bar=1,
                end_bar=4,
                template_id="sweep_lr_fan_hold",
                moment_cues=[MomentCueReference(cue_id="chorus-home")],
                shutter_events=[
                    ShutterEvent(
                        bar=1,
                        beat=1,
                        pattern="strobe_fast",
                        moment_cue_id="chorus-home",
                    )
                ],
            )
        ]
    )
    lyrics = LyricContextModel(
        has_lyrics=True,
        vocal_coverage_pct=0.25,
        moment_cues=[
            MomentCue(
                cue_id="chorus-home",
                timestamp_ms=1_450,
                section_id="chorus_1",
                emphasis="HIGH",
                text="light the way home",
                visual_hint="Open a white fan from center on home.",
            )
        ],
    )

    before = _render(baseline, grid)
    after = _render(
        bind_lyric_moment_cues(
            cue_plan,
            lyrics,
            grid,
            [
                SongSectionRef(
                    section_id="chorus_1",
                    name="chorus",
                    start_ms=0,
                    end_ms=8_000,
                )
            ],
        ),
        grid,
    )

    def has_cue_strobe(segments) -> bool:
        return any(
            segment.t0_ms == 1_500
            and (channel := segment.channels.get(ChannelName.SHUTTER)) is not None
            and channel.static_dmx == 190
            for segment in segments
        )

    assert not has_cue_strobe(before)
    assert has_cue_strobe(after)
