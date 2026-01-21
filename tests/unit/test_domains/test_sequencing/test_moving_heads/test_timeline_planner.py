"""Tests for TemplateTimelinePlanner.

Tests the timeline planner that converts AgentImplementation into
an ExplodedTimeline with all segments ordered chronologically.
"""

from blinkb0t.core.agents.moving_heads.models_agent_plan import (
    AgentImplementation,
    ImplementationSection,
)
from blinkb0t.core.domains.sequencing.infrastructure.timing.beat_grid import BeatGrid
from blinkb0t.core.domains.sequencing.models.templates import Template
from blinkb0t.core.domains.sequencing.models.timeline import (
    ExplodedTimeline,
    GapSegment,
    TemplateStepSegment,
)
from blinkb0t.core.domains.sequencing.moving_heads.timeline_planner import (
    TemplateTimelinePlanner,
)

# ============================================================================
# TemplateTimelinePlanner Tests
# ============================================================================


def test_planner_creation():
    """Test TemplateTimelinePlanner can be instantiated."""
    planner = TemplateTimelinePlanner()
    assert planner is not None


def test_plan_empty_implementation():
    """Test planning with empty implementation returns empty timeline."""
    planner = TemplateTimelinePlanner()
    beat_grid = _create_test_beat_grid()
    template_library = {}

    implementation = AgentImplementation(
        sections=[],
        total_duration_bars=8,
        quantization_applied=True,
        timing_precision="bar_aligned",
    )

    timeline = planner.plan(
        choreography_plan=implementation,
        beat_grid=beat_grid,
        template_library=template_library,
        total_duration_ms=16000.0,
    )

    assert isinstance(timeline, ExplodedTimeline)
    assert len(timeline.segments) == 0
    assert timeline.total_duration_ms == 16000.0


def test_plan_single_section_single_step():
    """Test planning with single section containing one step."""
    planner = TemplateTimelinePlanner()
    beat_grid = _create_test_beat_grid()
    template_library = _create_test_template_library()

    section = ImplementationSection(
        name="verse_1",
        plan_section_name="verse_1",
        start_bar=1,
        end_bar=4,
        template_id="sweep_lr",
        params={"intensity": "SMOOTH"},
        base_pose="AUDIENCE_CENTER",
        targets=["ALL"],
        layer_priority=0,
    )

    implementation = AgentImplementation(
        sections=[section],
        total_duration_bars=4,
        quantization_applied=True,
        timing_precision="bar_aligned",
    )

    timeline = planner.plan(
        choreography_plan=implementation,
        beat_grid=beat_grid,
        template_library=template_library,
        total_duration_ms=8000.0,
    )

    assert isinstance(timeline, ExplodedTimeline)
    assert len(timeline.segments) == 1
    assert isinstance(timeline.segments[0], TemplateStepSegment)

    segment = timeline.segments[0]
    assert segment.section_id == "verse_1"
    assert segment.start_ms == 0.0
    assert segment.end_ms == 8000.0
    assert segment.template_id == "sweep_lr"
    assert segment.target == "ALL"
    assert segment.base_pose == "AUDIENCE_CENTER"


def test_plan_multiple_sections():
    """Test planning with multiple sections."""
    planner = TemplateTimelinePlanner()
    beat_grid = _create_test_beat_grid()
    template_library = _create_test_template_library()

    section1 = ImplementationSection(
        name="verse_1",
        plan_section_name="verse_1",
        start_bar=1,
        end_bar=4,
        template_id="sweep_lr",
        params={"intensity": "SMOOTH"},
        base_pose="AUDIENCE_CENTER",
        targets=["ALL"],
        layer_priority=0,
    )

    section2 = ImplementationSection(
        name="chorus_1",
        plan_section_name="chorus_1",
        start_bar=5,
        end_bar=8,
        template_id="circle",
        params={"intensity": "DRAMATIC"},
        base_pose="AUDIENCE_CENTER",
        targets=["ALL"],
        layer_priority=0,
    )

    implementation = AgentImplementation(
        sections=[section1, section2],
        total_duration_bars=8,
        quantization_applied=True,
        timing_precision="bar_aligned",
    )

    timeline = planner.plan(
        choreography_plan=implementation,
        beat_grid=beat_grid,
        template_library=template_library,
        total_duration_ms=16000.0,
    )

    assert isinstance(timeline, ExplodedTimeline)
    assert len(timeline.segments) == 2

    # Check segments are in order
    assert timeline.segments[0].start_ms == 0.0
    assert timeline.segments[0].end_ms == 8000.0
    assert timeline.segments[1].start_ms == 8000.0
    assert timeline.segments[1].end_ms == 16000.0


def test_plan_with_gaps():
    """Test planning detects and fills gaps in timeline."""
    planner = TemplateTimelinePlanner()
    beat_grid = _create_test_beat_grid()
    template_library = _create_test_template_library()

    # Section 1: Bars 1-2 (0-4000ms)
    section1 = ImplementationSection(
        name="verse_1",
        plan_section_name="verse_1",
        start_bar=1,
        end_bar=2,
        template_id="sweep_lr",
        params={"intensity": "SMOOTH"},
        base_pose="AUDIENCE_CENTER",
        targets=["ALL"],
        layer_priority=0,
    )

    # Section 2: Bars 4-5 (6000-10000ms with gap from bars 3-4)
    section2 = ImplementationSection(
        name="chorus_1",
        plan_section_name="chorus_1",
        start_bar=4,
        end_bar=5,
        template_id="circle",
        params={"intensity": "DRAMATIC"},
        base_pose="AUDIENCE_CENTER",
        targets=["ALL"],
        layer_priority=0,
    )

    implementation = AgentImplementation(
        sections=[section1, section2],
        total_duration_bars=5,
        quantization_applied=True,
        timing_precision="bar_aligned",
    )

    timeline = planner.plan(
        choreography_plan=implementation,
        beat_grid=beat_grid,
        template_library=template_library,
        total_duration_ms=10000.0,
    )

    # Should have: section1, gap, section2
    assert len(timeline.segments) == 3

    # Check gap is inserted
    assert isinstance(timeline.segments[1], GapSegment)
    gap = timeline.segments[1]
    assert gap.start_ms == 4000.0
    assert gap.end_ms == 6000.0
    assert gap.gap_type == "inter_section"


def test_plan_template_with_steps():
    """Test planning template with multiple steps."""
    from blinkb0t.core.domains.sequencing.models.templates import (
        PatternStep,
        PatternStepTiming,
        TemplateCategory,
        TemplateTiming,
    )
    from blinkb0t.core.domains.sequencing.models.timing import MusicalTiming, TimingMode

    planner = TemplateTimelinePlanner()
    beat_grid = _create_test_beat_grid()

    # Create template with 2 steps
    template_library = {
        "multi_step_template": Template(
            template_id="multi_step_template",
            name="Multi Step",
            category=TemplateCategory.MEDIUM_ENERGY,
            timing=TemplateTiming(mode=TimingMode.MUSICAL, default_duration_bars=4.0),
            steps=[
                PatternStep(
                    step_id="multi_step_0",
                    target="ALL",
                    timing=PatternStepTiming(
                        base_timing=MusicalTiming(
                            mode=TimingMode.MUSICAL,
                            duration_bars=2.0,
                            offset_bars=0.0,
                        )
                    ),
                    movement_id="sweep",
                    dimmer_id="full",
                    movement_params={"intensity": "SMOOTH"},
                    dimmer_params={"base_pct": 80},
                ),
                PatternStep(
                    step_id="multi_step_1",
                    target="ALL",
                    timing=PatternStepTiming(
                        base_timing=MusicalTiming(
                            mode=TimingMode.MUSICAL,
                            duration_bars=2.0,
                            offset_bars=2.0,
                        )
                    ),
                    movement_id="circle",
                    dimmer_id="pulse",
                    movement_params={"intensity": "DRAMATIC"},
                    dimmer_params={"intensity": "SMOOTH"},
                ),
            ],
        )
    }

    section = ImplementationSection(
        name="verse_1",
        plan_section_name="verse_1",
        start_bar=1,
        end_bar=4,
        template_id="multi_step_template",
        params={},
        base_pose="AUDIENCE_CENTER",
        targets=["ALL"],
        layer_priority=0,
    )

    implementation = AgentImplementation(
        sections=[section],
        total_duration_bars=4,
        quantization_applied=True,
        timing_precision="bar_aligned",
    )

    timeline = planner.plan(
        choreography_plan=implementation,
        beat_grid=beat_grid,
        template_library=template_library,
        total_duration_ms=8000.0,
    )

    # Should have 2 step segments (one per template step)
    assert len(timeline.segments) == 2
    assert all(isinstance(seg, TemplateStepSegment) for seg in timeline.segments)

    # Check timing
    assert timeline.segments[0].start_ms == 0.0
    assert timeline.segments[0].end_ms == 4000.0  # 2 bars @ 2000ms/bar
    assert timeline.segments[1].start_ms == 4000.0
    assert timeline.segments[1].end_ms == 8000.0


def test_plan_uses_template_transitions():
    """Test planning uses template-defined transitions (not agent-specified)."""
    planner = TemplateTimelinePlanner()
    beat_grid = _create_test_beat_grid()
    template_library = _create_test_template_library()

    section = ImplementationSection(
        name="verse_1",
        plan_section_name="verse_1",
        start_bar=1,
        end_bar=4,
        template_id="sweep_lr",
        params={"intensity": "SMOOTH"},
        base_pose="AUDIENCE_CENTER",
        targets=["ALL"],
        layer_priority=0,
    )

    implementation = AgentImplementation(
        sections=[section],
        total_duration_bars=4,
        quantization_applied=True,
        timing_precision="bar_aligned",
    )

    timeline = planner.plan(
        choreography_plan=implementation,
        beat_grid=beat_grid,
        template_library=template_library,
        total_duration_ms=8000.0,
    )

    # Transitions come from template, not agent
    segment = timeline.segments[0]
    assert segment.entry_transition is not None
    assert segment.exit_transition is not None


def test_plan_end_of_song_gap():
    """Test planning adds end-of-song gap if needed."""
    planner = TemplateTimelinePlanner()
    beat_grid = _create_test_beat_grid()
    template_library = _create_test_template_library()

    # Section ends at bar 3 (6000ms), but total duration is 8000ms (bar 4)
    section = ImplementationSection(
        name="verse_1",
        plan_section_name="verse_1",
        start_bar=1,
        end_bar=3,
        template_id="sweep_lr",
        params={"intensity": "SMOOTH"},
        base_pose="AUDIENCE_CENTER",
        targets=["ALL"],
        layer_priority=0,
    )

    implementation = AgentImplementation(
        sections=[section],
        total_duration_bars=4,
        quantization_applied=True,
        timing_precision="bar_aligned",
    )

    timeline = planner.plan(
        choreography_plan=implementation,
        beat_grid=beat_grid,
        template_library=template_library,
        total_duration_ms=8000.0,
    )

    # Should have section + end-of-song gap
    assert len(timeline.segments) == 2
    assert isinstance(timeline.segments[1], GapSegment)

    gap = timeline.segments[1]
    assert gap.start_ms == 6000.0
    assert gap.end_ms == 8000.0
    assert gap.gap_type == "end_of_song"


def test_plan_multiple_targets():
    """Test planning handles multiple targets correctly."""
    planner = TemplateTimelinePlanner()
    beat_grid = _create_test_beat_grid()
    template_library = _create_test_template_library()

    section = ImplementationSection(
        name="verse_1",
        plan_section_name="verse_1",
        start_bar=1,
        end_bar=4,
        template_id="sweep_lr",
        params={"intensity": "SMOOTH"},
        base_pose="AUDIENCE_CENTER",
        targets=["LEFT", "RIGHT"],  # Multiple targets
        layer_priority=0,
    )

    implementation = AgentImplementation(
        sections=[section],
        total_duration_bars=4,
        quantization_applied=True,
        timing_precision="bar_aligned",
    )

    timeline = planner.plan(
        choreography_plan=implementation,
        beat_grid=beat_grid,
        template_library=template_library,
        total_duration_ms=8000.0,
    )

    # Should create segments for each target
    # For Phase 3, we create one segment per target
    assert len(timeline.segments) >= 1


# ============================================================================
# Helper Functions
# ============================================================================


def _create_test_beat_grid() -> BeatGrid:
    """Create a simple test beat grid."""
    # 4/4 time, 120 BPM = 2000ms per bar
    bar_boundaries = [0.0, 2000.0, 4000.0, 6000.0, 8000.0, 10000.0, 12000.0, 14000.0, 16000.0]
    beat_boundaries = [
        0.0,
        500.0,
        1000.0,
        1500.0,
        2000.0,  # Bar 1
        2500.0,
        3000.0,
        3500.0,
        4000.0,  # Bar 2
        4500.0,
        5000.0,
        5500.0,
        6000.0,  # Bar 3
        6500.0,
        7000.0,
        7500.0,
        8000.0,  # Bar 4
        8500.0,
        9000.0,
        9500.0,
        10000.0,  # Bar 5
    ]

    # Calculate eighth and sixteenth boundaries using BeatGrid helper methods
    eighth_boundaries = BeatGrid._calculate_eighth_boundaries(beat_boundaries)
    sixteenth_boundaries = BeatGrid._calculate_sixteenth_boundaries(beat_boundaries)

    return BeatGrid(
        bar_boundaries=bar_boundaries,
        beat_boundaries=beat_boundaries,
        eighth_boundaries=eighth_boundaries,
        sixteenth_boundaries=sixteenth_boundaries,
        beats_per_bar=4,
        tempo_bpm=120.0,
        duration_ms=16000.0,  # 8 bars * 2000ms/bar
    )


def _create_test_template_library() -> dict[str, Template]:
    """Create a simple test template library."""
    from blinkb0t.core.domains.sequencing.models.templates import (
        PatternStep,
        PatternStepTiming,
        TemplateCategory,
        TemplateTiming,
    )
    from blinkb0t.core.domains.sequencing.models.timing import MusicalTiming, TimingMode

    return {
        "sweep_lr": Template(
            template_id="sweep_lr",
            name="Sweep L/R",
            category=TemplateCategory.MEDIUM_ENERGY,
            timing=TemplateTiming(mode=TimingMode.MUSICAL, default_duration_bars=4.0),
            steps=[
                PatternStep(
                    step_id="sweep_lr_step_0",
                    target="ALL",
                    timing=PatternStepTiming(
                        base_timing=MusicalTiming(
                            mode=TimingMode.MUSICAL,
                            duration_bars=4.0,
                            offset_bars=0.0,
                        )
                    ),
                    movement_id="sweep",
                    dimmer_id="full",
                    movement_params={"intensity": "SMOOTH"},
                    dimmer_params={"base_pct": 100},
                )
            ],
        ),
        "circle": Template(
            template_id="circle",
            name="Circle",
            category=TemplateCategory.HIGH_ENERGY,
            timing=TemplateTiming(mode=TimingMode.MUSICAL, default_duration_bars=4.0),
            steps=[
                PatternStep(
                    step_id="circle_step_0",
                    target="ALL",
                    timing=PatternStepTiming(
                        base_timing=MusicalTiming(
                            mode=TimingMode.MUSICAL,
                            duration_bars=4.0,
                            offset_bars=0.0,
                        )
                    ),
                    movement_id="circle",
                    dimmer_id="full",
                    movement_params={"intensity": "DRAMATIC"},
                    dimmer_params={"base_pct": 100},
                )
            ],
        ),
    }
