"""Unit tests for transition planner."""

import pytest

from twinklr.core.config.models import TransitionConfig
from twinklr.core.sequencer.models.enum import ChannelName, TransitionMode
from twinklr.core.sequencer.models.transition import (
    Boundary,
    BoundaryType,
    TransitionHint,
    TransitionStrategy,
)
from twinklr.core.sequencer.moving_heads.compile.transition_planner import TransitionPlanner
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
def config():
    """Create default transition config."""
    return TransitionConfig()


@pytest.fixture
def planner(config, beat_grid):
    """Create transition planner."""
    return TransitionPlanner(config, beat_grid)


@pytest.fixture
def boundary():
    """Create a test boundary."""
    return Boundary(
        type=BoundaryType.SECTION_BOUNDARY,
        source_id="verse_1",
        target_id="chorus_1",
        time_ms=40000,  # Bar 21 at 120 BPM
        bar_position=21.0,
    )


class TestTransitionPlannerBasic:
    """Test basic transition planner functionality."""

    def test_plan_snap_transition(self, planner, boundary):
        """Test planning a SNAP transition (instant)."""
        hint = TransitionHint(mode=TransitionMode.SNAP, duration_bars=0.0)

        plan = planner.plan_transition(
            boundary=boundary,
            hint=hint,
            fixtures=["fixture_1", "fixture_2"],
        )

        assert plan.boundary == boundary
        assert plan.hint == hint
        assert plan.overlap_start_ms == 40000
        assert plan.overlap_end_ms == 40000
        assert plan.overlap_duration_ms == 0
        assert plan.fixtures == ["fixture_1", "fixture_2"]

        # All channels should be SNAP strategy
        assert all(
            strategy == TransitionStrategy.SNAP for strategy in plan.channel_strategies.values()
        )

    def test_plan_crossfade_transition(self, planner, boundary):
        """Test planning a CROSSFADE transition."""
        hint = TransitionHint(
            mode=TransitionMode.CROSSFADE,
            duration_bars=1.0,  # 2000ms at 120 BPM
            fade_out_ratio=0.5,
        )

        plan = planner.plan_transition(
            boundary=boundary,
            hint=hint,
            fixtures=["fixture_1"],
        )

        # Crossfade with 0.5 ratio: 1000ms before, 1000ms after boundary
        assert plan.overlap_start_ms == 39000  # 40000 - 1000
        assert plan.overlap_end_ms == 41000  # 40000 + 1000
        assert plan.overlap_duration_ms == 2000

    def test_plan_asymmetric_crossfade(self, planner, boundary):
        """Test planning a CROSSFADE with asymmetric fade_out_ratio."""
        hint = TransitionHint(
            mode=TransitionMode.CROSSFADE,
            duration_bars=1.0,  # 2000ms
            fade_out_ratio=0.7,  # 70% fade out, 30% fade in
        )

        plan = planner.plan_transition(
            boundary=boundary,
            hint=hint,
            fixtures=["fixture_1"],
        )

        # 1400ms fade out before boundary, 600ms fade in after
        assert plan.overlap_start_ms == 38600  # 40000 - 1400
        assert plan.overlap_end_ms == 40600  # 40000 + 600
        assert plan.overlap_duration_ms == 2000

    def test_plan_morph_transition(self, planner, boundary):
        """Test planning a MORPH transition (symmetric)."""
        hint = TransitionHint(
            mode=TransitionMode.MORPH,
            duration_bars=2.0,  # 4000ms
        )

        plan = planner.plan_transition(
            boundary=boundary,
            hint=hint,
            fixtures=["fixture_1"],
        )

        # MORPH splits symmetrically: 2000ms before, 2000ms after
        assert plan.overlap_start_ms == 38000  # 40000 - 2000
        assert plan.overlap_end_ms == 42000  # 40000 + 2000
        assert plan.overlap_duration_ms == 4000

    def test_plan_with_default_hint(self, planner, boundary, config):
        """Test planning without explicit hint (uses defaults)."""
        plan = planner.plan_transition(
            boundary=boundary,
            hint=None,
            fixtures=["fixture_1"],
        )

        # Should use config defaults
        assert plan.hint.mode == config.default_mode
        assert plan.hint.duration_bars == config.default_duration_bars
        assert plan.hint.curve == config.default_curve

    def test_plan_generates_transition_id(self, planner, boundary):
        """Test that planner generates transition ID automatically."""
        plan = planner.plan_transition(
            boundary=boundary,
            hint=TransitionHint(),
            fixtures=["fixture_1"],
        )

        assert plan.transition_id == "trans_verse_1_to_chorus_1"

    def test_plan_uses_explicit_transition_id(self, planner, boundary):
        """Test using explicit transition ID."""
        plan = planner.plan_transition(
            boundary=boundary,
            hint=TransitionHint(),
            fixtures=["fixture_1"],
            transition_id="custom_trans_001",
        )

        assert plan.transition_id == "custom_trans_001"


class TestTransitionPlannerOverlapCalculation:
    """Test overlap calculation logic."""

    def test_overlap_at_start_of_song(self, planner):
        """Test overlap calculation when boundary is at start (clamping)."""
        boundary = Boundary(
            type=BoundaryType.SECTION_BOUNDARY,
            source_id="intro",
            target_id="verse",
            time_ms=2000,  # Bar 2
            bar_position=2.0,
        )

        hint = TransitionHint(
            mode=TransitionMode.CROSSFADE,
            duration_bars=2.0,  # Would go to -1000ms
            fade_out_ratio=0.5,
        )

        plan = planner.plan_transition(boundary=boundary, hint=hint, fixtures=["f1"])

        # Should clamp to 0 (not negative)
        # Original: start would be -2000, end would be 4000 (duration 4000)
        # Clamped: start = 0, end = 4000 (fade-in duration preserved)
        assert plan.overlap_start_ms == 0  # Clamped from -2000
        assert plan.overlap_end_ms == 4000  # Fade-in duration (2000ms) preserved from boundary
        assert plan.overlap_duration_ms == 4000

    def test_overlap_long_duration(self, planner, boundary):
        """Test overlap with very long duration."""
        hint = TransitionHint(
            mode=TransitionMode.CROSSFADE,
            duration_bars=4.0,  # 8000ms
            fade_out_ratio=0.5,
        )

        plan = planner.plan_transition(boundary=boundary, hint=hint, fixtures=["f1"])

        # 4000ms before, 4000ms after
        assert plan.overlap_start_ms == 36000
        assert plan.overlap_end_ms == 44000
        assert plan.overlap_duration_ms == 8000

    def test_overlap_fractional_bars(self, planner, boundary):
        """Test overlap with fractional bar duration."""
        hint = TransitionHint(
            mode=TransitionMode.CROSSFADE,
            duration_bars=0.5,  # 1000ms
            fade_out_ratio=0.5,
        )

        plan = planner.plan_transition(boundary=boundary, hint=hint, fixtures=["f1"])

        # 500ms before, 500ms after
        assert plan.overlap_start_ms == 39500
        assert plan.overlap_end_ms == 40500
        assert plan.overlap_duration_ms == 1000


class TestTransitionPlannerChannelStrategies:
    """Test per-channel strategy determination."""

    def test_channel_strategy_overrides(self, planner, boundary):
        """Test that hint overrides take precedence."""
        hint = TransitionHint(
            mode=TransitionMode.CROSSFADE,
            duration_bars=1.0,
            per_channel_overrides={
                "dimmer": TransitionStrategy.FADE_VIA_BLACK,
                "pan": TransitionStrategy.SNAP,
            },
        )

        plan = planner.plan_transition(boundary=boundary, hint=hint, fixtures=["f1"])

        # Overrides should be applied
        assert plan.channel_strategies[ChannelName.DIMMER] == TransitionStrategy.FADE_VIA_BLACK
        assert plan.channel_strategies[ChannelName.PAN] == TransitionStrategy.SNAP
        # Non-overridden should use defaults
        assert plan.channel_strategies[ChannelName.TILT] == TransitionStrategy.SMOOTH_INTERPOLATION

    def test_snap_mode_overrides_all_channels(self, planner, boundary):
        """Test that SNAP mode overrides all channel strategies."""
        hint = TransitionHint(
            mode=TransitionMode.SNAP,
            duration_bars=0.0,
            per_channel_overrides={
                "dimmer": TransitionStrategy.CROSSFADE,  # Should be ignored
            },
        )

        plan = planner.plan_transition(boundary=boundary, hint=hint, fixtures=["f1"])

        # All channels should be SNAP, ignoring overrides
        assert all(
            strategy == TransitionStrategy.SNAP for strategy in plan.channel_strategies.values()
        )


class TestTransitionPlannerValidation:
    """Test transition feasibility validation."""

    def test_validate_feasible_transition(self, planner, boundary):
        """Test validation of a feasible transition."""
        hint = TransitionHint(mode=TransitionMode.CROSSFADE, duration_bars=1.0, fade_out_ratio=0.5)

        plan = planner.plan_transition(boundary=boundary, hint=hint, fixtures=["f1"])

        # Source and target have plenty of duration
        is_valid, warnings = planner.validate_transition_feasibility(
            plan,
            source_duration_ms=20000,  # 10 bars
            target_duration_ms=20000,  # 10 bars
        )

        assert is_valid
        assert len(warnings) == 0

    def test_validate_fade_out_exceeds_source(self, planner, boundary):
        """Test validation when fade-out exceeds source duration."""
        hint = TransitionHint(mode=TransitionMode.CROSSFADE, duration_bars=1.0, fade_out_ratio=0.5)

        plan = planner.plan_transition(boundary=boundary, hint=hint, fixtures=["f1"])

        # Source is too short for fade-out
        is_valid, warnings = planner.validate_transition_feasibility(
            plan,
            source_duration_ms=500,  # Very short
            target_duration_ms=20000,
        )

        assert not is_valid
        assert any("exceeds source duration" in w for w in warnings)

    def test_validate_fade_in_exceeds_target(self, planner, boundary):
        """Test validation when fade-in exceeds target duration."""
        hint = TransitionHint(mode=TransitionMode.CROSSFADE, duration_bars=1.0, fade_out_ratio=0.5)

        plan = planner.plan_transition(boundary=boundary, hint=hint, fixtures=["f1"])

        # Target is too short for fade-in
        is_valid, warnings = planner.validate_transition_feasibility(
            plan,
            source_duration_ms=20000,
            target_duration_ms=500,  # Very short
        )

        assert not is_valid
        assert any("exceeds target duration" in w for w in warnings)

    def test_validate_below_minimum_section_duration(self, planner, boundary, config):
        """Test validation of minimum section duration."""
        hint = TransitionHint(mode=TransitionMode.CROSSFADE, duration_bars=0.5)

        plan = planner.plan_transition(boundary=boundary, hint=hint, fixtures=["f1"])

        # Both sections below minimum (config default is 1.0 bar = 2000ms at 120 BPM)
        is_valid, warnings = planner.validate_transition_feasibility(
            plan,
            source_duration_ms=1000,  # 0.5 bars
            target_duration_ms=1000,  # 0.5 bars
        )

        assert not is_valid
        assert any("below minimum" in w for w in warnings)
        # Should have 2 warnings (source + target)
        assert len([w for w in warnings if "below minimum" in w]) == 2


class TestTransitionPlannerTimingAdjustment:
    """Test section timing adjustment."""

    def test_adjust_timing_for_overlap(self, planner, boundary):
        """Test timing adjustment creates overlap region."""
        hint = TransitionHint(mode=TransitionMode.CROSSFADE, duration_bars=1.0, fade_out_ratio=0.5)

        plan = planner.plan_transition(boundary=boundary, hint=hint, fixtures=["f1"])

        # Original section timing
        source_end_ms = 40000
        target_start_ms = 40000

        # Adjust for overlap
        adjusted_source_end, adjusted_target_start = planner.adjust_section_timing(
            plan, source_end_ms, target_start_ms
        )

        # Both should now start at overlap_start (39000)
        assert adjusted_source_end == 39000
        assert adjusted_target_start == 39000

    def test_adjust_timing_snap_no_change(self, planner, boundary):
        """Test that SNAP transitions don't adjust timing."""
        hint = TransitionHint(mode=TransitionMode.SNAP, duration_bars=0.0)

        plan = planner.plan_transition(boundary=boundary, hint=hint, fixtures=["f1"])

        source_end_ms = 40000
        target_start_ms = 40000

        adjusted_source_end, adjusted_target_start = planner.adjust_section_timing(
            plan, source_end_ms, target_start_ms
        )

        # No adjustment for SNAP
        assert adjusted_source_end == source_end_ms
        assert adjusted_target_start == target_start_ms

    def test_adjust_timing_overlaps_disabled(self, planner, boundary, config):
        """Test that timing adjustment is skipped when overlaps disabled."""
        # Disable overlaps in config
        config.allow_overlaps = False
        planner = TransitionPlanner(config, planner.beat_grid)

        hint = TransitionHint(mode=TransitionMode.CROSSFADE, duration_bars=1.0)

        plan = planner.plan_transition(boundary=boundary, hint=hint, fixtures=["f1"])

        source_end_ms = 40000
        target_start_ms = 40000

        adjusted_source_end, adjusted_target_start = planner.adjust_section_timing(
            plan, source_end_ms, target_start_ms
        )

        # No adjustment when overlaps disabled
        assert adjusted_source_end == source_end_ms
        assert adjusted_target_start == target_start_ms


class TestTransitionPlannerIntegration:
    """Integration tests with multiple transitions."""

    def test_plan_multiple_transitions(self, planner):
        """Test planning multiple transitions in sequence."""
        boundaries = [
            Boundary(
                type=BoundaryType.SECTION_BOUNDARY,
                source_id="intro",
                target_id="verse_1",
                time_ms=16000,
                bar_position=9.0,
            ),
            Boundary(
                type=BoundaryType.SECTION_BOUNDARY,
                source_id="verse_1",
                target_id="chorus_1",
                time_ms=32000,
                bar_position=17.0,
            ),
        ]

        plans = []
        for boundary in boundaries:
            hint = TransitionHint(mode=TransitionMode.CROSSFADE, duration_bars=0.5)
            plan = planner.plan_transition(boundary=boundary, hint=hint, fixtures=["f1"])
            plans.append(plan)

        assert len(plans) == 2
        assert plans[0].transition_id == "trans_intro_to_verse_1"
        assert plans[1].transition_id == "trans_verse_1_to_chorus_1"

        # Each should have correct overlap
        assert plans[0].overlap_duration_ms == 1000
        assert plans[1].overlap_duration_ms == 1000

    def test_plan_with_varying_hints(self, planner, boundary):
        """Test planning with different hint configurations."""
        hints = [
            TransitionHint(mode=TransitionMode.SNAP, duration_bars=0.0),
            TransitionHint(mode=TransitionMode.CROSSFADE, duration_bars=0.5),
            TransitionHint(mode=TransitionMode.MORPH, duration_bars=1.5),
            TransitionHint(
                mode=TransitionMode.FADE_VIA_BLACK,
                duration_bars=1.0,
                per_channel_overrides={"dimmer": TransitionStrategy.FADE_VIA_BLACK},
            ),
        ]

        plans = []
        for hint in hints:
            plan = planner.plan_transition(boundary=boundary, hint=hint, fixtures=["f1"])
            plans.append(plan)

        # SNAP has zero duration
        assert plans[0].overlap_duration_ms == 0

        # CROSSFADE and MORPH have expected durations
        assert plans[1].overlap_duration_ms == 1000
        assert plans[2].overlap_duration_ms == 3000

        # FADE_VIA_BLACK has override
        assert plans[3].channel_strategies[ChannelName.DIMMER] == TransitionStrategy.FADE_VIA_BLACK
