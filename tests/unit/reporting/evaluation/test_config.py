"""Tests for evaluation configuration model."""

from pydantic import ValidationError
import pytest

from twinklr.core.reporting.evaluation.config import EvalConfig


class TestEvalConfig:
    """Tests for EvalConfig model."""

    def test_default_config(self):
        """Test creating config with default values."""
        config = EvalConfig()
        assert config.gap_warning_bars == 0.5
        assert config.max_concurrent_layers == 3
        assert config.roles_to_plot is None
        assert config.plot_all_roles is False
        assert config.include_dmx_plots is False
        assert "json" in config.output_format
        assert "md" in config.output_format

    def test_output_formats(self):
        """Test config with custom output formats."""
        config = EvalConfig(output_format=["json", "md", "html"])
        assert "json" in config.output_format
        assert "md" in config.output_format
        assert "html" in config.output_format

    def test_validation_max_concurrent_layers(self):
        """Test validation of max_concurrent_layers."""
        with pytest.raises(ValidationError):
            EvalConfig(max_concurrent_layers=0)  # Must be >= 1

    def test_deserialization(self):
        """Test config deserialization."""
        data = {
            "gap_warning_bars": 1.0,
            "plot_all_roles": True,
            "output_format": ["json"],
        }
        config = EvalConfig.model_validate(data)

        assert config.gap_warning_bars == 1.0
        assert config.plot_all_roles is True
