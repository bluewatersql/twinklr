"""Configuration management for Twinklr."""

from twinklr.core.config.fixtures import (
    DmxMapping,
    FixtureConfig,
    FixtureGroup,
    FixtureGroupBuilder,
    FixtureInstance,
    FixturePosition,
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
from twinklr.core.config.render_policy import (
    UnsupportedRenderModeError,
    preflight_render_policy,
)

__all__ = [
    # App-level config
    "AppConfig",
    "AudioEnhancementConfig",
    "AudioProcessingConfig",
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
    "RhythmSourceName",
    "StructureSourceName",
    "UnsupportedRenderModeError",
    "load_app_config",
    # Loaders
    "load_config",
    "load_fixture_group",
    "load_full_config",
    "load_job_config",
    "preflight_render_policy",
]
