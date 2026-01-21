"""Tests for gap detection and filling."""

from dataclasses import FrozenInstanceError

import pytest

from blinkb0t.core.config.fixtures import FixtureInstance
from blinkb0t.core.domains.sequencing.channels.pipeline.gap_detector import Gap, GapDetector
from blinkb0t.core.domains.sequencing.channels.pipeline.gap_filler import GapFiller
from blinkb0t.core.domains.sequencing.channels.state import ChannelState
from blinkb0t.core.domains.sequencing.models.channels import DmxEffect


class TestGap:
    """Test Gap model."""

    def test_valid_gap(self):
        """Test valid Gap creation."""
        gap = Gap(start_ms=100, end_ms=200)
        assert gap.start_ms == 100
        assert gap.end_ms == 200

    def test_gap_zero_start(self):
        """Test Gap with start_ms at 0."""
        gap = Gap(start_ms=0, end_ms=100)
        assert gap.start_ms == 0
        assert gap.end_ms == 100

    def test_end_time_must_be_greater_than_start(self):
        """Test end_ms must be > start_ms."""
        with pytest.raises(ValueError, match=r"end_ms .* must be > start_ms"):
            Gap(start_ms=500, end_ms=100)

    def test_end_time_equal_to_start_raises(self):
        """Test end_ms equal to start_ms raises error."""
        with pytest.raises(ValueError, match=r"end_ms .* must be > start_ms"):
            Gap(start_ms=100, end_ms=100)

    def test_immutability(self):
        """Test that Gap instances are immutable."""
        gap = Gap(start_ms=0, end_ms=1000)
        with pytest.raises(FrozenInstanceError):
            gap.start_ms = 500  # type: ignore


class TestGapDetector:
    """Test GapDetector."""

    @pytest.fixture
    def detector(self):
        return GapDetector()

    @pytest.fixture
    def mock_dmx_effect(self, mock_fixture: FixtureInstance, mock_channel_state: ChannelState):
        """Create a mock DmxEffect."""

        def _create(start_ms: int, end_ms: int) -> DmxEffect:
            return DmxEffect(
                fixture_id=mock_fixture.fixture_id,
                start_ms=start_ms,
                end_ms=end_ms,
                channels={"pan": mock_channel_state, "tilt": mock_channel_state},
            )

        return _create

    def test_no_effects_entire_section_is_gap(self, detector):
        """Test that no effects means entire section is a gap."""
        gaps = detector.detect([], section_start_ms=0, section_end_ms=1000)

        assert len(gaps) == 1
        assert gaps[0].start_ms == 0
        assert gaps[0].end_ms == 1000

    def test_single_effect_no_gaps(self, detector, mock_dmx_effect):
        """Test single effect covering entire section has no gaps."""
        effects = [mock_dmx_effect(0, 1000)]

        gaps = detector.detect(effects, section_start_ms=0, section_end_ms=1000)

        assert len(gaps) == 0

    def test_gap_at_section_start(self, detector, mock_dmx_effect):
        """Test gap detection at section start."""
        effects = [mock_dmx_effect(100, 1000)]

        gaps = detector.detect(effects, section_start_ms=0, section_end_ms=1000)

        assert len(gaps) == 1
        assert gaps[0].start_ms == 0
        assert gaps[0].end_ms == 100

    def test_gap_at_section_end(self, detector, mock_dmx_effect):
        """Test gap detection at section end."""
        effects = [mock_dmx_effect(0, 800)]

        gaps = detector.detect(effects, section_start_ms=0, section_end_ms=1000)

        assert len(gaps) == 1
        assert gaps[0].start_ms == 800
        assert gaps[0].end_ms == 1000

    def test_gap_between_effects(self, detector, mock_dmx_effect):
        """Test gap detection between two effects."""
        effects = [mock_dmx_effect(100, 200), mock_dmx_effect(300, 400)]

        gaps = detector.detect(effects, section_start_ms=0, section_end_ms=500)

        assert len(gaps) == 3
        # Gap at start
        assert gaps[0].start_ms == 0
        assert gaps[0].end_ms == 100
        # Gap between effects
        assert gaps[1].start_ms == 200
        assert gaps[1].end_ms == 300
        # Gap at end
        assert gaps[2].start_ms == 400
        assert gaps[2].end_ms == 500

    def test_multiple_gaps_between_effects(self, detector, mock_dmx_effect):
        """Test multiple gaps between effects."""
        effects = [
            mock_dmx_effect(100, 200),
            mock_dmx_effect(300, 400),
            mock_dmx_effect(500, 600),
        ]

        gaps = detector.detect(effects, section_start_ms=0, section_end_ms=700)

        assert len(gaps) == 4
        assert gaps[0].start_ms == 0  # Start gap
        assert gaps[1].start_ms == 200  # Between 1 and 2
        assert gaps[2].start_ms == 400  # Between 2 and 3
        assert gaps[3].start_ms == 600  # End gap

    def test_contiguous_effects_no_gaps(self, detector, mock_dmx_effect):
        """Test contiguous effects with no gaps between."""
        effects = [mock_dmx_effect(0, 200), mock_dmx_effect(200, 400), mock_dmx_effect(400, 600)]

        gaps = detector.detect(effects, section_start_ms=0, section_end_ms=600)

        assert len(gaps) == 0

    def test_unsorted_effects_handled(self, detector, mock_dmx_effect):
        """Test that unsorted effects are handled correctly."""
        effects = [
            mock_dmx_effect(300, 400),
            mock_dmx_effect(100, 200),  # Out of order
            mock_dmx_effect(500, 600),
        ]

        gaps = detector.detect(effects, section_start_ms=0, section_end_ms=700)

        assert len(gaps) == 4
        assert gaps[0].start_ms == 0
        assert gaps[0].end_ms == 100
        assert gaps[1].start_ms == 200
        assert gaps[1].end_ms == 300


class TestGapFiller:
    """Test GapFiller."""

    @pytest.fixture
    def filler(self):
        return GapFiller()

    def test_fills_gap_with_soft_home(self, filler, mock_fixture: FixtureInstance):
        """Test that gaps are filled with soft home position."""
        gaps = [Gap(start_ms=100, end_ms=200)]

        gap_effects = filler.fill(gaps, mock_fixture)

        assert len(gap_effects) == 1
        effect = gap_effects[0]

        # Verify timing
        assert effect.start_ms == 100
        assert effect.end_ms == 200
        assert effect.fixture_id == mock_fixture.fixture_id

        # Verify channels exist
        assert "pan" in effect.channels
        assert "tilt" in effect.channels

        # Verify soft home position (0, 0 degrees -> DMX values)
        # PoseID.SOFT_HOME maps to Pose(pan_deg=0.0, tilt_deg=0.0)
        # We need to check the actual DMX values
        pan_value = effect.channels["pan"].get_channel("pan")
        tilt_value = effect.channels["tilt"].get_channel("tilt")

        # Verify it's a valid DMX value (0-255)
        assert pan_value is not None
        assert tilt_value is not None
        assert 0 <= pan_value <= 255
        assert 0 <= tilt_value <= 255

    def test_fills_multiple_gaps(self, filler, mock_fixture: FixtureInstance):
        """Test filling multiple gaps."""
        gaps = [Gap(start_ms=100, end_ms=200), Gap(start_ms=300, end_ms=400)]

        gap_effects = filler.fill(gaps, mock_fixture)

        assert len(gap_effects) == 2
        assert gap_effects[0].start_ms == 100
        assert gap_effects[0].end_ms == 200
        assert gap_effects[1].start_ms == 300
        assert gap_effects[1].end_ms == 400

    def test_includes_shutter_closed(self, filler, mock_fixture: FixtureInstance):
        """Test that shutter is closed in gap fill."""
        gaps = [Gap(start_ms=100, end_ms=200)]

        gap_effects = filler.fill(gaps, mock_fixture)

        effect = gap_effects[0]
        assert "shutter" in effect.channels
        assert effect.channels["shutter"].get_channel("shutter") == 0  # Closed

    def test_includes_dimmer_off(self, filler, mock_fixture: FixtureInstance):
        """Test that dimmer is off in gap fill."""
        gaps = [Gap(start_ms=100, end_ms=200)]

        gap_effects = filler.fill(gaps, mock_fixture)

        effect = gap_effects[0]
        assert "dimmer" in effect.channels
        assert effect.channels["dimmer"].get_channel("dimmer") == 0  # Off

    def test_includes_color_open(self, filler, mock_fixture: FixtureInstance):
        """Test that color is open/white in gap fill."""
        gaps = [Gap(start_ms=100, end_ms=200)]

        gap_effects = filler.fill(gaps, mock_fixture)

        effect = gap_effects[0]
        assert "color" in effect.channels
        assert effect.channels["color"].get_channel("color") == 0  # White/open

    def test_includes_gobo_open(self, filler, mock_fixture: FixtureInstance):
        """Test that gobo is open in gap fill."""
        gaps = [Gap(start_ms=100, end_ms=200)]

        gap_effects = filler.fill(gaps, mock_fixture)

        effect = gap_effects[0]
        assert "gobo" in effect.channels
        assert effect.channels["gobo"].get_channel("gobo") == 0  # Open

    def test_metadata_identifies_gap_fill(self, filler, mock_fixture: FixtureInstance):
        """Test that metadata identifies effect as gap fill."""
        gaps = [Gap(start_ms=100, end_ms=200)]

        gap_effects = filler.fill(gaps, mock_fixture)

        effect = gap_effects[0]
        assert effect.metadata["type"] == "gap_fill"
        assert effect.metadata["source"] == "gap_filler"

    def test_empty_gaps_list(self, filler, mock_fixture: FixtureInstance):
        """Test that empty gaps list returns empty effects list."""
        gap_effects = filler.fill([], mock_fixture)

        assert len(gap_effects) == 0
