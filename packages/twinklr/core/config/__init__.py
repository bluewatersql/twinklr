"""Configuration management for Twinklr."""

from twinklr.core.config.fixtures import (
    ChannelInversions,
    DmxMapping,
    FixtureConfig,
    FixtureGroup,
    FixtureGroupBuilder,
    FixtureInstance,
    FixturePosition,
    MovementLimits,
    Orientation,
    PanTiltRange,
    Pose,
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
    "Orientation",
    "PanTiltRange",
    "Pose",
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
