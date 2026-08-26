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
    RhythmSourceName,
    StructureSourceName,
)

__all__ = [
    # App-level config
    "AppConfig",
    "AudioEnhancementConfig",
    "AudioProcessingConfig",
    "ChannelInversions",
    "DmxMapping",
    "FixtureCapabilities",
    "FixtureConfig",
    # Fixture config
    "FixtureGroup",
    "FixtureGroupBuilder",
    "FixtureInstance",
    "FixturePosition",
    # Job-level config
    "JobConfig",
    "LoggingConfig",
    "MovementLimits",
    "MovementSpeed",
    "Orientation",
    "PanTiltRange",
    "PlanningContextConfig",
    "Pose",
    "RestingPosition",
    "RhythmSourceName",
    "ShutterMap",
    "StructureSourceName",
    "load_app_config",
    # Loaders
    "load_config",
    "load_fixture_group",
    "load_full_config",
    "load_job_config",
]
