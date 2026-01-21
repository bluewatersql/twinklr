"""
Unit tests for timeline data models.

Tests for TimelineGap, TimelineEffect, and GapType models used in the
two-phase transitions and gap filling system.
"""

from blinkb0t.core.domains.sequencing.infrastructure.xsq import EffectPlacement
from blinkb0t.core.domains.sequencing.models.templates import TransitionConfig, TransitionMode
from blinkb0t.core.domains.sequencing.models.transitions import (
    GapType,
    TimelineEffect,
    TimelineGap,
)


class TestGapType:
    """Test GapType enum."""

    def test_gap_type_values(self):
        """Test all gap type enum values exist."""
        assert GapType.START == "start"
        assert GapType.MID_SEQUENCE == "mid"
        assert GapType.INTER_SECTION == "inter"
        assert GapType.END == "end"


class TestTimelineGap:
    """Test TimelineGap model."""

    def test_create_basic_gap(self):
        """Test creating a basic gap with required fields."""
        gap = TimelineGap(
            start_ms=1000.0,
            end_ms=2000.0,
            gap_type=GapType.MID_SEQUENCE,
            fixture_id="MH1",
        )

        assert gap.start_ms == 1000.0
        assert gap.end_ms == 2000.0
        assert gap.gap_type == GapType.MID_SEQUENCE
        assert gap.fixture_id == "MH1"
        assert gap.transition_out_config is None
        assert gap.transition_in_config is None
        assert gap.from_position is None
        assert gap.to_position is None

    def test_gap_duration_property(self):
        """Test duration_ms property calculation."""
        gap = TimelineGap(
            start_ms=1000.0,
            end_ms=3500.0,
            gap_type=GapType.MID_SEQUENCE,
            fixture_id="MH1",
        )

        assert gap.duration_ms == 2500.0

    def test_has_transition_config_false(self):
        """Test has_transition_config when no configs present."""
        gap = TimelineGap(
            start_ms=1000.0,
            end_ms=2000.0,
            gap_type=GapType.START,
            fixture_id="MH1",
        )

        assert gap.has_transition_config is False

    def test_has_transition_config_with_in(self):
        """Test has_transition_config with transition_in_config."""
        transition = TransitionConfig(mode=TransitionMode.CROSSFADE, duration_bars=0.5)

        gap = TimelineGap(
            start_ms=1000.0,
            end_ms=2000.0,
            gap_type=GapType.MID_SEQUENCE,
            fixture_id="MH1",
            transition_in_config=transition,
        )

        assert gap.has_transition_config is True

    def test_has_transition_config_with_out(self):
        """Test has_transition_config with transition_out_config."""
        transition = TransitionConfig(
            mode=TransitionMode.FADE_THROUGH_BLACK,
            duration_bars=0.25,
        )

        gap = TimelineGap(
            start_ms=1000.0,
            end_ms=2000.0,
            gap_type=GapType.MID_SEQUENCE,
            fixture_id="MH1",
            transition_out_config=transition,
        )

        assert gap.has_transition_config is True

    def test_has_transition_config_with_both(self):
        """Test has_transition_config with both configs."""
        transition_in = TransitionConfig(mode=TransitionMode.CROSSFADE, duration_bars=0.5)
        transition_out = TransitionConfig(mode=TransitionMode.SNAP, duration_bars=0.0)

        gap = TimelineGap(
            start_ms=1000.0,
            end_ms=2000.0,
            gap_type=GapType.MID_SEQUENCE,
            fixture_id="MH1",
            transition_in_config=transition_in,
            transition_out_config=transition_out,
        )

        assert gap.has_transition_config is True

    def test_gap_with_anchor_positions(self):
        """Test gap with from/to anchor positions."""
        gap = TimelineGap(
            start_ms=1000.0,
            end_ms=2000.0,
            gap_type=GapType.MID_SEQUENCE,
            fixture_id="MH1",
            from_position=(45.0, 30.0),
            to_position=(90.0, 60.0),
        )

        assert gap.from_position == (45.0, 30.0)
        assert gap.to_position == (90.0, 60.0)

    def test_sequence_start_gap(self):
        """Test gap representing sequence start."""
        gap = TimelineGap(
            start_ms=0.0,
            end_ms=5000.0,
            gap_type=GapType.START,
            fixture_id="MH1",
            to_position=(0.0, 45.0),  # First effect start
        )

        assert gap.gap_type == GapType.START
        assert gap.start_ms == 0.0
        assert gap.from_position is None  # No previous effect
        assert gap.to_position == (0.0, 45.0)

    def test_sequence_end_gap(self):
        """Test gap representing sequence end."""
        gap = TimelineGap(
            start_ms=175000.0,
            end_ms=180000.0,
            gap_type=GapType.END,
            fixture_id="MH1",
            from_position=(90.0, 60.0),  # Last effect end
        )

        assert gap.gap_type == GapType.END
        assert gap.from_position == (90.0, 60.0)
        assert gap.to_position is None  # Will use soft home

    def test_inter_section_gap(self):
        """Test gap between sections."""
        gap = TimelineGap(
            start_ms=15000.0,
            end_ms=18000.0,
            gap_type=GapType.INTER_SECTION,
            fixture_id="MH1",
            from_position=(45.0, 30.0),
            to_position=(0.0, 0.0),
        )

        assert gap.gap_type == GapType.INTER_SECTION
        assert gap.duration_ms == 3000.0


class TestTimelineEffect:
    """Test TimelineEffect model."""

    def test_create_basic_effect(self):
        """Test creating a basic timeline effect."""
        effect_placement = EffectPlacement(
            element_name="Dmx MH1",
            effect_name="DMX",
            start_ms=1000,
            end_ms=3000,
        )

        timeline_effect = TimelineEffect(
            start_ms=1000.0,
            end_ms=3000.0,
            fixture_id="MH1",
            effect=effect_placement,
            pan_start=0.0,
            pan_end=45.0,
            tilt_start=0.0,
            tilt_end=30.0,
            step_index=0,
            template_id="verse_sweep_pulse",
        )

        assert timeline_effect.start_ms == 1000.0
        assert timeline_effect.end_ms == 3000.0
        assert timeline_effect.fixture_id == "MH1"
        assert timeline_effect.effect == effect_placement
        assert timeline_effect.pan_start == 0.0
        assert timeline_effect.pan_end == 45.0
        assert timeline_effect.tilt_start == 0.0
        assert timeline_effect.tilt_end == 30.0
        assert timeline_effect.step_index == 0
        assert timeline_effect.template_id == "verse_sweep_pulse"

    def test_effect_with_anchor_positions(self):
        """Test effect provides anchor positions for transitions."""
        effect_placement = EffectPlacement(
            element_name="Dmx MH2",
            effect_name="DMX",
            start_ms=5000,
            end_ms=8000,
        )

        timeline_effect = TimelineEffect(
            start_ms=5000.0,
            end_ms=8000.0,
            fixture_id="MH2",
            effect=effect_placement,
            pan_start=90.0,
            pan_end=45.0,  # Calculated from curve
            tilt_start=60.0,
            tilt_end=30.0,  # Calculated from curve
            step_index=1,
            template_id="chorus_circle_strobe",
        )

        # Verify anchors are accessible
        assert timeline_effect.pan_start == 90.0
        assert timeline_effect.pan_end == 45.0
        assert timeline_effect.tilt_start == 60.0
        assert timeline_effect.tilt_end == 30.0

    def test_effect_duration_matches_placement(self):
        """Test effect duration matches EffectPlacement."""
        effect_placement = EffectPlacement(
            element_name="Dmx MH1",
            effect_name="DMX",
            start_ms=1000,
            end_ms=3500,
        )

        timeline_effect = TimelineEffect(
            start_ms=1000.0,
            end_ms=3500.0,
            fixture_id="MH1",
            effect=effect_placement,
            pan_start=0.0,
            pan_end=0.0,
            tilt_start=0.0,
            tilt_end=0.0,
            step_index=0,
            template_id="ambient_hold_pulse",
        )

        effect_duration = effect_placement.end_ms - effect_placement.start_ms
        timeline_duration = timeline_effect.end_ms - timeline_effect.start_ms

        assert effect_duration == timeline_duration == 2500.0


class TestTimelineIntegration:
    """Test Timeline type (list of TimelineEffect | TimelineGap)."""

    def test_timeline_with_mixed_items(self):
        """Test timeline can contain both effects and gaps."""
        effect_placement = EffectPlacement(
            element_name="Dmx MH1",
            effect_name="DMX",
            start_ms=1000,
            end_ms=2000,
        )

        effect = TimelineEffect(
            start_ms=1000.0,
            end_ms=2000.0,
            fixture_id="MH1",
            effect=effect_placement,
            pan_start=0.0,
            pan_end=45.0,
            tilt_start=0.0,
            tilt_end=30.0,
            step_index=0,
            template_id="verse_sweep_pulse",
        )

        gap = TimelineGap(
            start_ms=2000.0,
            end_ms=2500.0,
            gap_type=GapType.MID_SEQUENCE,
            fixture_id="MH1",
            from_position=(45.0, 30.0),
            to_position=(90.0, 60.0),
        )

        timeline = [effect, gap]

        assert len(timeline) == 2
        assert isinstance(timeline[0], TimelineEffect)
        assert isinstance(timeline[1], TimelineGap)

    def test_timeline_sorting_by_time(self):
        """Test timeline items can be sorted by start_ms."""
        effect1_placement = EffectPlacement(
            element_name="Dmx MH1",
            effect_name="DMX",
            start_ms=5000,
            end_ms=6000,
        )

        effect1 = TimelineEffect(
            start_ms=5000.0,
            end_ms=6000.0,
            fixture_id="MH1",
            effect=effect1_placement,
            pan_start=0.0,
            pan_end=0.0,
            tilt_start=0.0,
            tilt_end=0.0,
            step_index=1,
            template_id="test",
        )

        gap = TimelineGap(
            start_ms=1000.0,
            end_ms=2000.0,
            gap_type=GapType.START,
            fixture_id="MH1",
        )

        effect2_placement = EffectPlacement(
            element_name="Dmx MH1",
            effect_name="DMX",
            start_ms=2000,
            end_ms=4000,
        )

        effect2 = TimelineEffect(
            start_ms=2000.0,
            end_ms=4000.0,
            fixture_id="MH1",
            effect=effect2_placement,
            pan_start=0.0,
            pan_end=0.0,
            tilt_start=0.0,
            tilt_end=0.0,
            step_index=0,
            template_id="test",
        )

        # Unsorted timeline
        timeline = [effect1, gap, effect2]

        # Sort by start_ms
        sorted_timeline = sorted(timeline, key=lambda item: item.start_ms)

        assert sorted_timeline[0] == gap  # 1000ms
        assert sorted_timeline[1] == effect2  # 2000ms
        assert sorted_timeline[2] == effect1  # 5000ms
