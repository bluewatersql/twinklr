"""Phase F integration tests for config options and corpus artifact wiring."""

from __future__ import annotations

from twinklr.core.feature_engineering.config import FeatureEngineeringPipelineOptions


def test_config_has_enable_active_learning() -> None:
    """Config has enable_active_learning field defaulting to False."""
    opts = FeatureEngineeringPipelineOptions()
    assert hasattr(opts, "enable_active_learning")
    assert opts.enable_active_learning is False


def test_config_has_enable_transition_v2() -> None:
    """Config has enable_transition_v2 field defaulting to True."""
    opts = FeatureEngineeringPipelineOptions()
    assert hasattr(opts, "enable_transition_v2")
    assert opts.enable_transition_v2 is True


def test_config_active_learning_can_be_enabled() -> None:
    """Config allows enabling active learning."""
    opts = FeatureEngineeringPipelineOptions(enable_active_learning=True)
    assert opts.enable_active_learning is True


def test_config_transition_v2_can_be_disabled() -> None:
    """Config allows disabling transition V2."""
    opts = FeatureEngineeringPipelineOptions(enable_transition_v2=False)
    assert opts.enable_transition_v2 is False
