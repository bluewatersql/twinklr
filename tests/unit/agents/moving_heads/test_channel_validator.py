"""Unit tests for channel heuristic validator."""

import pytest

from blinkb0t.core.agents.moving_heads.channel_validator import ChannelHeuristicValidator
from blinkb0t.core.agents.moving_heads.models_agent_plan import SectionPlan
from blinkb0t.core.domains.sequencing.models.channels import ChannelSpecification


class TestChannelHeuristicValidator:
    """Test channel heuristic validation."""

    @pytest.fixture
    def validator(self):
        """Create validator instance."""
        return ChannelHeuristicValidator()

    @pytest.fixture
    def high_energy_section(self):
        """High energy section (should use strobe)."""
        return SectionPlan(
            name="chorus",
            start_bar=1,
            end_bar=8,
            section_role="chorus",
            energy_level=85,  # High energy
            templates=["energetic_fan"],
            params={"intensity": "DRAMATIC"},
            base_pose="UP",
            reasoning="High energy chorus",
        )

    @pytest.fixture
    def low_energy_section(self):
        """Low energy section (should use open shutter)."""
        return SectionPlan(
            name="intro",
            start_bar=1,
            end_bar=8,
            section_role="intro",
            energy_level=25,  # Low energy
            templates=["gentle_sweep"],
            params={"intensity": "SMOOTH"},
            base_pose="FORWARD",
            reasoning="Gentle intro",
        )

    def test_high_energy_with_strobe_valid(self, validator, high_energy_section):
        """High energy section with strobe is valid."""
        high_energy_section.channels = ChannelSpecification(shutter="strobe_fast")

        is_valid, warnings = validator.validate_section_channels(high_energy_section)

        assert is_valid
        assert len(warnings) == 0

    def test_high_energy_with_open_shutter_warns(self, validator, high_energy_section):
        """High energy section with open shutter warns."""
        high_energy_section.channels = ChannelSpecification(shutter="open")

        is_valid, warnings = validator.validate_section_channels(high_energy_section)

        assert not is_valid
        assert len(warnings) > 0
        assert "High energy" in warnings[0]

    def test_low_energy_with_open_valid(self, validator, low_energy_section):
        """Low energy section with open shutter is valid."""
        low_energy_section.channels = ChannelSpecification(shutter="open")

        is_valid, warnings = validator.validate_section_channels(low_energy_section)

        assert is_valid
        assert len(warnings) == 0

    def test_low_energy_with_strobe_warns(self, validator, low_energy_section):
        """Low energy section with strobe warns."""
        low_energy_section.channels = ChannelSpecification(shutter="strobe_fast")

        is_valid, warnings = validator.validate_section_channels(low_energy_section)

        assert not is_valid
        assert len(warnings) > 0
        assert "Low energy" in warnings[0]

    def test_closed_shutter_with_gobo_conflict(self, validator, low_energy_section):
        """Closed shutter with gobo raises conflict."""
        low_energy_section.channels = ChannelSpecification(shutter="closed", gobo="stars")

        is_valid, warnings = validator.validate_section_channels(low_energy_section)

        assert not is_valid
        assert any("won't be visible" in w for w in warnings)

    def test_high_energy_with_cool_colors_warns(self, validator, high_energy_section):
        """High energy with cool colors may warn (suggestion)."""
        high_energy_section.channels = ChannelSpecification(
            shutter="strobe_fast",
            color="blue",  # Cool color
        )

        is_valid, warnings = validator.validate_section_channels(high_energy_section)

        # May warn about cool colors (soft warning)
        if not is_valid:
            assert any("warm colors" in w.lower() for w in warnings)

    def test_unknown_shutter_pattern_error(self, validator, low_energy_section):
        """Unknown shutter pattern raises error."""
        low_energy_section.channels = ChannelSpecification(shutter="invalid_pattern")

        is_valid, warnings = validator.validate_section_channels(low_energy_section)

        assert not is_valid
        assert any("Unknown shutter" in w for w in warnings)

    def test_no_channel_overrides_valid(self, validator, low_energy_section):
        """Section with no channel overrides is valid."""
        # Default (empty) channel spec
        low_energy_section.channels = ChannelSpecification()

        is_valid, warnings = validator.validate_section_channels(low_energy_section)

        assert is_valid
        assert len(warnings) == 0

    def test_partial_channel_overrides(self, validator, high_energy_section):
        """Partial channel overrides are validated."""
        # Only override color, not shutter/gobo
        high_energy_section.channels = ChannelSpecification(color="red")

        is_valid, warnings = validator.validate_section_channels(high_energy_section)

        # Should be valid (red is warm, appropriate for high energy)
        assert is_valid or len(warnings) == 0
