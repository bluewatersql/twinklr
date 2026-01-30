"""Unit tests for transition detector."""

import pytest

from twinklr.core.agents.sequencer.moving_heads.models import ChoreographyPlan, PlanSection
from twinklr.core.curves.registry import CurveRegistry
from twinklr.core.sequencer.models.compiler import ScheduledInstance
from twinklr.core.sequencer.models.context import TemplateCompileContext
from twinklr.core.sequencer.models.enum import (
    QuantizeMode,
    SemanticGroupType,
    TemplateCategory,
    TimingMode,
)
from twinklr.core.sequencer.models.template import (
    BaseTiming,
    Dimmer,
    Geometry,
    Movement,
    RemainderPolicy,
    RepeatContract,
    RepeatMode,
    StepTiming,
    Template,
    TemplateStep,
)
from twinklr.core.sequencer.models.transition import BoundaryType
from twinklr.core.sequencer.moving_heads.compile.scheduler import ScheduleResult
from twinklr.core.sequencer.moving_heads.compile.transition_detector import (
    TransitionDetector,
)
from twinklr.core.sequencer.moving_heads.handlers.registry import (
    DimmerRegistry,
    GeometryRegistry,
    MovementRegistry,
)
from twinklr.core.sequencer.moving_heads.libraries.dimmer import DimmerType
from twinklr.core.sequencer.moving_heads.libraries.geometry import GeometryType
from twinklr.core.sequencer.moving_heads.libraries.movement import MovementType
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


class TestTransitionDetectorStepBoundaries:
    """Test step boundary detection."""

    def test_detect_step_boundaries_two_steps(self, beat_grid, registries):
        """Test detecting boundary between two steps."""
        template = Template(
            template_id="test_template",
            version=1,
            name="Test Template",
            category=TemplateCategory.MEDIUM_ENERGY,
            roles=[],
            repeat=RepeatContract(
                repeatable=False,
                mode=RepeatMode.PING_PONG,
                cycle_bars=4.0,
                loop_step_ids=[],
                remainder_policy=RemainderPolicy.HOLD_LAST_POSE,
            ),
            steps=[
                TemplateStep(
                    step_id="intro",
                    target=SemanticGroupType.ALL,
                    timing=StepTiming(
                        base_timing=BaseTiming(
                            mode=TimingMode.MUSICAL,
                            quantize_type=QuantizeMode.DOWNBEAT,
                            start_offset_bars=0.0,
                            duration_bars=2.0,
                        )
                    ),
                    geometry=Geometry(geometry_type=GeometryType.NONE),
                    movement=Movement(movement_type=MovementType.NONE),
                    dimmer=Dimmer(dimmer_type=DimmerType.NONE),
                ),
                TemplateStep(
                    step_id="main",
                    target=SemanticGroupType.ALL,
                    timing=StepTiming(
                        base_timing=BaseTiming(
                            mode=TimingMode.MUSICAL,
                            quantize_type=QuantizeMode.DOWNBEAT,
                            start_offset_bars=2.0,
                            duration_bars=2.0,
                        )
                    ),
                    geometry=Geometry(geometry_type=GeometryType.NONE),
                    movement=Movement(movement_type=MovementType.NONE),
                    dimmer=Dimmer(dimmer_type=DimmerType.NONE),
                ),
            ],
        )

        # Create a simple schedule result with two step instances
        schedule_result = ScheduleResult(
            instances=[
                ScheduledInstance(step_id="intro", start_bars=0.0, end_bars=2.0, cycle_number=0),
                ScheduledInstance(step_id="main", start_bars=2.0, end_bars=4.0, cycle_number=0),
            ],
            num_complete_cycles=1,
            remainder_policy=RemainderPolicy.HOLD_LAST_POSE,
        )

        # Create a minimal compile context
        # Section starts at bar 1, so absolute time is (bar - 1) * ms_per_bar
        context = TemplateCompileContext(
            section_id="test_section",
            template_id="test_template",
            preset_id=None,
            fixtures=[],
            beat_grid=beat_grid,
            start_bar=1,
            duration_bars=4,
            n_samples=64,
            curve_registry=registries["curve"],
            geometry_registry=registries["geometry"],
            movement_registry=registries["movement"],
            dimmer_registry=registries["dimmer"],
        )

        detector = TransitionDetector()
        boundaries = detector.detect_step_boundaries(template, schedule_result, context)

        assert len(boundaries) == 1

        boundary = boundaries[0]
        assert boundary.type == BoundaryType.STEP_BOUNDARY
        assert "intro" in boundary.source_id
        assert "main" in boundary.target_id
        # Boundary at relative bar 2.0, absolute ms = start_ms + (2.0 * 2000) = 0 + 4000 = 4000ms
        assert boundary.time_ms == 4000

    def test_detect_no_step_boundaries_single_step(self, beat_grid, registries):
        """Test that no boundaries are detected for a single step."""
        template = Template(
            template_id="single_step_template",
            version=1,
            name="Single Step Template",
            category=TemplateCategory.MEDIUM_ENERGY,
            roles=[],
            repeat=RepeatContract(
                repeatable=False,
                mode=RepeatMode.PING_PONG,
                cycle_bars=4.0,
                loop_step_ids=[],
                remainder_policy=RemainderPolicy.HOLD_LAST_POSE,
            ),
            steps=[
                TemplateStep(
                    step_id="only_step",
                    target=SemanticGroupType.ALL,
                    timing=StepTiming(
                        base_timing=BaseTiming(
                            mode=TimingMode.MUSICAL,
                            quantize_type=QuantizeMode.DOWNBEAT,
                            start_offset_bars=0.0,
                            duration_bars=4.0,
                        )
                    ),
                    geometry=Geometry(geometry_type=GeometryType.NONE),
                    movement=Movement(movement_type=MovementType.NONE),
                    dimmer=Dimmer(dimmer_type=DimmerType.NONE),
                ),
            ],
        )

        schedule_result = ScheduleResult(
            instances=[
                ScheduledInstance(step_id="only_step", start_bars=0.0, end_bars=4.0, cycle_number=0)
            ],
            num_complete_cycles=1,
            remainder_policy=RemainderPolicy.HOLD_LAST_POSE,
        )

        context = TemplateCompileContext(
            section_id="test_section",
            template_id="single_step_template",
            preset_id=None,
            fixtures=[],
            beat_grid=beat_grid,
            start_bar=1,
            duration_bars=4,
            n_samples=64,
            curve_registry=registries["curve"],
            geometry_registry=registries["geometry"],
            movement_registry=registries["movement"],
            dimmer_registry=registries["dimmer"],
        )

        detector = TransitionDetector()
        boundaries = detector.detect_step_boundaries(template, schedule_result, context)

        assert len(boundaries) == 0


class TestTransitionDetectorCycleBoundaries:
    """Test cycle boundary detection."""

    def test_cycle_boundaries_not_yet_implemented(self, beat_grid, registries):
        """Test that cycle boundaries return empty list (not yet implemented)."""
        template = Template(
            template_id="test_template",
            version=1,
            name="Test Template",
            category=TemplateCategory.MEDIUM_ENERGY,
            roles=[],
            repeat=RepeatContract(
                repeatable=True,
                mode=RepeatMode.PING_PONG,
                cycle_bars=4.0,
                loop_step_ids=["step1"],
                remainder_policy=RemainderPolicy.HOLD_LAST_POSE,
            ),
            steps=[
                TemplateStep(
                    step_id="step1",
                    target=SemanticGroupType.ALL,
                    timing=StepTiming(
                        base_timing=BaseTiming(
                            mode=TimingMode.MUSICAL,
                            quantize_type=QuantizeMode.DOWNBEAT,
                            start_offset_bars=0.0,
                            duration_bars=4.0,
                        )
                    ),
                    geometry=Geometry(geometry_type=GeometryType.NONE),
                    movement=Movement(movement_type=MovementType.NONE),
                    dimmer=Dimmer(dimmer_type=DimmerType.NONE),
                ),
            ],
        )

        schedule_result = ScheduleResult(
            instances=[
                ScheduledInstance(step_id="step1", start_bars=0.0, end_bars=4.0, cycle_number=0),
                ScheduledInstance(step_id="step1", start_bars=4.0, end_bars=8.0, cycle_number=1),
            ],
            num_complete_cycles=2,
            remainder_policy=RemainderPolicy.HOLD_LAST_POSE,
        )

        context = TemplateCompileContext(
            section_id="test_section",
            template_id="test_template",
            preset_id=None,
            fixtures=[],
            beat_grid=beat_grid,
            start_bar=1,
            duration_bars=8,
            n_samples=64,
            curve_registry=registries["curve"],
            geometry_registry=registries["geometry"],
            movement_registry=registries["movement"],
            dimmer_registry=registries["dimmer"],
        )

        detector = TransitionDetector()
        boundaries = detector.detect_cycle_boundaries(template, schedule_result, context)

        # Not yet implemented, should return empty list
        assert len(boundaries) == 0
