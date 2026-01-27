"""Unit tests for channel blender."""

import pytest

from blinkb0t.core.curves.generator import CurveGenerator
from blinkb0t.core.sequencer.models.enum import ChannelName, TransitionMode
from blinkb0t.core.sequencer.models.transition import (
    Boundary,
    BoundaryType,
    TransitionHint,
    TransitionPlan,
    TransitionStrategy,
)
from blinkb0t.core.sequencer.moving_heads.compile.channel_blender import ChannelBlender


@pytest.fixture
def curve_generator():
    """Create curve generator."""
    return CurveGenerator()


@pytest.fixture
def blender(curve_generator):
    """Create channel blender."""
    return ChannelBlender(curve_generator)


@pytest.fixture
def transition_plan():
    """Create a test transition plan."""
    boundary = Boundary(
        type=BoundaryType.SECTION_BOUNDARY,
        source_id="verse",
        target_id="chorus",
        time_ms=40000,
        bar_position=21.0,
    )

    hint = TransitionHint(mode=TransitionMode.CROSSFADE, duration_bars=1.0)

    return TransitionPlan(
        transition_id="test_trans",
        boundary=boundary,
        hint=hint,
        overlap_start_ms=39000,
        overlap_end_ms=41000,
        overlap_duration_ms=2000,
        channel_strategies={
            ChannelName.PAN: TransitionStrategy.SMOOTH_INTERPOLATION,
            ChannelName.TILT: TransitionStrategy.SMOOTH_INTERPOLATION,
            ChannelName.DIMMER: TransitionStrategy.CROSSFADE,
            ChannelName.SHUTTER: TransitionStrategy.SEQUENCE,
            ChannelName.COLOR: TransitionStrategy.FADE_VIA_BLACK,
        },
        fixtures=["f1"],
    )


class TestChannelBlenderSnap:
    """Test SNAP blending strategy."""

    def test_snap_before_midpoint(self, blender, transition_plan):
        """Test SNAP returns source value before midpoint."""
        # Override strategy to SNAP
        transition_plan.channel_strategies[ChannelName.PAN] = TransitionStrategy.SNAP

        result = blender.blend_channel(
            ChannelName.PAN,
            source_value=100,
            target_value=200,
            transition_plan=transition_plan,
            time_in_transition=0.4,  # Before 0.5
        )

        assert result == 100  # Should be source value

    def test_snap_at_midpoint(self, blender, transition_plan):
        """Test SNAP changes at midpoint."""
        transition_plan.channel_strategies[ChannelName.PAN] = TransitionStrategy.SNAP

        result = blender.blend_channel(
            ChannelName.PAN,
            source_value=100,
            target_value=200,
            transition_plan=transition_plan,
            time_in_transition=0.5,
        )

        assert result == 200  # Should be target value

    def test_snap_after_midpoint(self, blender, transition_plan):
        """Test SNAP returns target value after midpoint."""
        transition_plan.channel_strategies[ChannelName.PAN] = TransitionStrategy.SNAP

        result = blender.blend_channel(
            ChannelName.PAN,
            source_value=100,
            target_value=200,
            transition_plan=transition_plan,
            time_in_transition=0.8,
        )

        assert result == 200  # Should be target value


class TestChannelBlenderSmooth:
    """Test SMOOTH_INTERPOLATION blending strategy."""

    def test_smooth_start(self, blender, transition_plan):
        """Test smooth interpolation at start."""
        result = blender.blend_channel(
            ChannelName.PAN,
            source_value=0,
            target_value=255,
            transition_plan=transition_plan,
            time_in_transition=0.0,
        )

        assert result == 0  # Should be at source

    def test_smooth_end(self, blender, transition_plan):
        """Test smooth interpolation at end."""
        result = blender.blend_channel(
            ChannelName.PAN,
            source_value=0,
            target_value=255,
            transition_plan=transition_plan,
            time_in_transition=1.0,
        )

        assert result == 255  # Should be at target

    def test_smooth_midpoint(self, blender, transition_plan):
        """Test smooth interpolation at midpoint."""
        result = blender.blend_channel(
            ChannelName.PAN,
            source_value=0,
            target_value=255,
            transition_plan=transition_plan,
            time_in_transition=0.5,
        )

        # Should be roughly in middle (exact value depends on curve)
        assert 100 < result < 155

    def test_smooth_descending(self, blender, transition_plan):
        """Test smooth interpolation with descending values."""
        result = blender.blend_channel(
            ChannelName.PAN,
            source_value=255,
            target_value=0,
            transition_plan=transition_plan,
            time_in_transition=0.5,
        )

        # Should be roughly in middle
        assert 100 < result < 155


class TestChannelBlenderCrossfade:
    """Test CROSSFADE blending strategy."""

    def test_crossfade_start(self, blender, transition_plan):
        """Test crossfade at start (all source)."""
        result = blender.blend_channel(
            ChannelName.DIMMER,
            source_value=255,
            target_value=0,
            transition_plan=transition_plan,
            time_in_transition=0.0,
        )

        assert result == 255  # Should be all source

    def test_crossfade_end(self, blender, transition_plan):
        """Test crossfade at end (all target)."""
        result = blender.blend_channel(
            ChannelName.DIMMER,
            source_value=255,
            target_value=0,
            transition_plan=transition_plan,
            time_in_transition=1.0,
        )

        assert result == 0  # Should be all target

    def test_crossfade_midpoint(self, blender, transition_plan):
        """Test crossfade at midpoint (equal power)."""
        result = blender.blend_channel(
            ChannelName.DIMMER,
            source_value=255,
            target_value=0,
            transition_plan=transition_plan,
            time_in_transition=0.5,
        )

        # Equal-power crossfade: cos(π/4) ≈ 0.707
        # 255 * 0.707 ≈ 180
        assert 175 < result < 185

    def test_crossfade_equal_values(self, blender, transition_plan):
        """Test crossfade with equal source and target."""
        result = blender.blend_channel(
            ChannelName.DIMMER,
            source_value=128,
            target_value=128,
            transition_plan=transition_plan,
            time_in_transition=0.5,
        )

        # Equal-power crossfade: cos(π/4) + sin(π/4) ≈ 1.414
        # 128 * 1.414 ≈ 181
        # This is expected behavior for equal-power crossfade
        assert 175 < result < 185


class TestChannelBlenderFadeViaBlack:
    """Test FADE_VIA_BLACK blending strategy."""

    def test_fade_via_black_start(self, blender, transition_plan):
        """Test fade via black at start."""
        result = blender.blend_channel(
            ChannelName.COLOR,
            source_value=255,
            target_value=128,
            transition_plan=transition_plan,
            time_in_transition=0.0,
        )

        assert result == 255  # Should be at source

    def test_fade_via_black_first_quarter(self, blender, transition_plan):
        """Test fade via black during first quarter (fading out)."""
        result = blender.blend_channel(
            ChannelName.COLOR,
            source_value=255,
            target_value=128,
            transition_plan=transition_plan,
            time_in_transition=0.25,
        )

        # Should be halfway through fade out: 255 * 0.5 = 127.5
        assert 120 < result < 135

    def test_fade_via_black_midpoint(self, blender, transition_plan):
        """Test fade via black at midpoint (should be at zero)."""
        result = blender.blend_channel(
            ChannelName.COLOR,
            source_value=255,
            target_value=128,
            transition_plan=transition_plan,
            time_in_transition=0.5,
        )

        assert result == 0  # Should be at black

    def test_fade_via_black_third_quarter(self, blender, transition_plan):
        """Test fade via black during third quarter (fading in)."""
        result = blender.blend_channel(
            ChannelName.COLOR,
            source_value=255,
            target_value=128,
            transition_plan=transition_plan,
            time_in_transition=0.75,
        )

        # Should be halfway through fade in: 128 * 0.5 = 64
        assert 60 < result < 70

    def test_fade_via_black_end(self, blender, transition_plan):
        """Test fade via black at end."""
        result = blender.blend_channel(
            ChannelName.COLOR,
            source_value=255,
            target_value=128,
            transition_plan=transition_plan,
            time_in_transition=1.0,
        )

        assert result == 128  # Should be at target


class TestChannelBlenderSequence:
    """Test SEQUENCE blending strategy."""

    def test_sequence_start(self, blender, transition_plan):
        """Test sequence at start (closing)."""
        result = blender.blend_channel(
            ChannelName.SHUTTER,
            source_value=255,
            target_value=128,
            transition_plan=transition_plan,
            time_in_transition=0.0,
        )

        assert result == 255  # Should be at source

    def test_sequence_first_phase(self, blender, transition_plan):
        """Test sequence during first phase (closing)."""
        result = blender.blend_channel(
            ChannelName.SHUTTER,
            source_value=255,
            target_value=128,
            transition_plan=transition_plan,
            time_in_transition=0.15,  # Halfway through close phase
        )

        # Should be fading to zero
        assert 100 < result < 140

    def test_sequence_middle_phase(self, blender, transition_plan):
        """Test sequence during middle phase (closed)."""
        result = blender.blend_channel(
            ChannelName.SHUTTER,
            source_value=255,
            target_value=128,
            transition_plan=transition_plan,
            time_in_transition=0.5,
        )

        assert result == 0  # Should be closed

    def test_sequence_third_phase(self, blender, transition_plan):
        """Test sequence during third phase (opening)."""
        result = blender.blend_channel(
            ChannelName.SHUTTER,
            source_value=255,
            target_value=128,
            transition_plan=transition_plan,
            time_in_transition=0.8,
        )

        # Should be fading in toward target
        assert 50 < result < 100

    def test_sequence_end(self, blender, transition_plan):
        """Test sequence at end (opened to target)."""
        result = blender.blend_channel(
            ChannelName.SHUTTER,
            source_value=255,
            target_value=128,
            transition_plan=transition_plan,
            time_in_transition=1.0,
        )

        assert result == 128  # Should be at target


class TestChannelBlenderCurveGeneration:
    """Test full curve generation."""

    def test_blend_channel_curve_snap(self, blender, transition_plan):
        """Test generating full curve with SNAP strategy."""
        transition_plan.channel_strategies[ChannelName.PAN] = TransitionStrategy.SNAP

        source_curve = [100] * 10
        target_curve = [200] * 10

        result = blender.blend_channel_curve(
            ChannelName.PAN,
            source_curve,
            target_curve,
            transition_plan,
            n_samples=10,
        )

        assert len(result) == 10
        # First half should be source, second half target
        assert result[0] == 100
        assert result[4] == 100
        assert result[5] == 200
        assert result[9] == 200

    def test_blend_channel_curve_smooth(self, blender, transition_plan):
        """Test generating full curve with SMOOTH strategy."""
        source_curve = [0] * 10
        target_curve = [255] * 10

        result = blender.blend_channel_curve(
            ChannelName.PAN,
            source_curve,
            target_curve,
            transition_plan,
            n_samples=10,
        )

        assert len(result) == 10
        assert result[0] == 0  # Start at source
        assert result[-1] == 255  # End at target
        # Should be monotonically increasing
        for i in range(len(result) - 1):
            assert result[i] <= result[i + 1]

    def test_blend_channel_curve_mismatched_lengths(self, blender, transition_plan):
        """Test error handling for mismatched curve lengths."""
        source_curve = [100] * 10
        target_curve = [200] * 5  # Wrong length

        with pytest.raises(ValueError, match="must have 10 samples"):
            blender.blend_channel_curve(
                ChannelName.PAN,
                source_curve,
                target_curve,
                transition_plan,
                n_samples=10,
            )


class TestChannelBlenderEdgeCases:
    """Test edge cases and error handling."""

    def test_blend_dmx_clamping_upper(self, blender, transition_plan):
        """Test DMX value clamping at upper bound."""
        result = blender.blend_channel(
            ChannelName.PAN,
            source_value=255,
            target_value=255,
            transition_plan=transition_plan,
            time_in_transition=0.5,
        )

        assert result <= 255  # Should not exceed max

    def test_blend_dmx_clamping_lower(self, blender, transition_plan):
        """Test DMX value clamping at lower bound."""
        result = blender.blend_channel(
            ChannelName.PAN,
            source_value=0,
            target_value=0,
            transition_plan=transition_plan,
            time_in_transition=0.5,
        )

        assert result >= 0  # Should not go negative

    def test_blend_unknown_strategy_fallback(self, blender, transition_plan):
        """Test fallback for unknown strategy."""
        # Clear channel strategies to trigger fallback
        transition_plan.channel_strategies.clear()

        result = blender.blend_channel(
            ChannelName.PAN,
            source_value=0,
            target_value=255,
            transition_plan=transition_plan,
            time_in_transition=0.5,
        )

        # Should fallback to smooth interpolation (somewhere in middle)
        assert 0 < result < 255

    def test_blend_single_sample_curve(self, blender, transition_plan):
        """Test blending with single-sample curve."""
        source_curve = [100]
        target_curve = [200]

        result = blender.blend_channel_curve(
            ChannelName.PAN,
            source_curve,
            target_curve,
            transition_plan,
            n_samples=1,
        )

        assert len(result) == 1
        # With single sample, time=0.0, so should be source value
        assert result[0] == 100


class TestChannelBlenderChannelValueCreation:
    """Test creating ChannelValue objects from blended curves."""

    def test_create_blended_channel_value(self, blender):
        """Test creating ChannelValue from blended curve."""
        blended_curve = [255, 200, 150, 100, 50, 0]

        channel_value = blender.create_blended_channel_value(
            ChannelName.DIMMER,
            blended_curve,
        )

        assert channel_value.channel == ChannelName.DIMMER
        assert channel_value.curve is not None
        assert channel_value.curve.kind == "POINTS"
        assert len(channel_value.curve.points) == 6

        # Check curve points (normalized to 0-1)
        assert channel_value.curve.points[0].t == 0.0
        assert channel_value.curve.points[0].v == 1.0  # 255/255 = 1.0

        assert channel_value.curve.points[-1].t == 1.0
        assert channel_value.curve.points[-1].v == 0.0  # 0/255 = 0.0

    def test_create_channel_value_single_point(self, blender):
        """Test creating ChannelValue with single point (creates 2 identical points)."""
        blended_curve = [128]

        channel_value = blender.create_blended_channel_value(
            ChannelName.PAN,
            blended_curve,
        )

        # Single input creates 2 identical points (PointsCurve requires min 2)
        assert len(channel_value.curve.points) == 2
        assert channel_value.curve.points[0].t == 0.0
        assert channel_value.curve.points[1].t == 1.0
        assert abs(channel_value.curve.points[0].v - 0.5) < 0.01  # 128/255 ≈ 0.5
        assert abs(channel_value.curve.points[1].v - 0.5) < 0.01  # Same value

    def test_create_channel_value_with_clamping(self, blender):
        """Test creating ChannelValue with custom clamping."""
        blended_curve = [50, 100, 150, 200, 250]

        channel_value = blender.create_blended_channel_value(
            ChannelName.DIMMER,
            blended_curve,
            clamp_min=50,
            clamp_max=200,
        )

        assert channel_value.clamp_min == 50
        assert channel_value.clamp_max == 200

        # Normalized values should be relative to clamp range
        # First point: (50-50)/(200-50) = 0.0
        assert channel_value.curve.points[0].v == 0.0
        # Last point: (250-50)/(200-50) clamped to 1.0
        assert channel_value.curve.points[-1].v == 1.0


class TestChannelBlenderIntegration:
    """Integration tests with multiple channels and strategies."""

    def test_blend_multiple_channels(self, blender, transition_plan):
        """Test blending multiple channels with different strategies."""
        # smooth
        pan_result = blender.blend_channel(
            ChannelName.PAN,
            source_value=0,
            target_value=255,
            transition_plan=transition_plan,
            time_in_transition=0.5,
        )

        # crossfade
        dimmer_result = blender.blend_channel(
            ChannelName.DIMMER,
            source_value=255,
            target_value=0,
            transition_plan=transition_plan,
            time_in_transition=0.5,
        )

        # COLOR: fade via black
        color_result = blender.blend_channel(
            ChannelName.COLOR,
            source_value=255,
            target_value=128,
            transition_plan=transition_plan,
            time_in_transition=0.5,
        )

        # All should have valid DMX values
        assert 0 <= pan_result <= 255
        assert 0 <= dimmer_result <= 255
        assert 0 <= color_result <= 255

        # COLOR should be at black (fade via black at midpoint)
        assert color_result == 0

    def test_blend_full_transition_lifecycle(self, blender, transition_plan):
        """Test complete transition from start to end."""
        n_samples = 20
        source_curve = [255] * n_samples
        target_curve = [0] * n_samples

        # Blend dimmer channel (crossfade)
        result = blender.blend_channel_curve(
            ChannelName.DIMMER,
            source_curve,
            target_curve,
            transition_plan,
            n_samples=n_samples,
        )

        # Should start high, end low
        assert result[0] == 255
        assert result[-1] == 0

        # Should be monotonically decreasing (with some tolerance for rounding)
        for i in range(len(result) - 1):
            assert result[i] >= result[i + 1] - 1  # Allow 1 DMX unit tolerance
