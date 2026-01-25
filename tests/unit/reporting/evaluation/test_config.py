"""Tests for evaluation configuration model."""

from pydantic import ValidationError
import pytest

from blinkb0t.core.reporting.evaluation.config import EvalConfig


class TestEvalConfig:
    """Tests for EvalConfig model."""

    def test_default_config(self):
        """Test creating config with default values."""
        config = EvalConfig()
        assert config.samples_per_bar == 96
        assert config.clamp_warning_threshold == 0.05
        assert config.clamp_error_threshold == 0.20
        assert config.loop_delta_threshold == 0.05
        assert config.gap_warning_bars == 0.5
        assert config.max_concurrent_layers == 3
        assert config.roles_to_plot is None
        assert config.plot_all_roles is False
        assert config.include_dmx_plots is False
        assert "json" in config.output_format
        assert "md" in config.output_format

    def test_custom_sampling(self):
        """Test config with custom sampling rate."""
        config = EvalConfig(samples_per_bar=128)
        assert config.samples_per_bar == 128

    def test_custom_thresholds(self):
        """Test config with custom thresholds."""
        config = EvalConfig(
            clamp_warning_threshold=0.10,
            clamp_error_threshold=0.25,
            loop_delta_threshold=0.10,
        )
        assert config.clamp_warning_threshold == 0.10
        assert config.clamp_error_threshold == 0.25
        assert config.loop_delta_threshold == 0.10

    def test_plot_specific_roles(self):
        """Test config with specific roles to plot."""
        config = EvalConfig(roles_to_plot=["OUTER_LEFT", "CENTER"])
        assert config.roles_to_plot == ["OUTER_LEFT", "CENTER"]
        assert config.plot_all_roles is False

    def test_plot_all_roles(self):
        """Test config with plot_all_roles enabled."""
        config = EvalConfig(plot_all_roles=True)
        assert config.plot_all_roles is True

    def test_output_formats(self):
        """Test config with custom output formats."""
        config = EvalConfig(output_format=["json", "md", "html"])
        assert "json" in config.output_format
        assert "md" in config.output_format
        assert "html" in config.output_format

    def test_validation_samples_per_bar(self):
        """Test validation of samples_per_bar."""
        with pytest.raises(ValidationError):
            EvalConfig(samples_per_bar=0)  # Must be >= 1

    def test_validation_clamp_thresholds(self):
        """Test validation of clamp thresholds."""
        with pytest.raises(ValidationError):
            EvalConfig(clamp_warning_threshold=1.5)  # Must be <= 1.0

        with pytest.raises(ValidationError):
            EvalConfig(clamp_warning_threshold=-0.1)  # Must be >= 0.0

    def test_validation_max_concurrent_layers(self):
        """Test validation of max_concurrent_layers."""
        with pytest.raises(ValidationError):
            EvalConfig(max_concurrent_layers=0)  # Must be >= 1

    def test_config_is_frozen(self):
        """Test that config is immutable."""
        config = EvalConfig()
        with pytest.raises(ValidationError):
            config.samples_per_bar = 200  # type: ignore

    def test_serialization(self):
        """Test config serialization."""
        config = EvalConfig(samples_per_bar=128, plot_all_roles=True)
        data = config.model_dump()

        assert data["samples_per_bar"] == 128
        assert data["plot_all_roles"] is True

    def test_deserialization(self):
        """Test config deserialization."""
        data = {
            "samples_per_bar": 128,
            "clamp_warning_threshold": 0.10,
            "plot_all_roles": True,
            "output_format": ["json"],
        }
        config = EvalConfig.model_validate(data)

        assert config.samples_per_bar == 128
        assert config.clamp_warning_threshold == 0.10
        assert config.plot_all_roles is True
