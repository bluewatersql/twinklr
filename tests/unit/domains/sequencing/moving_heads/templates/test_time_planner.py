"""
Unit tests for TemplateTimePlanner.

Tests for time budgeting and timeline creation with gaps for transitions.
"""

from unittest.mock import Mock

import pytest

from blinkb0t.core.domains.sequencing.models.templates import (
    PatternStep,
    PatternStepTiming,
    Template,
    TemplateCategory,
    TransitionConfig,
    TransitionMode,
)
from blinkb0t.core.domains.sequencing.models.timing import MusicalTiming
from blinkb0t.core.domains.sequencing.models.transitions import (
    TimelineEffect,
    TimelineGap,
)
from blinkb0t.core.domains.sequencing.moving_heads.templates.planner import (
    TemplateTimePlanner,
)


def create_timing(duration_bars: float) -> PatternStepTiming:
    """Helper to create PatternStepTiming with MusicalTiming."""
    return PatternStepTiming(base_timing=MusicalTiming(duration_bars=duration_bars))


def create_step(
    movement_id: str,
    duration_bars: float,
    step_id: str = "test_step",
    entry_transition: TransitionConfig | None = None,
    exit_transition: TransitionConfig | None = None,
) -> PatternStep:
    """Helper to create PatternStep with minimal required fields."""
    return PatternStep(
        step_id=step_id,
        movement_id=movement_id,
        dimmer_id="default_dimmer",
        timing=create_timing(duration_bars),
        entry_transition=entry_transition or TransitionConfig(mode=TransitionMode.SNAP),
        exit_transition=exit_transition or TransitionConfig(mode=TransitionMode.SNAP),
    )


def create_template(template_id: str, steps: list[PatternStep]) -> Template:
    """Helper to create Template with minimal required fields."""
    return Template(
        template_id=template_id,
        name=f"{template_id}_name",
        category=TemplateCategory.MEDIUM_ENERGY,
        steps=steps,
    )


class TestTemplateTimePlanner:
    """Test TemplateTimePlanner time budgeting and gap creation."""

    @pytest.fixture
    def song_features(self) -> dict:
        """Create mock song features."""
        return {
            "tempo_bpm": 120.0,  # 120 BPM = 0.5s per beat, 2s per bar (4/4)
            "time_signature": {"time_signature": "4/4", "confidence": 0.9},
        }

    @pytest.fixture
    def planner(self, song_features) -> TemplateTimePlanner:
        """Create TemplateTimePlanner instance."""
        return TemplateTimePlanner(song_features)

    def test_ms_per_bar_calculation(self, planner):
        """Test milliseconds per bar calculation from tempo."""
        # 120 BPM = 120 beats/minute = 2 beats/second
        # 4/4 time = 4 beats per bar
        # 1 bar = 4 beats / 2 beats/second = 2 seconds = 2000ms
        assert planner.ms_per_bar == 2000.0

    def test_plan_template_with_no_transitions(self, planner, song_features):
        """Test planning template with no transitions (simple case)."""
        # Create simple template with one step, no transitions
        step = create_step(
            movement_id="sweep_lr",
            duration_bars=4.0,
        )
        template = create_template(template_id="test", steps=[step])

        # Mock _process_step to return a mock effect
        planner._process_step = Mock(
            return_value=Mock(
                start_ms=1000.0,
                end_ms=9000.0,
                pan_center=0.0,
                tilt_center=45.0,
            )
        )
        planner._calculate_end_position = Mock(return_value=(45.0, 60.0))

        timeline = planner.plan_template(
            template=template,
            section_start_ms=1000.0,
            section_duration_ms=8000.0,  # 4 bars at 120 BPM
            fixture_id="MH1",
        )

        # Should have 1 effect, no gaps
        effects = [item for item in timeline if isinstance(item, TimelineEffect)]
        gaps = [item for item in timeline if isinstance(item, TimelineGap)]

        assert len(effects) == 1
        assert len(gaps) == 0

    def test_plan_template_with_entry_transition(self, planner):
        """Test planning template with entry transition creates gap."""
        # Step with entry transition
        step = create_step(
            movement_id="sweep_lr",
            duration_bars=3.0,
            entry_transition=TransitionConfig(mode=TransitionMode.CROSSFADE, duration_bars=0.5),
        )
        template = create_template(template_id="test", steps=[step])

        planner._process_step = Mock(
            return_value=Mock(
                start_ms=2000.0,
                end_ms=8000.0,
                pan_center=0.0,
                tilt_center=45.0,
            )
        )
        planner._calculate_end_position = Mock(return_value=(45.0, 60.0))

        timeline = planner.plan_template(
            template=template,
            section_start_ms=1000.0,
            section_duration_ms=8000.0,
            fixture_id="MH1",
        )

        # Should have 1 gap (entry), 1 effect
        gaps = [item for item in timeline if isinstance(item, TimelineGap)]
        effects = [item for item in timeline if isinstance(item, TimelineEffect)]

        assert len(gaps) == 1
        assert len(effects) == 1

        # Gap should be at start
        gap = gaps[0]
        assert gap.start_ms == 1000.0
        assert gap.transition_in_config is not None
        assert gap.transition_in_config.mode == TransitionMode.CROSSFADE

    def test_plan_template_with_exit_transition(self, planner):
        """Test planning template with exit transition creates gap."""
        step = create_step(
            movement_id="sweep_lr",
            duration_bars=3.0,
            exit_transition=TransitionConfig(
                mode=TransitionMode.FADE_THROUGH_BLACK, duration_bars=0.5
            ),
        )
        template = create_template(template_id="test", steps=[step])

        planner._process_step = Mock(
            return_value=Mock(
                start_ms=1000.0,
                end_ms=7000.0,
                pan_center=0.0,
                tilt_center=45.0,
            )
        )
        planner._calculate_end_position = Mock(return_value=(45.0, 60.0))

        timeline = planner.plan_template(
            template=template,
            section_start_ms=1000.0,
            section_duration_ms=8000.0,
            fixture_id="MH1",
        )

        # Should have 1 effect, 1 gap (exit)
        gaps = [item for item in timeline if isinstance(item, TimelineGap)]
        effects = [item for item in timeline if isinstance(item, TimelineEffect)]

        assert len(gaps) == 1
        assert len(effects) == 1

        # Gap should be after effect
        gap = gaps[0]
        assert gap.start_ms >= effects[0].end_ms  # Gap starts where effect ends
        assert gap.transition_out_config is not None
        assert gap.transition_out_config.mode == TransitionMode.FADE_THROUGH_BLACK

    def test_adjacent_gaps_collapsed(self, planner):
        """Test adjacent exit + entry transitions are collapsed into single gap."""
        # Two steps with exit and entry transitions
        step1 = create_step(
            movement_id="sweep_lr",
            duration_bars=2.0,
            step_id="step1",
            exit_transition=TransitionConfig(mode=TransitionMode.CROSSFADE, duration_bars=0.25),
        )
        step2 = create_step(
            movement_id="circle",
            duration_bars=2.0,
            step_id="step2",
            entry_transition=TransitionConfig(mode=TransitionMode.CROSSFADE, duration_bars=0.25),
        )
        template = create_template(template_id="test", steps=[step1, step2])

        planner._process_step = Mock(
            side_effect=[
                Mock(start_ms=1000.0, end_ms=4000.0, pan_center=0.0, tilt_center=45.0),
                Mock(start_ms=5000.0, end_ms=8000.0, pan_center=45.0, tilt_center=60.0),
            ]
        )
        planner._calculate_end_position = Mock(
            side_effect=[
                (45.0, 60.0),
                (90.0, 75.0),
            ]
        )

        timeline = planner.plan_template(
            template=template,
            section_start_ms=1000.0,
            section_duration_ms=8000.0,
            fixture_id="MH1",
        )

        # Should have 2 effects, 1 collapsed gap
        gaps = [item for item in timeline if isinstance(item, TimelineGap)]
        effects = [item for item in timeline if isinstance(item, TimelineEffect)]

        assert len(effects) == 2
        assert len(gaps) == 1

        # Gap should have both configs
        gap = gaps[0]
        assert gap.transition_out_config is not None
        assert gap.transition_in_config is not None
        assert gap.transition_out_config.mode == TransitionMode.CROSSFADE
        assert gap.transition_in_config.mode == TransitionMode.CROSSFADE

    def test_zero_duration_transition_no_gap(self, planner):
        """Test zero-duration transition (snap) does not create gap."""
        step = create_step(
            movement_id="sweep_lr",
            duration_bars=4.0,
            entry_transition=TransitionConfig(mode=TransitionMode.SNAP, duration_bars=0.0),
        )
        template = create_template(template_id="test", steps=[step])

        planner._process_step = Mock(
            return_value=Mock(
                start_ms=1000.0,
                end_ms=9000.0,
                pan_center=0.0,
                tilt_center=45.0,
            )
        )
        planner._calculate_end_position = Mock(return_value=(45.0, 60.0))

        timeline = planner.plan_template(
            template=template,
            section_start_ms=1000.0,
            section_duration_ms=8000.0,
            fixture_id="MH1",
        )

        # Should have 1 effect, no gaps (duration=0)
        gaps = [item for item in timeline if isinstance(item, TimelineGap)]
        assert len(gaps) == 0

    def test_transition_budget_calculation(self, planner):
        """Test transition budget is correctly calculated and subtracted."""
        # Step with both transitions
        step = create_step(
            movement_id="sweep_lr",
            duration_bars=3.0,
            entry_transition=TransitionConfig(
                mode=TransitionMode.CROSSFADE,
                duration_bars=0.5,  # 1000ms
            ),
            exit_transition=TransitionConfig(
                mode=TransitionMode.FADE_THROUGH_BLACK,
                duration_bars=0.5,  # 1000ms
            ),
        )
        template = create_template(template_id="test", steps=[step])

        planner._process_step = Mock(
            return_value=Mock(
                start_ms=2000.0,
                end_ms=7000.0,
                pan_center=0.0,
                tilt_center=45.0,
            )
        )
        planner._calculate_end_position = Mock(return_value=(45.0, 60.0))

        timeline = planner.plan_template(
            template=template,
            section_start_ms=1000.0,
            section_duration_ms=8000.0,  # Total time
            fixture_id="MH1",
        )

        # Total: 8000ms
        # Transitions: 1000ms + 1000ms = 2000ms
        # Effect: 8000 - 2000 = 6000ms
        gaps = [item for item in timeline if isinstance(item, TimelineGap)]
        effects = [item for item in timeline if isinstance(item, TimelineEffect)]

        total_gap_time = sum(gap.duration_ms for gap in gaps)
        total_effect_time = sum(effect.end_ms - effect.start_ms for effect in effects)

        # Transitions should be ~2000ms, effects should be ~6000ms
        assert abs(total_gap_time - 2000.0) < 100  # Some tolerance
        assert abs(total_effect_time - 6000.0) < 100

    def test_time_scaling_for_multiple_steps(self, planner):
        """Test effect durations are scaled proportionally."""
        # Two steps with equal durations
        step1 = create_step(
            movement_id="sweep_lr",
            duration_bars=2.0,
            step_id="step1",
        )
        step2 = create_step(
            movement_id="circle",
            duration_bars=2.0,
            step_id="step2",
        )
        template = create_template(template_id="test", steps=[step1, step2])

        planner._process_step = Mock(
            side_effect=[
                Mock(start_ms=1000.0, end_ms=5000.0, pan_center=0.0, tilt_center=45.0),
                Mock(start_ms=5000.0, end_ms=9000.0, pan_center=45.0, tilt_center=60.0),
            ]
        )
        planner._calculate_end_position = Mock(
            side_effect=[
                (45.0, 60.0),
                (90.0, 75.0),
            ]
        )

        timeline = planner.plan_template(
            template=template,
            section_start_ms=1000.0,
            section_duration_ms=8000.0,
            fixture_id="MH1",
        )

        effects = [item for item in timeline if isinstance(item, TimelineEffect)]

        # Both steps should get equal time (4000ms each)
        duration1 = effects[0].end_ms - effects[0].start_ms
        duration2 = effects[1].end_ms - effects[1].start_ms

        assert abs(duration1 - duration2) < 100  # Should be roughly equal

    def test_timeline_ordering(self, planner):
        """Test timeline items are in correct temporal order."""
        step1 = create_step(
            movement_id="sweep_lr",
            duration_bars=2.0,
            step_id="step1",
            entry_transition=TransitionConfig(mode=TransitionMode.CROSSFADE, duration_bars=0.25),
            exit_transition=TransitionConfig(mode=TransitionMode.CROSSFADE, duration_bars=0.25),
        )
        step2 = create_step(
            movement_id="circle",
            duration_bars=2.0,
            step_id="step2",
            entry_transition=TransitionConfig(mode=TransitionMode.CROSSFADE, duration_bars=0.25),
        )
        template = create_template(template_id="test", steps=[step1, step2])

        planner._process_step = Mock(
            side_effect=[
                Mock(start_ms=1500.0, end_ms=4500.0, pan_center=0.0, tilt_center=45.0),
                Mock(start_ms=5500.0, end_ms=8500.0, pan_center=45.0, tilt_center=60.0),
            ]
        )
        planner._calculate_end_position = Mock(
            side_effect=[
                (45.0, 60.0),
                (90.0, 75.0),
            ]
        )

        timeline = planner.plan_template(
            template=template,
            section_start_ms=1000.0,
            section_duration_ms=8000.0,
            fixture_id="MH1",
        )

        # Verify temporal ordering
        for i in range(len(timeline) - 1):
            current = timeline[i]
            next_item = timeline[i + 1]
            # Each item should start at or after the previous ends
            assert next_item.start_ms >= current.end_ms - 1.0  # Allow 1ms tolerance

    def test_anchor_extraction_for_gaps(self, planner):
        """Test gaps correctly extract anchor positions from adjacent effects."""
        step1 = create_step(
            movement_id="sweep_lr",
            duration_bars=2.0,
            exit_transition=TransitionConfig(mode=TransitionMode.CROSSFADE, duration_bars=0.5),
        )
        template = create_template(template_id="test", steps=[step1])

        timeline = planner.plan_template(
            template=template,
            section_start_ms=1000.0,
            section_duration_ms=6000.0,
            fixture_id="MH1",
        )

        gaps = [item for item in timeline if isinstance(item, TimelineGap)]

        # Gap should have from_position from effect end
        assert len(gaps) == 1
        gap = gaps[0]
        # With the new implementation, placeholder anchors are used
        # from_position should be set from the effect that precedes the gap
        assert gap.from_position == (0.0, 45.0)  # From placeholder effect end

    def test_single_step_template(self, planner):
        """Test planning template with single step."""
        step = create_step(
            movement_id="hold",
            duration_bars=4.0,
        )
        template = create_template(template_id="test", steps=[step])

        timeline = planner.plan_template(
            template=template,
            section_start_ms=1000.0,
            section_duration_ms=8000.0,
            fixture_id="MH1",
        )

        # Single step, no transitions
        assert len(timeline) == 1
        assert isinstance(timeline[0], TimelineEffect)

    def test_multi_step_template(self, planner):
        """Test planning template with multiple steps."""
        steps = [
            create_step(
                movement_id=f"movement{i}",
                duration_bars=1.0,
                step_id=f"step{i}",
            )
            for i in range(4)
        ]
        template = create_template(template_id="test", steps=steps)

        timeline = planner.plan_template(
            template=template,
            section_start_ms=1000.0,
            section_duration_ms=8000.0,
            fixture_id="MH1",
        )

        effects = [item for item in timeline if isinstance(item, TimelineEffect)]
        assert len(effects) == 4
