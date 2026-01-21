"""Integration tests forchannel system (Component 7).

Tests interaction between multiplecomponents to ensure they work together.
"""

import pytest

from blinkb0t.core.agents.moving_heads.channel_validator import ChannelHeuristicValidator
from blinkb0t.core.agents.moving_heads.models_agent_plan import SectionPlan
from blinkb0t.core.config.loader import validate_channel_config
from blinkb0t.core.config.models import ChannelDefaults, JobConfig, PlannerFeatures
from blinkb0t.core.domains.sequencing.libraries.channels import (
    ColorLibrary,
    GoboLibrary,
    ShutterLibrary,
)
from blinkb0t.core.domains.sequencing.models.channels import ChannelSpecification


class TestChannelLibrariesIntegration:
    """Test channel libraries work together with configuration."""

    def test_all_libraries_accessible(self):
        """Test all three channel libraries are accessible."""
        shutter_lib = ShutterLibrary()
        color_lib = ColorLibrary()
        gobo_lib = GoboLibrary()

        # Should be able to get patterns from all libraries
        shutter_pattern = shutter_lib.get_pattern("open")
        color_preset = color_lib.get_preset("white")
        gobo_pattern = gobo_lib.get_pattern("open")

        assert shutter_pattern.pattern_id == "open"
        assert color_preset.color_id == "white"
        assert gobo_pattern.gobo_id == "open"

    def test_config_validation_with_real_libraries(self):
        """Test configuration validation with real library values."""
        # Valid config with real library values
        valid_config = JobConfig(
            channel_defaults=ChannelDefaults(shutter="open", color="blue", gobo="stars")
        )

        is_valid, errors = validate_channel_config(valid_config)
        assert is_valid is True
        assert len(errors) == 0

        # Invalid config
        invalid_config = JobConfig(
            channel_defaults=ChannelDefaults(shutter="invalid_shutter", color="white", gobo="open")
        )

        is_valid, errors = validate_channel_config(invalid_config)
        assert is_valid is False
        assert len(errors) > 0


class TestConfigurationToValidation:
    """Test configuration → validation flow."""

    def test_channel_defaults_validated_on_load(self):
        """Test channel defaults are validated."""
        config = JobConfig(
            channel_defaults=ChannelDefaults(shutter="strobe_fast", color="red", gobo="stars")
        )

        # Should validate successfully
        is_valid, _ = validate_channel_config(config)

        assert is_valid is True
        assert config.channel_defaults.shutter == "strobe_fast"
        assert config.channel_defaults.color == "red"
        assert config.channel_defaults.gobo == "stars"

    def test_feature_flags_control_planning(self):
        """Test feature flags control what gets planned."""
        # Disable color planning
        config = JobConfig(
            planner_features=PlannerFeatures(
                enable_shutter=True, enable_color=False, enable_gobo=True
            )
        )

        assert config.is_channel_enabled("shutter") is True
        assert config.is_channel_enabled("color") is False
        assert config.is_channel_enabled("gobo") is True


class TestAgentValidationFlow:
    """Test agent plan → validation flow."""

    @pytest.fixture
    def validator(self):
        """Create channel validator."""
        return ChannelHeuristicValidator()

    def test_high_energy_section_validation(self, validator):
        """Test high energy section with appropriate shutter."""
        section = SectionPlan(
            name="chorus",
            start_bar=1,
            end_bar=8,
            section_role="chorus",
            energy_level=85,  # High energy
            templates=["energetic_fan"],
            params={"intensity": "DRAMATIC"},
            base_pose="UP",
            reasoning="High energy chorus",
            channels=ChannelSpecification(shutter="strobe_fast"),  # Appropriate
        )

        is_valid, warnings = validator.validate_section_channels(section)

        assert is_valid is True
        assert len(warnings) == 0

    def test_low_energy_section_validation(self, validator):
        """Test low energy section with appropriate shutter."""
        section = SectionPlan(
            name="verse",
            start_bar=1,
            end_bar=8,
            section_role="verse",
            energy_level=25,  # Low energy
            templates=["gentle_sweep"],
            params={"intensity": "SMOOTH"},
            base_pose="FORWARD",
            reasoning="Gentle verse",
            channels=ChannelSpecification(shutter="open"),  # Appropriate
        )

        is_valid, warnings = validator.validate_section_channels(section)

        assert is_valid is True
        assert len(warnings) == 0

    def test_energy_mismatch_detected(self, validator):
        """Test validator detects energy mismatches."""
        section = SectionPlan(
            name="verse",
            start_bar=1,
            end_bar=8,
            section_role="verse",
            energy_level=20,  # Low energy
            templates=["gentle_sweep"],
            params={"intensity": "SMOOTH"},
            base_pose="FORWARD",
            reasoning="Gentle verse",
            channels=ChannelSpecification(shutter="strobe_fast"),  # Wrong!
        )

        is_valid, warnings = validator.validate_section_channels(section)

        assert is_valid is False
        assert len(warnings) > 0
        assert any("Low energy" in w for w in warnings)


class TestEndToEndDataFlow:
    """Test complete data flow through system."""

    def test_config_to_plan_data_flow(self):
        """Test configuration flows to plan correctly."""
        # Create config with specific defaults and flags
        config = JobConfig(
            channel_defaults=ChannelDefaults(shutter="open", color="blue", gobo="open"),
            planner_features=PlannerFeatures(
                enable_shutter=True, enable_color=True, enable_gobo=False
            ),
        )

        # Validate config
        is_valid, _ = validate_channel_config(config)
        assert is_valid is True

        # Create section plan (simulating agent output)
        section = SectionPlan(
            name="verse",
            start_bar=1,
            end_bar=8,
            section_role="verse",
            energy_level=30,
            templates=["gentle_sweep"],
            params={},
            base_pose="FORWARD",
            reasoning="Test",
            channels=ChannelSpecification(
                shutter="open",
                color="blue",  # Can be planned (enabled)
                gobo="open",  # Should use default (disabled)
            ),
        )

        # Validate section
        validator = ChannelHeuristicValidator()
        is_valid, warnings = validator.validate_section_channels(section)

        # Should be valid (gobo is default)
        assert is_valid is True or len(warnings) == 0

    def test_libraries_to_validation_flow(self):
        """Test library values flow to validation correctly."""
        # Get valid values from libraries
        shutter_lib = ShutterLibrary()
        color_lib = ColorLibrary()
        gobo_lib = GoboLibrary()

        valid_shutter = shutter_lib.get_pattern("strobe_fast")
        valid_color = color_lib.get_preset("red")
        valid_gobo = gobo_lib.get_pattern("stars")

        # Create config with these values
        config = JobConfig(
            channel_defaults=ChannelDefaults(
                shutter=valid_shutter.pattern_id,
                color=valid_color.color_id,
                gobo=valid_gobo.gobo_id,
            )
        )

        # Should validate successfully
        is_valid, errors = validate_channel_config(config)

        assert is_valid is True
        assert len(errors) == 0


class TestComponentInteraction:
    """Test multiple components interact correctly."""

    def test_config_and_validator_integration(self):
        """Test config validation and channel validator work together."""
        # Create valid config
        config = JobConfig(
            channel_defaults=ChannelDefaults(shutter="open", color="white", gobo="open")
        )

        # Validate config
        is_valid, _ = validate_channel_config(config)
        assert is_valid is True

        # Create section using config defaults
        section = SectionPlan(
            name="intro",
            start_bar=1,
            end_bar=4,
            section_role="intro",
            energy_level=20,
            templates=["gentle_sweep"],
            params={},
            base_pose="FORWARD",
            reasoning="Test",
            channels=ChannelSpecification(
                shutter=config.channel_defaults.shutter,
                color=config.channel_defaults.color,
                gobo=config.channel_defaults.gobo,
            ),
        )

        # Validate section
        validator = ChannelHeuristicValidator()
        is_valid, _ = validator.validate_section_channels(section)

        # Should be valid (low energy with open shutter is fine)
        assert is_valid is True
