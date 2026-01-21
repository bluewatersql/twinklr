"""Comprehensive tests forComponent 2: Channel Handlers."""

from __future__ import annotations

from unittest.mock import Mock

import pytest

from blinkb0t.core.config.fixtures import (
    DmxMapping,
    FixtureConfig,
    FixtureGroup,
    FixtureInstance,
    ShutterMap,
)
from blinkb0t.core.domains.sequencing.channels.handlers import (
    ColorHandler,
    GoboHandler,
    ShutterHandler,
)
from blinkb0t.core.domains.sequencing.libraries.channels import (
    ColorLibrary,
    GoboLibrary,
    ShutterLibrary,
)
from blinkb0t.core.domains.sequencing.models.channels import ChannelEffect

# ═══════════════════════════════════════════════════════════════════════════
# Fixtures
# ═══════════════════════════════════════════════════════════════════════════


@pytest.fixture
def mock_fixture_with_all_channels():
    """Create mock fixture with all channels and proper shutter_map."""
    fixture = Mock(spec=FixtureInstance)
    fixture.fixture_id = "MH1"
    fixture.config = Mock(spec=FixtureConfig)
    fixture.config.dmx_mapping = Mock(spec=DmxMapping)

    # Mock shutter channel property (returns channel number or None)
    fixture.config.dmx_mapping.shutter = 1  # Has shutter channel
    fixture.config.dmx_mapping.color = 2  # Has color channel
    fixture.config.dmx_mapping.gobo = 3  # Has gobo channel

    # Mock shutter_map with fixture-specific DMX values
    fixture.config.dmx_mapping.shutter_map = ShutterMap(
        closed=0,
        open=255,
        strobe_slow=64,
        strobe_medium=127,
        strobe_fast=190,
    )

    # Mock color_map
    fixture.config.dmx_mapping.color_map = {
        "white": 0,
        "blue": 30,
        "red": 10,
    }

    # Mock gobo_map
    fixture.config.dmx_mapping.gobo_map = {
        "open": 0,
        "stars": 60,
    }

    return fixture


@pytest.fixture
def mock_fixture_group_with_all_channels(mock_fixture_with_all_channels):
    """Create mock fixture group with all channels."""
    fixture_group = Mock(spec=FixtureGroup)
    fixture_group.fixtures = [mock_fixture_with_all_channels]
    # Mock expand_fixtures to return the fixtures list
    fixture_group.expand_fixtures.return_value = [mock_fixture_with_all_channels]
    return fixture_group


@pytest.fixture
def mock_fixture_no_channels():
    """Create mock fixture without channel support."""
    fixture = Mock(spec=FixtureInstance)
    fixture.fixture_id = "MH2"
    fixture.config = Mock(spec=FixtureConfig)
    fixture.config.dmx_mapping = Mock(spec=DmxMapping)

    # Mock channel properties returning None (no channels)
    fixture.config.dmx_mapping.shutter = None
    fixture.config.dmx_mapping.color = None
    fixture.config.dmx_mapping.gobo = None

    return fixture


@pytest.fixture
def mock_fixture_group_no_channels(mock_fixture_no_channels):
    """Create mock fixture group without channels."""
    fixture_group = Mock(spec=FixtureGroup)
    fixture_group.fixtures = [mock_fixture_no_channels]
    # Mock expand_fixtures to return the fixtures list
    fixture_group.expand_fixtures.return_value = [mock_fixture_no_channels]
    return fixture_group


# ═══════════════════════════════════════════════════════════════════════════
# Library Tests
# ═══════════════════════════════════════════════════════════════════════════


class TestShutterLibrary:
    """Test ShutterLibrary."""

    def test_get_pattern_open(self):
        """Test getting open pattern."""
        pattern = ShutterLibrary.get_pattern("open")
        assert pattern.pattern_id == "open"
        assert pattern.dmx_value == ShutterLibrary.DMX_OPEN
        assert pattern.is_dynamic is False

    def test_get_pattern_strobe_fast(self):
        """Test getting strobe_fast pattern."""
        pattern = ShutterLibrary.get_pattern("strobe_fast")
        assert pattern.pattern_id == "strobe_fast"
        assert pattern.dmx_value == ShutterLibrary.DMX_STROBE_FAST
        assert pattern.energy_level == 10

    def test_get_pattern_pulse(self):
        """Test getting pulse pattern."""
        pattern = ShutterLibrary.get_pattern("pulse")
        assert pattern.pattern_id == "pulse"
        assert pattern.is_dynamic is True
        assert pattern.dmx_value is None

    def test_invalid_pattern_raises(self):
        """Test invalid pattern raises error."""
        with pytest.raises(ValueError, match="Unknown shutter pattern"):
            ShutterLibrary.get_pattern("invalid")

    def test_get_all_metadata(self):
        """Test getting all pattern metadata."""
        metadata = ShutterLibrary.get_all_metadata()
        assert len(metadata) == 6  # 6 patterns
        assert all("pattern_id" in m for m in metadata)
        assert all("energy_level" in m for m in metadata)

    def test_all_patterns_have_required_fields(self):
        """Test all patterns have required fields."""
        for pattern in ShutterLibrary.PATTERNS.values():
            assert pattern.pattern_id
            assert pattern.name
            assert pattern.description
            assert isinstance(pattern.is_dynamic, bool)
            assert 0 <= pattern.energy_level <= 10


class TestColorLibrary:
    """Test ColorLibrary."""

    def test_get_preset_blue(self):
        """Test getting blue preset."""
        preset = ColorLibrary.get_preset("blue")
        assert preset.color_id == "blue"
        assert preset.category == "primary"
        assert preset.mood == "cool"

    def test_get_preset_white(self):
        """Test getting white preset."""
        preset = ColorLibrary.get_preset("white")
        assert preset.color_id == "white"
        assert preset.dmx_value == 0
        assert preset.category == "special"

    def test_invalid_preset_raises(self):
        """Test invalid preset raises error."""
        with pytest.raises(ValueError, match="Unknown color preset"):
            ColorLibrary.get_preset("invalid")

    def test_get_all_metadata(self):
        """Test getting all preset metadata."""
        metadata = ColorLibrary.get_all_metadata()
        assert len(metadata) == 14  # 14 presets
        assert all("color_id" in m for m in metadata)
        assert all("mood" in m for m in metadata)

    def test_get_by_mood_warm(self):
        """Test filtering by warm mood."""
        warm_colors = ColorLibrary.get_by_mood("warm")
        assert all(c.mood == "warm" for c in warm_colors)
        assert len(warm_colors) > 0

    def test_get_by_mood_cool(self):
        """Test filtering by cool mood."""
        cool_colors = ColorLibrary.get_by_mood("cool")
        assert all(c.mood == "cool" for c in cool_colors)
        assert len(cool_colors) > 0

    def test_all_presets_have_required_fields(self):
        """Test all presets have required fields."""
        for preset in ColorLibrary.PRESETS.values():
            assert preset.color_id
            assert preset.name
            assert preset.description
            assert 0 <= preset.dmx_value <= 255
            assert preset.category in ["primary", "secondary", "special"]
            assert preset.mood in ["warm", "cool", "neutral"]


class TestGoboLibrary:
    """Test GoboLibrary."""

    def test_get_pattern_stars(self):
        """Test getting stars pattern."""
        pattern = GoboLibrary.get_pattern("stars")
        assert pattern.gobo_id == "stars"
        assert pattern.category == "geometric"
        assert 0 <= pattern.visual_density <= 10

    def test_get_pattern_open(self):
        """Test getting open pattern."""
        pattern = GoboLibrary.get_pattern("open")
        assert pattern.gobo_id == "open"
        assert pattern.dmx_value == 0
        assert pattern.visual_density == 1  # Changed from 0 to meet validation (ge=1)

    def test_invalid_pattern_raises(self):
        """Test invalid pattern raises error."""
        with pytest.raises(ValueError, match="Unknown gobo pattern"):
            GoboLibrary.get_pattern("invalid")

    def test_get_all_metadata(self):
        """Test getting all pattern metadata."""
        metadata = GoboLibrary.get_all_metadata()
        assert len(metadata) == 13  # 13 patterns
        assert all("gobo_id" in m for m in metadata)
        assert all("visual_density" in m for m in metadata)

    def test_get_by_category_geometric(self):
        """Test filtering by geometric category."""
        geometric = GoboLibrary.get_by_category("geometric")
        assert all(g.category == "geometric" for g in geometric)
        assert len(geometric) > 0

    def test_get_by_category_breakup(self):
        """Test filtering by breakup category."""
        breakup = GoboLibrary.get_by_category("breakup")
        assert all(g.category == "breakup" for g in breakup)
        assert len(breakup) > 0

    def test_all_patterns_have_required_fields(self):
        """Test all patterns have required fields."""
        for pattern in GoboLibrary.PATTERNS.values():
            assert pattern.gobo_id
            assert pattern.name
            assert pattern.description
            assert 0 <= pattern.dmx_value <= 255
            assert pattern.category in ["basic", "geometric", "breakup", "special"]
            assert 0 <= pattern.visual_density <= 10


# ═══════════════════════════════════════════════════════════════════════════
# Handler Tests
# ═══════════════════════════════════════════════════════════════════════════


class TestShutterHandler:
    """Test ShutterHandler."""

    @pytest.fixture
    def handler(self):
        """Create handler instance."""
        library = ShutterLibrary()
        return ShutterHandler(library)

    def test_render_static_pattern_open(self, handler, mock_fixture_group_with_all_channels):
        """Test rendering static open pattern."""
        effects = handler.render(
            channel_value="open",
            fixtures=mock_fixture_group_with_all_channels,
            start_time_ms=0,
            end_time_ms=8000,
        )

        assert len(effects) == 1
        effect = effects[0]
        assert effect.fixture_id == "MH1"
        assert effect.channel_name == "shutter"
        # Should use fixture's shutter_map.open value (255)
        assert effect.dmx_values == [255]
        assert effect.value_curve is None  # Constant value (no curve)
        assert effect.start_time_ms == 0
        assert effect.end_time_ms == 8000

    def test_render_strobe_fast(self, handler, mock_fixture_group_with_all_channels):
        """Test rendering strobe_fast pattern using fixture-specific DMX values."""
        effects = handler.render(
            channel_value="strobe_fast",
            fixtures=mock_fixture_group_with_all_channels,
            start_time_ms=1000,
            end_time_ms=5000,
        )

        assert len(effects) == 1
        # Should use fixture's shutter_map.strobe_fast value (190)
        assert effects[0].dmx_values == [190]
        assert effects[0].value_curve is None  # Constant value

    def test_render_pulse_with_beats(self, handler, mock_fixture_group_with_all_channels):
        """Test rendering pulse pattern with beat sync using fixture-specific DMX values."""
        beat_times = [0, 500, 1000, 1500, 2000]

        effects = handler.render(
            channel_value="pulse",
            fixtures=mock_fixture_group_with_all_channels,
            start_time_ms=0,
            end_time_ms=2000,
            beat_times_ms=beat_times,
        )

        assert len(effects) == 1
        effect = effects[0]
        assert effect.value_curve is None  # Dynamic pattern (discrete values, no curve)
        assert len(effect.dmx_values) == len(beat_times)
        # Should alternate between fixture's open (255) and closed (0) values
        assert effect.dmx_values[0] == 255  # open
        assert effect.dmx_values[1] == 0  # closed
        assert effect.dmx_values[2] == 255  # open
        assert effect.dmx_values[3] == 0  # closed
        assert effect.dmx_values[4] == 255  # open

    def test_render_pulse_without_beats_fallback(
        self, handler, mock_fixture_group_with_all_channels
    ):
        """Test pulse without beats falls back to open using fixture's value."""
        effects = handler.render(
            channel_value="pulse",
            fixtures=mock_fixture_group_with_all_channels,
            start_time_ms=0,
            end_time_ms=2000,
            beat_times_ms=None,
        )

        assert len(effects) == 1
        # Should use fixture's shutter_map.open value (255)
        assert effects[0].dmx_values == [255]

    def test_fixture_without_shutter_skipped(self, handler, mock_fixture_group_no_channels):
        """Test fixture without shutter channel is skipped."""
        effects = handler.render(
            channel_value="open",
            fixtures=mock_fixture_group_no_channels,
            start_time_ms=0,
            end_time_ms=8000,
        )

        assert len(effects) == 0

    def test_invalid_pattern_raises(self, handler, mock_fixture_group_with_all_channels):
        """Test invalid pattern raises error."""
        with pytest.raises(ValueError, match="Unknown shutter pattern"):
            handler.render(
                channel_value="invalid",
                fixtures=mock_fixture_group_with_all_channels,
                start_time_ms=0,
                end_time_ms=8000,
            )


class TestColorHandler:
    """Test ColorHandler."""

    @pytest.fixture
    def handler(self):
        """Create handler instance."""
        library = ColorLibrary()
        return ColorHandler(library)

    def test_render_blue(self, handler, mock_fixture_group_with_all_channels):
        """Test rendering blue color using fixture-specific DMX values."""
        effects = handler.render(
            channel_value="blue",
            fixtures=mock_fixture_group_with_all_channels,
            start_time_ms=0,
            end_time_ms=8000,
        )

        assert len(effects) == 1
        effect = effects[0]
        assert effect.fixture_id == "MH1"
        assert effect.channel_name == "color"
        # Should use fixture's color_map value for blue (30)
        assert effect.dmx_values == [30]
        assert effect.value_curve is None  # Constant value

    def test_render_white(self, handler, mock_fixture_group_with_all_channels):
        """Test rendering white color using fixture-specific DMX values."""
        effects = handler.render(
            channel_value="white",
            fixtures=mock_fixture_group_with_all_channels,
            start_time_ms=0,
            end_time_ms=8000,
        )

        assert len(effects) == 1
        # Should use fixture's color_map value for white (0)
        assert effects[0].dmx_values == [0]

    def test_fixture_without_color_skipped(self, handler, mock_fixture_group_no_channels):
        """Test fixture without color channel is skipped."""
        effects = handler.render(
            channel_value="blue",
            fixtures=mock_fixture_group_no_channels,
            start_time_ms=0,
            end_time_ms=8000,
        )

        assert len(effects) == 0

    def test_invalid_color_raises(self, handler, mock_fixture_group_with_all_channels):
        """Test invalid color raises error."""
        with pytest.raises(ValueError, match="Unknown color preset"):
            handler.render(
                channel_value="invalid",
                fixtures=mock_fixture_group_with_all_channels,
                start_time_ms=0,
                end_time_ms=8000,
            )


class TestGoboHandler:
    """Test GoboHandler."""

    @pytest.fixture
    def handler(self):
        """Create handler instance."""
        library = GoboLibrary()
        return GoboHandler(library)

    def test_render_stars(self, handler, mock_fixture_group_with_all_channels):
        """Test rendering stars gobo using fixture-specific DMX values."""
        effects = handler.render(
            channel_value="stars",
            fixtures=mock_fixture_group_with_all_channels,
            start_time_ms=0,
            end_time_ms=8000,
        )

        assert len(effects) == 1
        effect = effects[0]
        assert effect.fixture_id == "MH1"
        assert effect.channel_name == "gobo"
        # Should use fixture's gobo_map value for stars (60)
        assert effect.dmx_values == [60]
        assert effect.value_curve is None  # Constant value

    def test_render_open(self, handler, mock_fixture_group_with_all_channels):
        """Test rendering open gobo using fixture-specific DMX values."""
        effects = handler.render(
            channel_value="open",
            fixtures=mock_fixture_group_with_all_channels,
            start_time_ms=0,
            end_time_ms=8000,
        )

        assert len(effects) == 1
        # Should use fixture's gobo_map value for open (0)
        assert effects[0].dmx_values == [0]

    def test_fixture_without_gobo_skipped(self, handler, mock_fixture_group_no_channels):
        """Test fixture without gobo channel is skipped."""
        effects = handler.render(
            channel_value="stars",
            fixtures=mock_fixture_group_no_channels,
            start_time_ms=0,
            end_time_ms=8000,
        )

        assert len(effects) == 0

    def test_invalid_gobo_raises(self, handler, mock_fixture_group_with_all_channels):
        """Test invalid gobo raises error."""
        with pytest.raises(ValueError, match="Unknown gobo pattern"):
            handler.render(
                channel_value="invalid",
                fixtures=mock_fixture_group_with_all_channels,
                start_time_ms=0,
                end_time_ms=8000,
            )


# ═══════════════════════════════════════════════════════════════════════════
# ChannelEffect Model Tests
# ═══════════════════════════════════════════════════════════════════════════


class TestChannelEffect:
    """Test ChannelEffect model."""

    def test_valid_creation(self):
        """Test creating valid channel effect."""
        effect = ChannelEffect(
            fixture_id="MH1",
            channel_name="shutter",
            start_time_ms=0,
            end_time_ms=8000,
            dmx_values=[255],
            value_curve=None,
        )

        assert effect.fixture_id == "MH1"
        assert effect.channel_name == "shutter"
        assert effect.start_time_ms == 0
        assert effect.end_time_ms == 8000
        assert effect.dmx_values == [255]
        assert effect.value_curve is None

    def test_end_time_must_be_greater_than_start(self):
        """Test end_time_ms must be > start_time_ms."""
        with pytest.raises(ValueError, match="end_time_ms must be > start_time_ms"):
            ChannelEffect(
                fixture_id="MH1",
                channel_name="shutter",
                start_time_ms=8000,
                end_time_ms=0,  # Invalid: end <= start
                dmx_values=[255],
                value_curve=None,
            )

    def test_dmx_values_cannot_be_empty(self):
        """Test dmx_values cannot be empty."""
        with pytest.raises(ValueError, match="dmx_values cannot be empty"):
            ChannelEffect(
                fixture_id="MH1",
                channel_name="shutter",
                start_time_ms=0,
                end_time_ms=8000,
                dmx_values=[],  # Invalid: empty
                value_curve=None,
            )

    def test_dmx_values_must_be_0_255(self):
        """Test DMX values must be 0-255."""
        with pytest.raises(ValueError, match="All DMX values must be 0-255"):
            ChannelEffect(
                fixture_id="MH1",
                channel_name="shutter",
                start_time_ms=0,
                end_time_ms=8000,
                dmx_values=[256],  # Invalid: > 255
                value_curve=None,
            )

    def test_negative_dmx_value_raises(self):
        """Test negative DMX value raises error."""
        with pytest.raises(ValueError, match="All DMX values must be 0-255"):
            ChannelEffect(
                fixture_id="MH1",
                channel_name="shutter",
                start_time_ms=0,
                end_time_ms=8000,
                dmx_values=[-1],  # Invalid: < 0
                value_curve=None,
            )

    def test_multiple_dmx_values(self):
        """Test effect with multiple DMX values."""
        effect = ChannelEffect(
            fixture_id="MH1",
            channel_name="shutter",
            start_time_ms=0,
            end_time_ms=2000,
            dmx_values=[255, 0, 255, 0, 255],
            value_curve=None,
        )

        assert len(effect.dmx_values) == 5
        assert effect.value_curve is None
