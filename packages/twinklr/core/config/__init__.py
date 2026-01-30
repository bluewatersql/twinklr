"""Configuration management for Twinklr."""

from twinklr.core.config.fixtures import (
    ChannelInversions,
    DmxMapping,
    FixtureCapabilities,
    FixtureConfig,
    FixtureGroup,
    FixtureGroupBuilder,
    FixtureInstance,
    FixturePosition,
    MovementLimits,
    MovementSpeed,
    Orientation,
    PanTiltRange,
    Pose,
    RestingPosition,
    ShutterMap,
)
from twinklr.core.config.loader import (
    configure_logging,
    load_app_config,
    load_config,
    load_fixture_group,
    load_full_config,
    load_job_config,
)
from twinklr.core.config.models import (
    AppConfig,
    AudioEnhancementConfig,
    AudioProcessingConfig,
    JobConfig,
    LoggingConfig,
    PlanningContextConfig,
)

__all__ = [
    # Loaders
    "load_config",
    "load_app_config",
    "load_job_config",
    "load_fixture_group",
    "load_full_config",
    "configure_logging",
    # App-level config
    "AppConfig",
    "AudioProcessingConfig",
    "AudioEnhancementConfig",
    "LoggingConfig",
    "PlanningContextConfig",
    # Job-level config
    "JobConfig",
    # Fixture config
    "FixtureGroup",
    "FixtureConfig",
    "FixtureInstance",
    "FixtureGroupBuilder",
    "FixturePosition",
    "Pose",
    "DmxMapping",
    "ChannelInversions",
    "ShutterMap",
    "PanTiltRange",
    "Orientation",
    "RestingPosition",
    "MovementLimits",
    "MovementSpeed",
    "FixtureCapabilities",
]
