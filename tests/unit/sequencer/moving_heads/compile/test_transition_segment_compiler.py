"""Unit tests for transition segment compiler."""

import pytest

from twinklr.core.curves.generator import CurveGenerator
from twinklr.core.sequencer.models.enum import ChannelName, TransitionMode
from twinklr.core.sequencer.models.transition import (
    Boundary,
    BoundaryType,
    TransitionHint,
    TransitionPlan,
    TransitionStrategy,
)
from twinklr.core.sequencer.moving_heads.channels.state import ChannelValue, FixtureSegment
from twinklr.core.sequencer.moving_heads.compile.channel_blender import ChannelBlender
from twinklr.core.sequencer.moving_heads.compile.transition_segment_compiler import (
    TransitionSegmentCompiler,
)


@pytest.fixture
def curve_generator():
    """Create curve generator."""
    return CurveGenerator()


@pytest.fixture
def blender(curve_generator):
    """Create channel blender."""
    return ChannelBlender(curve_generator)


@pytest.fixture
def compiler(blender):
    """Create transition segment compiler."""
    return TransitionSegmentCompiler(blender)


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
        transition_id="verse_to_chorus",
        boundary=boundary,
        hint=hint,
        overlap_start_ms=39000,
        overlap_end_ms=41000,
        overlap_duration_ms=2000,
        channel_strategies={
            ChannelName.PAN: TransitionStrategy.SMOOTH_INTERPOLATION,
            ChannelName.TILT: TransitionStrategy.SMOOTH_INTERPOLATION,
            ChannelName.DIMMER: TransitionStrategy.CROSSFADE,
        },
        fixtures=["fixture_1", "fixture_2"],
    )


@pytest.fixture
def source_segments():
    """Create source fixture segments."""
    return [
        FixtureSegment(
            section_id="verse",
            segment_id="verse_seg_1",
            step_id="step_1",
            template_id="template_verse",
            fixture_id="fixture_1",
            t0_ms=30000,
            t1_ms=40000,
            channels={
                ChannelName.PAN: ChannelValue(channel=ChannelName.PAN, static_dmx=100),
                ChannelName.TILT: ChannelValue(channel=ChannelName.TILT, static_dmx=150),
                ChannelName.DIMMER: ChannelValue(channel=ChannelName.DIMMER, static_dmx=255),
            },
        ),
        FixtureSegment(
            section_id="verse",
            segment_id="verse_seg_2",
            step_id="step_1",
            template_id="template_verse",
            fixture_id="fixture_2",
            t0_ms=30000,
            t1_ms=40000,
            channels={
                ChannelName.PAN: ChannelValue(channel=ChannelName.PAN, static_dmx=120),
                ChannelName.TILT: ChannelValue(channel=ChannelName.TILT, static_dmx=180),
                ChannelName.DIMMER: ChannelValue(channel=ChannelName.DIMMER, static_dmx=200),
            },
        ),
    ]


@pytest.fixture
def target_segments():
    """Create target fixture segments."""
    return [
        FixtureSegment(
            section_id="chorus",
            segment_id="chorus_seg_1",
            step_id="step_1",
            template_id="template_chorus",
            fixture_id="fixture_1",
            t0_ms=40000,
            t1_ms=50000,
            channels={
                ChannelName.PAN: ChannelValue(channel=ChannelName.PAN, static_dmx=200),
                ChannelName.TILT: ChannelValue(channel=ChannelName.TILT, static_dmx=100),
                ChannelName.DIMMER: ChannelValue(channel=ChannelName.DIMMER, static_dmx=255),
            },
        ),
        FixtureSegment(
            section_id="chorus",
            segment_id="chorus_seg_2",
            step_id="step_1",
            template_id="template_chorus",
            fixture_id="fixture_2",
            t0_ms=40000,
            t1_ms=50000,
            channels={
                ChannelName.PAN: ChannelValue(channel=ChannelName.PAN, static_dmx=180),
                ChannelName.TILT: ChannelValue(channel=ChannelName.TILT, static_dmx=120),
                ChannelName.DIMMER: ChannelValue(channel=ChannelName.DIMMER, static_dmx=230),
            },
        ),
    ]


class TestTransitionSegmentCompilerBasic:
    """Test basic transition compilation."""

    def test_transition_segment_timing(
        self, compiler, transition_plan, source_segments, target_segments
    ):
        """Test that transition segments have correct timing."""
        result = compiler.compile_transition(transition_plan, source_segments, target_segments)

        for segment in result:
            assert segment.t0_ms == transition_plan.overlap_start_ms  # 39000
            assert segment.t1_ms == transition_plan.overlap_end_ms  # 41000

    def test_transition_segment_metadata(
        self, compiler, transition_plan, source_segments, target_segments
    ):
        """Test that transition segments have correct metadata."""
        result = compiler.compile_transition(transition_plan, source_segments, target_segments)

        for segment in result:
            assert segment.metadata["is_transition"] == "true"
            assert segment.metadata["transition_id"] == "verse_to_chorus"
            assert segment.metadata["boundary_type"] == "section"
            assert segment.metadata["source_id"] == "verse"
            assert segment.metadata["target_id"] == "chorus"
            assert segment.metadata["transition_mode"] == "crossfade"

    def test_transition_segment_no_grouping(
        self, compiler, transition_plan, source_segments, target_segments
    ):
        """Test that transition segments have allow_grouping=False."""
        result = compiler.compile_transition(transition_plan, source_segments, target_segments)

        for segment in result:
            assert segment.allow_grouping is False


class TestTransitionSegmentCompilerChannelBlending:
    """Test channel blending in transition segments."""

    def test_transition_has_blended_channels(
        self, compiler, transition_plan, source_segments, target_segments
    ):
        """Test that transition segments contain blended channels."""
        result = compiler.compile_transition(transition_plan, source_segments, target_segments)

        fixture_1_seg = next(seg for seg in result if seg.fixture_id == "fixture_1")

        # Should have all three channels
        assert ChannelName.PAN in fixture_1_seg.channels
        assert ChannelName.TILT in fixture_1_seg.channels
        assert ChannelName.DIMMER in fixture_1_seg.channels

    def test_blended_channels_are_curves(
        self, compiler, transition_plan, source_segments, target_segments
    ):
        """Test that blended channels are curve-based (not static)."""
        result = compiler.compile_transition(transition_plan, source_segments, target_segments)

        fixture_1_seg = next(seg for seg in result if seg.fixture_id == "fixture_1")

        # All channels should be curves (not static)
        for channel_value in fixture_1_seg.channels.values():
            assert channel_value.curve is not None
            assert channel_value.static_dmx is None

    def test_curve_has_multiple_points(
        self, compiler, transition_plan, source_segments, target_segments
    ):
        """Test that blended curves have multiple points."""
        result = compiler.compile_transition(transition_plan, source_segments, target_segments)

        fixture_1_seg = next(seg for seg in result if seg.fixture_id == "fixture_1")

        # Check that curves have multiple points
        for channel_value in fixture_1_seg.channels.values():
            assert len(channel_value.curve.points) >= 2
            # First and last points should span t=[0, 1]
            assert channel_value.curve.points[0].t == 0.0
            assert channel_value.curve.points[-1].t == 1.0

    def test_per_fixture_blending(
        self, compiler, transition_plan, source_segments, target_segments
    ):
        """Test that each fixture gets its own blended values."""
        result = compiler.compile_transition(transition_plan, source_segments, target_segments)

        fixture_1_seg = next(seg for seg in result if seg.fixture_id == "fixture_1")
        fixture_2_seg = next(seg for seg in result if seg.fixture_id == "fixture_2")

        # Fixtures should have different channel values
        # (because source and target states are different)
        f1_pan_start = fixture_1_seg.channels[ChannelName.PAN].curve.points[0].v
        f2_pan_start = fixture_2_seg.channels[ChannelName.PAN].curve.points[0].v

        assert f1_pan_start != f2_pan_start


class TestTransitionSegmentCompilerEdgeCases:
    """Test edge cases in transition compilation."""

    def test_missing_source_segment(self, compiler, transition_plan, target_segments):
        """Test handling of missing source segment."""
        # Only one fixture in source, two in target
        source_segments = [
            FixtureSegment(
                section_id="verse",
                segment_id="verse_seg_1",
                step_id="step_1",
                template_id="template_verse",
                fixture_id="fixture_1",
                t0_ms=30000,
                t1_ms=40000,
                channels={
                    ChannelName.DIMMER: ChannelValue(channel=ChannelName.DIMMER, static_dmx=255)
                },
            )
        ]

        result = compiler.compile_transition(transition_plan, source_segments, target_segments)

        # Should still create segments for both fixtures
        assert len(result) == 2

        # Fixture 2 should have a transition segment (source defaults to 0)
        fixture_2_seg = next(seg for seg in result if seg.fixture_id == "fixture_2")
        assert fixture_2_seg is not None

    def test_missing_target_segment(self, compiler, transition_plan, source_segments):
        """Test handling of missing target segment."""
        # Two fixtures in source, only one in target
        target_segments = [
            FixtureSegment(
                section_id="chorus",
                segment_id="chorus_seg_1",
                step_id="step_1",
                template_id="template_chorus",
                fixture_id="fixture_1",
                t0_ms=40000,
                t1_ms=50000,
                channels={
                    ChannelName.DIMMER: ChannelValue(channel=ChannelName.DIMMER, static_dmx=200)
                },
            )
        ]

        result = compiler.compile_transition(transition_plan, source_segments, target_segments)

        # Should still create segments for both fixtures
        assert len(result) == 2

        # Fixture 2 should have a transition segment (target defaults to 0)
        fixture_2_seg = next(seg for seg in result if seg.fixture_id == "fixture_2")
        assert fixture_2_seg is not None

    def test_different_channels_in_source_and_target(self, compiler, transition_plan):
        """Test blending when source and target have different channels."""
        source_segments = [
            FixtureSegment(
                section_id="verse",
                segment_id="verse_seg_1",
                step_id="step_1",
                template_id="template_verse",
                fixture_id="fixture_1",
                t0_ms=30000,
                t1_ms=40000,
                channels={
                    ChannelName.PAN: ChannelValue(channel=ChannelName.PAN, static_dmx=100),
                    # No TILT or DIMMER
                },
            )
        ]

        target_segments = [
            FixtureSegment(
                section_id="chorus",
                segment_id="chorus_seg_1",
                step_id="step_1",
                template_id="template_chorus",
                fixture_id="fixture_1",
                t0_ms=40000,
                t1_ms=50000,
                channels={
                    ChannelName.TILT: ChannelValue(channel=ChannelName.TILT, static_dmx=150),
                    ChannelName.DIMMER: ChannelValue(channel=ChannelName.DIMMER, static_dmx=200),
                    # No PAN
                },
            )
        ]

        result = compiler.compile_transition(transition_plan, source_segments, target_segments)

        fixture_1_seg = result[0]

        # Should have all three channels (union of source and target)
        assert ChannelName.PAN in fixture_1_seg.channels
        assert ChannelName.TILT in fixture_1_seg.channels
        assert ChannelName.DIMMER in fixture_1_seg.channels


class TestTransitionSegmentCompilerIntegration:
    """Integration tests with realistic scenarios."""

    def test_full_crossfade_transition(
        self, compiler, transition_plan, source_segments, target_segments
    ):
        """Test complete crossfade transition with multiple fixtures."""
        result = compiler.compile_transition(transition_plan, source_segments, target_segments)

        # Basic checks
        assert len(result) == 2
        assert all(seg.t0_ms == 39000 for seg in result)
        assert all(seg.t1_ms == 41000 for seg in result)
        assert all(seg.metadata["is_transition"] == "true" for seg in result)

        # Check that channels are blended
        for segment in result:
            for channel_value in segment.channels.values():
                # Should have curves, not static values
                assert channel_value.curve is not None
                # Curves should have multiple points
                assert len(channel_value.curve.points) >= 10

    def test_snap_transition(self, compiler, source_segments, target_segments):
        """Test SNAP transition (instant change)."""
        boundary = Boundary(
            type=BoundaryType.SECTION_BOUNDARY,
            source_id="verse",
            target_id="chorus",
            time_ms=40000,
            bar_position=21.0,
        )

        hint = TransitionHint(mode=TransitionMode.SNAP, duration_bars=0.0)

        snap_plan = TransitionPlan(
            transition_id="verse_to_chorus_snap",
            boundary=boundary,
            hint=hint,
            overlap_start_ms=40000,
            overlap_end_ms=40000,
            overlap_duration_ms=0,
            channel_strategies={
                ChannelName.PAN: TransitionStrategy.SNAP,
                ChannelName.TILT: TransitionStrategy.SNAP,
                ChannelName.DIMMER: TransitionStrategy.SNAP,
            },
            fixtures=["fixture_1"],
        )

        result = compiler.compile_transition(snap_plan, source_segments, target_segments)

        # SNAP should still create a segment (even if 0 duration)
        assert len(result) == 1
        assert result[0].t0_ms == result[0].t1_ms  # 0 duration
