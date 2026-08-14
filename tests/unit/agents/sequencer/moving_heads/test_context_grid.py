"""P1P-T4: the planner numbers bars against the same grid the renderer uses.

`MovingHeadPlanningContext._ms_to_bar` produces the `start_bar`/`end_bar` the
renderer is later handed. Before this task it converted with a nominal tempo
anchored at 0 ms and *floored*, quantizing every section start down by up to a
whole bar (~2 s at 120 BPM) before the renderer's own average-grid error was even
applied. The two errors were independent and did not cancel.
"""

from __future__ import annotations

import logging

import pytest

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
        context = make_context(uneven)
        sections = context.for_prompt()["song_structure"]["sections"]
        assert [(s["start_bar"], s["end_bar"]) for s in sections] == [(1, 3), (3, 5)]

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
        from twinklr.core.curves.registry import CurveRegistry
        from twinklr.core.sequencer.models.context import TemplateCompileContext
        from twinklr.core.sequencer.moving_heads.handlers.defaults import (
            create_default_registries,
        )

        registries = create_default_registries()
        planner = make_context(uneven)
        renderer = TemplateCompileContext(
            section_id="section",
            template_id="template",
            fixtures=[],
            beat_grid=uneven,
            start_bar=1,
            duration_bars=1,
            curve_registry=CurveRegistry(),
            geometry_registry=registries["geometry"],
            movement_registry=registries["movement"],
            dimmer_registry=registries["dimmer"],
        )

        for bar in range(1, len(UNEVEN_BARS) + 1):
            assert planner._ms_to_bar(renderer._bar_to_ms(bar)) == bar
