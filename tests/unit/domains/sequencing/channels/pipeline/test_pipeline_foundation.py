"""Tests for BoundaryDetector, EffectSplitter, and ChannelStateFiller."""

from __future__ import annotations

from unittest.mock import Mock

import pytest

from blinkb0t.core.config.fixtures import (
    DmxMapping,
    FixtureConfig,
    FixtureInstance,
)
from blinkb0t.core.domains.sequencing.channels.pipeline.boundary_detector import BoundaryDetector
from blinkb0t.core.domains.sequencing.channels.pipeline.channel_state_filler import (
    ChannelStateFiller,
)
from blinkb0t.core.domains.sequencing.channels.pipeline.effect_splitter import (
    EffectSplitter,
    TimeSegment,
)
from blinkb0t.core.domains.sequencing.channels.state import ChannelState
from blinkb0t.core.domains.sequencing.models.channels import SequencedEffect


class TestBoundaryDetector:
    """Test BoundaryDetector."""

    @pytest.fixture
    def detector(self):
        return BoundaryDetector()

    def test_single_effect(self, detector, mock_channel_state):
        """Test boundary detection for single effect."""
        effects = [
            SequencedEffect(
                targets=["ALL"], channels={"pan": mock_channel_state}, start_ms=100, end_ms=500
            )
        ]

        boundaries = detector.detect(effects)

        assert boundaries == [100, 500]

    def test_non_overlapping_effects(self, detector, mock_channel_state):
        """Test boundary detection for non-overlapping effects."""
        effects = [
            SequencedEffect(
                targets=["ALL"], channels={"pan": mock_channel_state}, start_ms=100, end_ms=200
            ),
            SequencedEffect(
                targets=["ALL"], channels={"pan": mock_channel_state}, start_ms=300, end_ms=400
            ),
        ]

        boundaries = detector.detect(effects)

        assert boundaries == [100, 200, 300, 400]

    def test_overlapping_effects(self, detector, mock_channel_state):
        """Test boundary detection for overlapping effects."""
        effects = [
            SequencedEffect(
                targets=["ALL"], channels={"pan": mock_channel_state}, start_ms=100, end_ms=500
            ),
            SequencedEffect(
                targets=["ALL"], channels={"shutter": mock_channel_state}, start_ms=200, end_ms=400
            ),
        ]

        boundaries = detector.detect(effects)

        assert boundaries == [100, 200, 400, 500]

    def test_duplicate_boundaries_removed(self, detector, mock_channel_state):
        """Test that duplicate boundaries are removed."""
        effects = [
            SequencedEffect(
                targets=["ALL"], channels={"pan": mock_channel_state}, start_ms=100, end_ms=300
            ),
            SequencedEffect(
                targets=["ALL"], channels={"tilt": mock_channel_state}, start_ms=100, end_ms=300
            ),
        ]

        boundaries = detector.detect(effects)

        assert boundaries == [100, 300]

    def test_empty_effects(self, detector):
        """Test boundary detection with no effects."""
        boundaries = detector.detect([])

        assert boundaries == []

    def test_many_effects(self, detector, mock_channel_state):
        """Test boundary detection with many effects."""
        effects = [
            SequencedEffect(
                targets=["ALL"],
                channels={"pan": mock_channel_state},
                start_ms=i * 100,
                end_ms=(i + 1) * 100,
            )
            for i in range(10)
        ]

        boundaries = detector.detect(effects)

        assert len(boundaries) == 11  # 0, 100, 200, ..., 1000
        assert boundaries[0] == 0
        assert boundaries[-1] == 1000


class TestEffectSplitter:
    """Test EffectSplitter."""

    @pytest.fixture
    def splitter(self):
        return EffectSplitter()

    def test_single_effect_single_segment(self, splitter, mock_channel_state):
        """Test splitting single effect creates single segment."""
        effects = [
            SequencedEffect(
                targets=["ALL"], channels={"pan": mock_channel_state}, start_ms=100, end_ms=500
            )
        ]
        boundaries = [100, 500]

        segments = splitter.split(effects, boundaries)

        assert len(segments) == 1
        assert segments[0].start_ms == 100
        assert segments[0].end_ms == 500
        assert len(segments[0].effects) == 1

    def test_overlapping_effects_multiple_segments(self, splitter, mock_channel_state):
        """Test overlapping effects create multiple segments."""
        effect1 = SequencedEffect(
            targets=["ALL"], channels={"pan": mock_channel_state}, start_ms=100, end_ms=500
        )
        effect2 = SequencedEffect(
            targets=["ALL"], channels={"shutter": mock_channel_state}, start_ms=200, end_ms=400
        )
        effects = [effect1, effect2]
        boundaries = [100, 200, 400, 500]

        segments = splitter.split(effects, boundaries)

        assert len(segments) == 3
        # Segment 1: 100-200 (only effect1)
        assert segments[0].start_ms == 100
        assert segments[0].end_ms == 200
        assert segments[0].effects == [effect1]
        # Segment 2: 200-400 (both effects)
        assert segments[1].start_ms == 200
        assert segments[1].end_ms == 400
        # Check both effects are in the segment (can't use set comparison due to unhashable list)
        assert len(segments[1].effects) == 2
        assert effect1 in segments[1].effects
        assert effect2 in segments[1].effects
        # Segment 3: 400-500 (only effect1)
        assert segments[2].start_ms == 400
        assert segments[2].end_ms == 500
        assert segments[2].effects == [effect1]

    def test_empty_boundaries(self, splitter, mock_channel_state):
        """Test empty boundaries returns empty segments."""
        effects = [
            SequencedEffect(
                targets=["ALL"], channels={"pan": mock_channel_state}, start_ms=100, end_ms=500
            )
        ]

        segments = splitter.split(effects, [])

        assert segments == []

    def test_single_boundary(self, splitter, mock_channel_state):
        """Test single boundary returns empty segments."""
        effects = [
            SequencedEffect(
                targets=["ALL"], channels={"pan": mock_channel_state}, start_ms=100, end_ms=500
            )
        ]

        segments = splitter.split(effects, [100])

        assert segments == []

    def test_non_overlapping_effects(self, splitter, mock_channel_state):
        """Test non-overlapping effects create separate segments."""
        effect1 = SequencedEffect(
            targets=["ALL"], channels={"pan": mock_channel_state}, start_ms=100, end_ms=200
        )
        effect2 = SequencedEffect(
            targets=["ALL"], channels={"pan": mock_channel_state}, start_ms=300, end_ms=400
        )
        effects = [effect1, effect2]
        boundaries = [100, 200, 300, 400]

        segments = splitter.split(effects, boundaries)

        assert len(segments) == 3
        # Segment 1: 100-200 (effect1)
        assert segments[0].effects == [effect1]
        # Segment 2: 200-300 (gap - no effects)
        assert segments[1].effects == []
        # Segment 3: 300-400 (effect2)
        assert segments[2].effects == [effect2]


class TestChannelStateFiller:
    """Test ChannelStateFiller."""

    @pytest.fixture
    def filler(self):
        return ChannelStateFiller()

    def test_fills_missing_channels(self, filler, mock_fixture, mock_channel_state):
        """Test that missing channels are filled with DMX 0."""
        # Effect with only pan/tilt
        effect = SequencedEffect(
            targets=["ALL"],
            channels={"pan": mock_channel_state, "tilt": mock_channel_state},
            start_ms=100,
            end_ms=200,
        )
        segment = TimeSegment(start_ms=100, end_ms=200, effects=[effect])

        dmx_effects = filler.fill([segment], mock_fixture)

        assert len(dmx_effects) == 1
        dmx_effect = dmx_effects[0]

        # Should have all channels
        assert "pan" in dmx_effect.channels
        assert "tilt" in dmx_effect.channels
        assert "shutter" in dmx_effect.channels  # Filled
        assert "dimmer" in dmx_effect.channels  # Filled
        assert "color" in dmx_effect.channels  # Filled
        assert "gobo" in dmx_effect.channels  # Filled

        # Verify filled channels have DMX 0
        assert dmx_effect.channels["shutter"].get_channel("shutter") == 0
        assert dmx_effect.channels["dimmer"].get_channel("dimmer") == 0
        assert dmx_effect.channels["color"].get_channel("color") == 0
        assert dmx_effect.channels["gobo"].get_channel("gobo") == 0

    def test_skips_gap_segments(self, filler, mock_fixture):
        """Test that segments with no effects are skipped (gaps)."""
        segment = TimeSegment(start_ms=100, end_ms=200, effects=[])

        dmx_effects = filler.fill([segment], mock_fixture)

        assert len(dmx_effects) == 0  # Gap segment skipped

    def test_preserves_existing_channels(self, filler, mock_fixture):
        """Test that existing channels are preserved."""
        pan_state = ChannelState(fixture=mock_fixture)
        pan_state.set_channel("pan", 200)
        tilt_state = ChannelState(fixture=mock_fixture)
        tilt_state.set_channel("tilt", 100)

        effect = SequencedEffect(
            targets=["ALL"],
            channels={"pan": pan_state, "tilt": tilt_state},
            start_ms=0,
            end_ms=1000,
        )
        segment = TimeSegment(start_ms=0, end_ms=1000, effects=[effect])

        dmx_effects = filler.fill([segment], mock_fixture)

        dmx_effect = dmx_effects[0]
        assert dmx_effect.channels["pan"].get_channel("pan") == 200
        assert dmx_effect.channels["tilt"].get_channel("tilt") == 100

    def test_multiple_segments(self, filler, mock_fixture, mock_channel_state):
        """Test filling multiple segments."""
        effect1 = SequencedEffect(
            targets=["ALL"], channels={"pan": mock_channel_state}, start_ms=0, end_ms=500
        )
        effect2 = SequencedEffect(
            targets=["ALL"], channels={"tilt": mock_channel_state}, start_ms=500, end_ms=1000
        )
        segments = [
            TimeSegment(start_ms=0, end_ms=500, effects=[effect1]),
            TimeSegment(start_ms=500, end_ms=1000, effects=[effect2]),
        ]

        dmx_effects = filler.fill(segments, mock_fixture)

        assert len(dmx_effects) == 2
        assert dmx_effects[0].start_ms == 0
        assert dmx_effects[0].end_ms == 500
        assert dmx_effects[1].start_ms == 500
        assert dmx_effects[1].end_ms == 1000

    def test_fixture_without_optional_channels(self, filler, mock_channel_state):
        """Test fixture without optional channels (color, gobo)."""
        from blinkb0t.core.config.fixtures import ChannelInversions, MovementLimits

        fixture = Mock(spec=FixtureInstance)
        fixture.fixture_id = "MH1"
        fixture.config = Mock(spec=FixtureConfig)
        fixture.config.dmx_mapping = Mock(spec=DmxMapping)

        # Only pan, tilt, dimmer, shutter
        fixture.config.dmx_mapping.pan_channel = 1
        fixture.config.dmx_mapping.tilt_channel = 2
        fixture.config.dmx_mapping.dimmer_channel = 3
        fixture.config.dmx_mapping.shutter = 4
        fixture.config.dmx_mapping.color = None  # No color
        fixture.config.dmx_mapping.gobo = None  # No gobo
        fixture.config.dmx_mapping.use_16bit_pan_tilt = False
        fixture.config.dmx_mapping.pan_fine_channel = None
        fixture.config.dmx_mapping.tilt_fine_channel = None

        # Add required attributes
        fixture.config.inversions = ChannelInversions()
        fixture.config.limits = MovementLimits()

        effect = SequencedEffect(
            targets=["ALL"], channels={"pan": mock_channel_state}, start_ms=0, end_ms=1000
        )
        segment = TimeSegment(start_ms=0, end_ms=1000, effects=[effect])

        dmx_effects = filler.fill([segment], fixture)

        dmx_effect = dmx_effects[0]
        # Should have pan, tilt, dimmer, shutter
        assert "pan" in dmx_effect.channels
        assert "tilt" in dmx_effect.channels
        assert "dimmer" in dmx_effect.channels
        assert "shutter" in dmx_effect.channels
        # Should NOT have color or gobo
        assert "color" not in dmx_effect.channels
        assert "gobo" not in dmx_effect.channels
