"""Unit tests for channel configuration (Component 5)."""

from pydantic import ValidationError
import pytest

from blinkb0t.core.config.loader import validate_channel_config
from blinkb0t.core.config.models import ChannelDefaults, JobConfig, PlannerFeatures


class TestChannelDefaults:
    """Test ChannelDefaults configuration model."""

    def test_default_values(self):
        """Test default channel values."""
        defaults = ChannelDefaults()

        assert defaults.shutter == "open"
        assert defaults.color == "white"
        assert defaults.gobo == "open"

    def test_custom_values(self):
        """Test custom channel values."""
        defaults = ChannelDefaults(shutter="strobe_fast", color="blue", gobo="stars")

        assert defaults.shutter == "strobe_fast"
        assert defaults.color == "blue"
        assert defaults.gobo == "stars"

    def test_immutable(self):
        """Test defaults are immutable (frozen)."""
        defaults = ChannelDefaults()

        with pytest.raises(ValidationError):
            defaults.shutter = "closed"  # type: ignore

    def test_extra_fields_rejected(self):
        """Test extra fields are rejected."""
        with pytest.raises(ValidationError):
            ChannelDefaults(shutter="open", color="white", gobo="open", invalid_field="value")  # type: ignore


class TestPlannerFeatures:
    """Test PlannerFeatures with channel flags."""

    def test_default_flags(self):
        """Test default channel flags."""
        features = PlannerFeatures()

        assert features.enable_shutter is True
        assert features.enable_color is True
        assert features.enable_gobo is True

    def test_custom_flags(self):
        """Test custom channel flags."""
        features = PlannerFeatures(enable_shutter=True, enable_color=False, enable_gobo=True)

        assert features.enable_shutter is True
        assert features.enable_color is False
        assert features.enable_gobo is True

    def test_all_disabled(self):
        """Test all channels can be disabled."""
        features = PlannerFeatures(enable_shutter=False, enable_color=False, enable_gobo=False)

        assert features.enable_shutter is False
        assert features.enable_color is False
        assert features.enable_gobo is False


class TestJobConfigChannels:
    """Test JobConfig with channel configuration."""

    def test_default_channel_config(self):
        """Test default channel configuration."""
        config = JobConfig()

        assert config.channel_defaults.shutter == "open"
        assert config.channel_defaults.color == "white"
        assert config.channel_defaults.gobo == "open"

    def test_custom_channel_defaults(self):
        """Test custom channel defaults."""
        config = JobConfig(
            channel_defaults=ChannelDefaults(shutter="open", color="blue", gobo="stars")
        )

        assert config.channel_defaults.color == "blue"
        assert config.channel_defaults.gobo == "stars"

    def test_is_channel_enabled_all_enabled(self):
        """Test is_channel_enabled with all channels enabled."""
        config = JobConfig(
            planner_features=PlannerFeatures(
                enable_shutter=True, enable_color=True, enable_gobo=True
            )
        )

        assert config.is_channel_enabled("shutter") is True
        assert config.is_channel_enabled("color") is True
        assert config.is_channel_enabled("gobo") is True

    def test_is_channel_enabled_mixed(self):
        """Test is_channel_enabled with mixed flags."""
        config = JobConfig(
            planner_features=PlannerFeatures(
                enable_shutter=True, enable_color=False, enable_gobo=True
            )
        )

        assert config.is_channel_enabled("shutter") is True
        assert config.is_channel_enabled("color") is False
        assert config.is_channel_enabled("gobo") is True

    def test_is_channel_enabled_all_disabled(self):
        """Test is_channel_enabled with all channels disabled."""
        config = JobConfig(
            planner_features=PlannerFeatures(
                enable_shutter=False, enable_color=False, enable_gobo=False
            )
        )

        assert config.is_channel_enabled("shutter") is False
        assert config.is_channel_enabled("color") is False
        assert config.is_channel_enabled("gobo") is False

    def test_is_channel_enabled_unknown_channel_raises(self):
        """Test unknown channel raises ValueError."""
        config = JobConfig()

        with pytest.raises(ValueError, match="Unknown channel: invalid"):
            config.is_channel_enabled("invalid")

    def test_channel_defaults_and_features_independent(self):
        """Test channel defaults and feature flags are independent."""
        config = JobConfig(
            channel_defaults=ChannelDefaults(shutter="strobe_fast", color="red", gobo="stars"),
            planner_features=PlannerFeatures(
                enable_shutter=False, enable_color=True, enable_gobo=False
            ),
        )

        # Defaults are set
        assert config.channel_defaults.shutter == "strobe_fast"
        assert config.channel_defaults.color == "red"
        assert config.channel_defaults.gobo == "stars"

        # But planning is disabled for shutter/gobo
        assert config.is_channel_enabled("shutter") is False
        assert config.is_channel_enabled("color") is True
        assert config.is_channel_enabled("gobo") is False


class TestChannelConfigValidation:
    """Test channel configuration validation."""

    def test_validate_valid_config(self):
        """Test validation passes for valid config."""
        config = JobConfig(
            channel_defaults=ChannelDefaults(shutter="open", color="blue", gobo="stars")
        )

        is_valid, errors = validate_channel_config(config)

        assert is_valid is True
        assert len(errors) == 0

    def test_validate_default_config(self):
        """Test validation passes for default config."""
        config = JobConfig()

        is_valid, errors = validate_channel_config(config)

        assert is_valid is True
        assert len(errors) == 0

    def test_validate_invalid_shutter(self):
        """Test validation fails for invalid shutter."""
        config = JobConfig(
            channel_defaults=ChannelDefaults(shutter="invalid_shutter", color="white", gobo="open")
        )

        is_valid, errors = validate_channel_config(config)

        assert is_valid is False
        assert len(errors) > 0
        assert any("shutter" in err.lower() for err in errors)

    def test_validate_invalid_color(self):
        """Test validation fails for invalid color."""
        config = JobConfig(
            channel_defaults=ChannelDefaults(shutter="open", color="invalid_color", gobo="open")
        )

        is_valid, errors = validate_channel_config(config)

        assert is_valid is False
        assert len(errors) > 0
        assert any("color" in err.lower() for err in errors)

    def test_validate_invalid_gobo(self):
        """Test validation fails for invalid gobo."""
        config = JobConfig(
            channel_defaults=ChannelDefaults(shutter="open", color="white", gobo="invalid_gobo")
        )

        is_valid, errors = validate_channel_config(config)

        assert is_valid is False
        assert len(errors) > 0
        assert any("gobo" in err.lower() for err in errors)

    def test_validate_multiple_invalid(self):
        """Test validation reports multiple errors."""
        config = JobConfig(
            channel_defaults=ChannelDefaults(
                shutter="invalid_shutter", color="invalid_color", gobo="invalid_gobo"
            )
        )

        is_valid, errors = validate_channel_config(config)

        assert is_valid is False
        assert len(errors) == 3  # All 3 should fail


class TestConfigurationExamples:
    """Test configuration examples from design doc."""

    def test_example_default_configuration(self):
        """Test default configuration example."""
        config_data = {
            "agent": {"max_iterations": 3, "token_budget": 150000},
            "channel_defaults": {"shutter": "open", "color": "white", "gobo": "open"},
        }

        config = JobConfig.model_validate(config_data)

        assert config.agent.max_iterations == 3
        assert config.channel_defaults.shutter == "open"

    def test_example_custom_channel_defaults(self):
        """Test custom channel defaults example."""
        config_data = {"channel_defaults": {"shutter": "open", "color": "blue", "gobo": "open"}}

        config = JobConfig.model_validate(config_data)

        assert config.channel_defaults.color == "blue"

    def test_example_disable_gobo_planning(self):
        """Test disable gobo planning example."""
        config_data = {
            "planner_features": {
                "enable_shutter": True,
                "enable_color": True,
                "enable_gobo": False,
            },
            "channel_defaults": {"shutter": "open", "color": "white", "gobo": "open"},
        }

        config = JobConfig.model_validate(config_data)

        assert config.is_channel_enabled("shutter") is True
        assert config.is_channel_enabled("color") is True
        assert config.is_channel_enabled("gobo") is False

    def test_example_movement_only(self):
        """Test movement only (no channels) example."""
        config_data = {
            "planner_features": {
                "enable_shutter": False,
                "enable_color": False,
                "enable_gobo": False,
            },
            "channel_defaults": {"shutter": "open", "color": "white", "gobo": "open"},
        }

        config = JobConfig.model_validate(config_data)

        assert config.is_channel_enabled("shutter") is False
        assert config.is_channel_enabled("color") is False
        assert config.is_channel_enabled("gobo") is False
