"""Configuration management for BlinkB0t."""

from blinkb0t.core.config.fixtures import (
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
from blinkb0t.core.config.loader import (
    configure_logging,
    load_app_config,
    load_config,
    load_fixture_group,
    load_full_config,
    load_job_config,
)
from blinkb0t.core.config.models import (
    AppConfig,
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
