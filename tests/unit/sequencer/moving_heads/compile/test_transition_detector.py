"""Unit tests for transition detector."""

import pytest

from twinklr.core.agents.sequencer.moving_heads.models import ChoreographyPlan, PlanSection
from twinklr.core.curves.registry import CurveRegistry
from twinklr.core.sequencer.models.context import TemplateCompileContext
from twinklr.core.sequencer.models.transition import BoundaryType
from twinklr.core.sequencer.moving_heads.compile.transition_detector import (
    TransitionDetector,
)
from twinklr.core.sequencer.moving_heads.handlers.registry import (
    DimmerRegistry,
    GeometryRegistry,
    MovementRegistry,
)
from twinklr.core.sequencer.timing.beat_grid import BeatGrid


@pytest.fixture
def beat_grid():
    """Create a beat grid for testing (120 BPM, 4/4 time)."""
    # 120 BPM = 2 beats per second = 500ms per beat = 2000ms per bar
    return BeatGrid.from_tempo(
        tempo_bpm=120.0,
        total_bars=64,
        beats_per_bar=4,
        start_offset_ms=0.0,
    )


@pytest.fixture
def registries():
    """Create registry instances for testing."""
    return {
        "curve": CurveRegistry(),
        "geometry": GeometryRegistry(),
        "movement": MovementRegistry(),
        "dimmer": DimmerRegistry(),
    }


class TestTransitionDetectorSectionBoundaries:
    """Test section boundary detection."""

    def test_detect_single_boundary(self, beat_grid):
        """Test detecting a single boundary between two sections."""
        plan = ChoreographyPlan(
            sections=[
                PlanSection(
                    section_name="intro",
                    start_bar=1,
                    end_bar=8,
                    template_id="template_intro",
                    preset_id="CHILL",
                ),
                PlanSection(
                    section_name="verse_1",
                    start_bar=9,
                    end_bar=16,
                    template_id="template_verse",
                    preset_id="MODERATE",
                ),
            ]
        )

        detector = TransitionDetector()
        boundaries = detector.detect_section_boundaries(plan, beat_grid)

        assert len(boundaries) == 1

        boundary = boundaries[0]
        assert boundary.type == BoundaryType.SECTION_BOUNDARY
        assert boundary.source_id == "intro"
        assert boundary.target_id == "verse_1"
        assert boundary.bar_position == 9.0
        # Bar 9 at 120 BPM = 8 bars * 2000ms/bar = 16000ms
        assert boundary.time_ms == 16000

    def test_detect_multiple_boundaries(self, beat_grid):
        """Test detecting multiple boundaries in a plan."""
        plan = ChoreographyPlan(
            sections=[
                PlanSection(
                    section_name="intro",
                    start_bar=1,
                    end_bar=8,
                    template_id="template_intro",
                    preset_id="CHILL",
                ),
                PlanSection(
                    section_name="verse_1",
                    start_bar=9,
                    end_bar=16,
                    template_id="template_verse",
                    preset_id="MODERATE",
                ),
                PlanSection(
                    section_name="chorus_1",
                    start_bar=17,
                    end_bar=24,
                    template_id="template_chorus",
                    preset_id="ENERGETIC",
                ),
            ]
        )

        detector = TransitionDetector()
        boundaries = detector.detect_section_boundaries(plan, beat_grid)

        assert len(boundaries) == 2

        # First boundary: intro → verse_1
        assert boundaries[0].source_id == "intro"
        assert boundaries[0].target_id == "verse_1"
        assert boundaries[0].bar_position == 9.0

        # Second boundary: verse_1 → chorus_1
        assert boundaries[1].source_id == "verse_1"
        assert boundaries[1].target_id == "chorus_1"
        assert boundaries[1].bar_position == 17.0

    def test_detect_no_boundaries_single_section(self, beat_grid):
        """Test that no boundaries are detected for a single section."""
        plan = ChoreographyPlan(
            sections=[
                PlanSection(
                    section_name="only_section",
                    start_bar=1,
                    end_bar=16,
                    template_id="template_only",
                    preset_id="MODERATE",
                )
            ]
        )

        detector = TransitionDetector()
        boundaries = detector.detect_section_boundaries(plan, beat_grid)

        assert len(boundaries) == 0

    def test_boundary_timing_accuracy(self, beat_grid):
        """Test that boundary timing is accurate for different BPMs."""
        # Test with sections at various positions
        plan = ChoreographyPlan(
            sections=[
                PlanSection(
                    section_name="section_1",
                    start_bar=1,
                    end_bar=4,
                    template_id="t1",
                    preset_id="p1",
                ),
                PlanSection(
                    section_name="section_2",
                    start_bar=5,
                    end_bar=8,
                    template_id="t2",
                    preset_id="p2",
                ),
            ]
        )

        detector = TransitionDetector()
        boundaries = detector.detect_section_boundaries(plan, beat_grid)

        assert len(boundaries) == 1
        # Bar 5 at 120 BPM = 4 bars * 2000ms/bar = 8000ms
        assert boundaries[0].time_ms == 8000
        assert boundaries[0].bar_position == 5.0


class TestTransitionBoundariesUseTheSameGrid:
    """P1P-T4: boundary times come from the detected downbeats, not a bar average.

    The detector used to repeat the renderer's `(bar - 1) * ms_per_bar` formula
    independently. On a non-uniform grid that put transition boundaries somewhere
    other than the section starts they separate, so the crossfade straddled nothing.
    """

    @pytest.fixture
    def uneven_grid(self) -> BeatGrid:
        # Bars of 2000 / 2500 / 1500 / 2500 ms from 1500 ms; average 2125 ms.
        boundaries = [1500.0, 3500.0, 6000.0, 7500.0, 10000.0]
        return BeatGrid(
            bar_boundaries=boundaries,
            beat_boundaries=list(boundaries),
            eighth_boundaries=[],
            sixteenth_boundaries=[],
            tempo_bpm=120.0,
            beats_per_bar=4,
            duration_ms=10000.0,
        )

    def test_section_boundary_is_the_detected_downbeat(self, uneven_grid: BeatGrid) -> None:
        plan = ChoreographyPlan(
            sections=[
                PlanSection(section_name="intro", start_bar=1, end_bar=2, template_id="t"),
                PlanSection(section_name="verse", start_bar=3, end_bar=4, template_id="t"),
            ]
        )

        boundaries = TransitionDetector().detect_section_boundaries(plan, uneven_grid)

        assert len(boundaries) == 1
        # Bar 3's downbeat is 6000ms; two average bars from zero would be 4250ms.
        assert boundaries[0].time_ms == 6000
        assert boundaries[0].time_ms == int(uneven_grid.get_bar_start_ms(2))

    def test_section_boundary_matches_the_target_sections_start_ms(
        self, uneven_grid: BeatGrid, registries
    ) -> None:
        """The boundary and the section it opens agree to the millisecond."""
        plan = ChoreographyPlan(
            sections=[
                PlanSection(section_name="intro", start_bar=1, end_bar=2, template_id="t"),
                PlanSection(section_name="verse", start_bar=3, end_bar=4, template_id="t"),
            ]
        )
        target_context = TemplateCompileContext(
            section_id="verse",
            template_id="test_template",
            fixtures=[],
            beat_grid=uneven_grid,
            start_bar=3,
            duration_bars=2,
            curve_registry=registries["curve"],
            geometry_registry=registries["geometry"],
            movement_registry=registries["movement"],
            dimmer_registry=registries["dimmer"],
        )

        boundaries = TransitionDetector().detect_section_boundaries(plan, uneven_grid)

        assert boundaries[0].time_ms == target_context.start_ms
