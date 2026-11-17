"""P1P-T4: the planner numbers bars against the same grid the renderer uses.

`MovingHeadPlanningContext._ms_to_bar` produces the `start_bar`/`end_bar` the
renderer is later handed. Before this task it converted with a nominal tempo
anchored at 0 ms and *floored*, quantizing every section start down by up to a
whole bar (~2 s at 120 BPM) before the renderer's own average-grid error was even
applied. The two errors were independent and did not cancel.
"""

from __future__ import annotations

from itertools import pairwise
import logging

import pytest

from tests.support.moving_heads import plan_section
from tests.unit.agents.sequencer.moving_heads.test_context import (
    create_minimal_audio_profile,
)
from twinklr.core.agents.audio.profile.models import SongSectionRef
from twinklr.core.agents.sequencer.moving_heads.context import (
    FixtureContext,
    MovingHeadPlanningContext,
)
from twinklr.core.sequencer.timing.beat_grid import BeatGrid

# Bars of 2000 / 2500 / 1500 / 2500 ms starting at 1500 ms; average 2125 ms.
UNEVEN_BARS = [1500.0, 3500.0, 6000.0, 7500.0, 10000.0]


def make_grid(bar_boundaries: list[float]) -> BeatGrid:
    return BeatGrid(
        bar_boundaries=bar_boundaries,
        beat_boundaries=list(bar_boundaries),
        eighth_boundaries=[],
        sixteenth_boundaries=[],
        tempo_bpm=120.0,
        beats_per_bar=4,
        duration_ms=bar_boundaries[-1],
    )


def make_context(
    beat_grid: BeatGrid | None,
    sections: list[SongSectionRef] | None = None,
) -> MovingHeadPlanningContext:
    if sections is None:
        sections = [
            SongSectionRef(section_id="intro", name="intro", start_ms=1500, end_ms=6000),
            SongSectionRef(section_id="verse_1", name="verse", start_ms=6000, end_ms=10000),
        ]
    return MovingHeadPlanningContext(
        audio_profile=create_minimal_audio_profile(duration_ms=10000, sections=sections),
        fixtures=FixtureContext(count=4),
        available_templates=["sweep_lr_fan_hold"],
        beat_grid=beat_grid,
    )


@pytest.fixture
def uneven() -> BeatGrid:
    return make_grid(UNEVEN_BARS)


class TestMsToBarWithGrid:
    def test_ms_to_bar_rounds_to_nearest_downbeat(self, uneven: BeatGrid) -> None:
        """The assertion that fails on the floor implementation.

        100ms *after* bar 2's downbeat resolves to bar 2, as flooring also would.
        100ms *before* bar 3's downbeat resolves to bar 3 — flooring said bar 2 and
        dragged the section back a whole bar.
        """
        context = make_context(uneven)
        assert context._ms_to_bar(3600) == 2
        assert context._ms_to_bar(5900) == 3

    def test_detected_downbeats_map_to_their_own_bars(self, uneven: BeatGrid) -> None:
        context = make_context(uneven)
        for index, boundary in enumerate(UNEVEN_BARS):
            assert context._ms_to_bar(int(boundary)) == index + 1

    def test_nominal_tempo_is_ignored_when_a_grid_is_present(self, uneven: BeatGrid) -> None:
        """6000ms is bar 3 on the real grid; at a nominal 120 BPM it would be bar 4."""
        context = make_context(uneven)
        assert context.tempo == 120.0
        assert context._ms_to_bar(6000) == 3

    def test_total_bars_counts_detected_downbeats(self, uneven: BeatGrid) -> None:
        context = make_context(uneven)
        assert context.total_bars == len(UNEVEN_BARS)

    def test_prompt_section_bars_come_from_the_grid(self, uneven: BeatGrid) -> None:
        """Inclusive bars: a section ends on the bar before the one its end time
        resolves to, so consecutive sections share no bar and the last ends on the
        song's last bar (bar 5 starts at the song's end, 10000 ms)."""
        context = make_context(uneven)
        sections = context.for_prompt()["song_structure"]["sections"]
        assert [(s["start_bar"], s["end_bar"]) for s in sections] == [(1, 2), (3, 4)]
        assert all(
            set(s) == {"name", "section_id", "start_ms", "end_ms", "start_bar", "end_bar"}
            for s in sections
        )

    def test_section_starts_are_monotonic_non_decreasing(self, uneven: BeatGrid) -> None:
        """Rounding must never reorder sections, however short they are."""
        sections = [
            SongSectionRef(section_id="a", name="a", start_ms=1500, end_ms=3400),
            SongSectionRef(section_id="b", name="b", start_ms=3400, end_ms=3600),
            SongSectionRef(section_id="c", name="c", start_ms=3600, end_ms=10000),
        ]
        context = make_context(uneven, sections)
        start_bars = [s["start_bar"] for s in context.for_prompt()["song_structure"]["sections"]]
        assert start_bars == sorted(start_bars)

    def test_sub_bar_section_collapse_is_reported(
        self, uneven: BeatGrid, caplog: pytest.LogCaptureFixture
    ) -> None:
        """A section shorter than a bar collapses onto one downbeat; say so.

        Short-section rendering belongs to P1P-T5, so this records the case rather
        than silently overlapping the neighbouring section.
        """
        sections = [
            SongSectionRef(section_id="a", name="a", start_ms=1500, end_ms=3400),
            SongSectionRef(section_id="blip", name="blip", start_ms=3400, end_ms=3600),
            SongSectionRef(section_id="c", name="c", start_ms=3600, end_ms=10000),
        ]
        context = make_context(uneven, sections)
        logger_name = "twinklr.core.agents.sequencer.moving_heads.context"
        with caplog.at_level(logging.WARNING, logger=logger_name):
            context.for_prompt()

        assert "shorter than one bar" in caplog.text
        assert "same downbeat as the preceding section" in caplog.text


class TestMsToBarWithoutGrid:
    def test_no_grid_available_falls_back_and_logs(self, caplog: pytest.LogCaptureFixture) -> None:
        """The nominal-tempo path survives only as a logged last resort."""
        context = make_context(None)
        logger_name = "twinklr.core.agents.sequencer.moving_heads.context"
        with caplog.at_level(logging.WARNING, logger=logger_name):
            context.for_prompt()

        assert "No beat grid supplied to the moving-head planner" in caplog.text

    def test_fallback_still_rounds_rather_than_floors(self) -> None:
        """Flooring is the defect, so the degraded path must not reintroduce it.

        At 120 BPM a bar is 2000ms. 1900ms is 100ms short of bar 2's nominal start,
        which the floor sent to bar 1.
        """
        context = make_context(None)
        assert context._ms_to_bar(0) == 1
        assert context._ms_to_bar(1900) == 2
        assert context._ms_to_bar(2000) == 2
        assert context._ms_to_bar(2100) == 2

    def test_fallback_uses_120_bpm_when_tempo_is_unknown(self) -> None:
        profile = create_minimal_audio_profile()
        profile.song_identity.bpm = None
        context = MovingHeadPlanningContext(
            audio_profile=profile,
            fixtures=FixtureContext(count=4),
            available_templates=["sweep_lr_fan_hold"],
        )
        assert context.tempo is None
        # 120 BPM in 4/4 -> 2000ms bars: 4000ms is bar 3.
        assert context._ms_to_bar(4000) == 3


class TestPlannerAndRendererAgree:
    def test_bar_round_trip_is_identity(self, uneven: BeatGrid) -> None:
        """The plan's bar numbers survive the renderer's conversion back to ms.

        This is the property the whole task exists for: `_ms_to_bar` and
        `TemplateCompileContext._bar_to_ms` are inverses over the detected range.
        """
        from twinklr.core.sequencer.models.context import TemplateCompileContext

        planner = make_context(uneven)
        renderer = TemplateCompileContext(
            section_id="section",
            template_id="template",
            fixtures=[],
            beat_grid=uneven,
            start_bar=1,
            duration_bars=1,
        )

        for bar in range(1, len(UNEVEN_BARS) + 1):
            assert planner._ms_to_bar(renderer._bar_to_ms(bar)) == bar


# The 2026-11-17 "Need A Favor" shape: 61 bars of 3000 ms from 2000 ms, so the grid
# ends at 185 000 ms, 12.4 s before the 197 400 ms song does.
SHORT_GRID_BARS = [2000.0 + 3000.0 * index for index in range(61)]
SHORT_GRID_SONG = [
    ("intro", 0, 32000),
    ("verse_1", 32000, 62000),
    ("verse_2", 62000, 95000),
    ("chorus_1", 95000, 128000),
    ("break", 128000, 158000),
    ("chorus_2", 158000, 191000),  # starts inside the grid, ends beyond it
    ("verse_3", 191000, 197400),  # starts beyond the grid's last bar
]
# The "Dance Jams" shape: 135 bars of 2000 ms from 0; the grid ends at 270 000 ms.
DANCE_GRID_BARS = [2000.0 * index for index in range(135)]
DANCE_SONG = [
    ("verse_1", 0, 250000),
    ("instrumental", 250000, 274000),
    ("verse_2", 274000, 278000),
]


def short_grid_context(
    bars: list[float] = SHORT_GRID_BARS,
    song: list[tuple[str, int, int]] = SHORT_GRID_SONG,
) -> MovingHeadPlanningContext:
    """A song whose beat grid stops before the audio ends."""
    sections = [
        SongSectionRef(section_id=section_id, name=section_id.split("_")[0], start_ms=a, end_ms=b)
        for section_id, a, b in song
    ]
    grid = make_grid(bars).model_copy(update={"duration_ms": float(song[-1][2])})
    return MovingHeadPlanningContext(
        audio_profile=create_minimal_audio_profile(duration_ms=song[-1][2], sections=sections),
        fixtures=FixtureContext(count=4),
        available_templates=["sweep_lr_fan_hold"],
        beat_grid=grid,
    )


class TestGridShorterThanTheSong:
    def test_bars_stay_within_the_grid_and_the_out_of_grid_section_is_left_out(self) -> None:
        context = short_grid_context()
        structure = context.for_prompt()["song_structure"]
        bars = [(s["section_id"], s["start_bar"], s["end_bar"]) for s in structure["sections"]]

        assert structure["total_bars"] == 61
        assert bars == [
            ("intro", 1, 10),
            ("verse_1", 11, 20),
            ("verse_2", 21, 31),
            ("chorus_1", 32, 42),
            ("break", 43, 52),
            ("chorus_2", 53, 61),
        ]
        assert structure["beyond_grid"] == {
            "from_ms": 185000,
            "seconds": 12.4,
            "section_ids": ["verse_3"],
        }

    def test_the_dance_jams_shape_is_clamped_the_same_way(self) -> None:
        structure = short_grid_context(DANCE_GRID_BARS, DANCE_SONG).song_structure()
        bars = [(s["section_id"], s["start_bar"], s["end_bar"]) for s in structure["sections"]]

        assert bars == [("verse_1", 1, 125), ("instrumental", 126, 135)]
        assert structure["beyond_grid"]["section_ids"] == ["verse_2"]
        assert structure["beyond_grid"]["seconds"] == 8.0

    @pytest.mark.parametrize(
        ("bars", "song"),
        [(SHORT_GRID_BARS, SHORT_GRID_SONG), (DANCE_GRID_BARS, DANCE_SONG)],
    )
    def test_the_table_is_contiguous_and_ends_on_the_last_bar(
        self, bars: list[float], song: list[tuple[str, int, int]]
    ) -> None:
        structure = short_grid_context(bars, song).song_structure()
        sections = structure["sections"]

        assert sections[0]["start_bar"] == 1
        assert all(b["start_bar"] == a["end_bar"] + 1 for a, b in pairwise(sections))
        assert sections[-1]["end_bar"] == structure["total_bars"]

    def test_the_cut_is_reported(self, caplog: pytest.LogCaptureFixture) -> None:
        with caplog.at_level(logging.WARNING):
            short_grid_context().song_structure()
        assert "The beat grid ends at bar 61 (185.0 s), 12.4 s before the song ends" in caplog.text
        assert "verse_3 left unplanned" in caplog.text

    def test_a_grid_covering_the_song_has_nothing_beyond_it(self, uneven: BeatGrid) -> None:
        assert make_context(uneven).song_structure()["beyond_grid"] is None


class TestThePlannerIsNotShownASectionBeyondTheGrid:
    """The prompts say what the grid leaves unplanned, and show no macro row, palette
    line, focal entry or lyric-cue advice for a section beyond it."""

    @staticmethod
    def _context() -> MovingHeadPlanningContext:
        from tests.unit.agents.sequencer.moving_heads.test_orchestrator import (
            create_test_macro_plan,
        )

        context = short_grid_context()
        return context.model_copy(
            update={
                "macro_plan": create_test_macro_plan(context.audio_profile),
                "head_focal_roles": {section_id: "LEAD" for section_id, *_ in SHORT_GRID_SONG},
            }
        )

    @staticmethod
    def _render(pack: str, variables: dict) -> str:
        from pathlib import Path

        from twinklr.core.agents.prompts.loader import PromptPackLoader
        from twinklr.core.agents.prompts.renderer import PromptRenderer

        base = (
            Path(__file__).parents[5]
            / "packages/twinklr/core/agents/sequencer/moving_heads/prompts"
        )
        return PromptRenderer().render(
            PromptPackLoader(base_path=base).load(pack)["user"], variables
        )

    def test_the_planner_prompt_says_what_is_left_out_and_shows_no_such_section(self) -> None:
        from twinklr.core.agents.sequencer.moving_heads.orchestrator import (
            build_planner_variables,
        )

        variables = build_planner_variables(self._context())
        assert variables["beyond_grid"]["section_ids"] == ["verse_3"]
        rendered = self._render("planner", {**variables, "response_schema": "{}"})

        assert (
            "The last 12.4 s of the song lie beyond the detected beat grid and are not "
            "planned (verse_3 left out)."
        ) in rendered
        assert "| chorus_2 |" in rendered
        assert "verse_3 |" not in rendered and "**verse_3**" not in rendered
        assert "`verse_3`" not in rendered

    def test_the_judge_prompt_says_the_plan_without_them_is_complete(self) -> None:
        from twinklr.core.agents.sequencer.moving_heads.models import ChoreographyPlan
        from twinklr.core.agents.sequencer.moving_heads.orchestrator import build_judge_variables
        from twinklr.core.agents.shared.judge.controller import IterationContext

        variables = build_judge_variables(
            self._context(),
            ChoreographyPlan(
                sections=[plan_section("intro", 1, 10, "mirror_wings")], overall_strategy="x"
            ),
            0,
            IterationContext(),
        )
        assert variables["beyond_grid"]["section_ids"] == ["verse_3"]
        rendered = self._render("judge", {**variables, "response_schema": "{}"})
        assert "(verse_3 left out): a plan without them is complete." in rendered
        assert "| verse_3 |" not in rendered

    def test_no_lyric_cue_beyond_the_grid_is_advised(self) -> None:
        from twinklr.core.agents.audio.lyrics.models import LyricContextModel, MomentCue
        from twinklr.core.agents.sequencer.moving_heads.models import ChoreographyPlan
        from twinklr.core.agents.sequencer.moving_heads.moment_cues import unanswered_high_cues

        context = self._context()
        cues = LyricContextModel(
            has_lyrics=True,
            vocal_coverage_pct=0.5,
            moment_cues=[
                MomentCue(
                    cue_id=cue_id,
                    section_id=section_id,
                    timestamp_ms=at,
                    emphasis="HIGH",
                    text="la",
                    visual_hint="Accent it.",
                )
                for cue_id, section_id, at in (
                    ("in", "chorus_2", 160000),
                    ("out", "verse_3", 193000),
                )
            ],
        )
        plan = ChoreographyPlan(
            sections=[plan_section("intro", 1, 10, "mirror_wings")], overall_strategy="x"
        )

        advised = unanswered_high_cues(plan, cues, context.sections)
        assert len(advised) == 2
        (kept,) = unanswered_high_cues(plan, cues, context.sections, unplannable=("verse_3",))
        assert "'chorus_2'" in kept
