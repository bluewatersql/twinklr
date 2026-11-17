"""Type-safe fixture configuration models.

Industry-standard Pydantic models for moving head fixture configuration.
Provides clear separation of concerns, sensible defaults, and type safety.

This package is organized into focused modules:
- dmx: DMX channel assignments
- removed_fields: Retired and removed fixture-config fields
- instances: Fixture instances and their configurations
- groups: Fixture grouping and batch configuration
- capabilities: Explicit physical profiles and run initial state
"""

from __future__ import annotations

# Capabilities module exports
from twinklr.core.config.fixtures.capabilities import (
    AxisCapability,
    DiscreteCapability,
    DiscreteState,
    FixtureCapabilities,
    InitialFixtureState,
    VisibilityCapability,
)
from twinklr.core.config.fixtures.dmx import (
    ChannelWithConfig,
    DmxMapping,
)

# Groups module exports
from twinklr.core.config.fixtures.groups import (
    BaseFixtureConfig,
    FixtureGroup,
    FixtureGroupBuilder,
    SimplifiedFixtureInstance,
)

# Instances module exports
from twinklr.core.config.fixtures.instances import (
    FixtureConfig,
    FixtureInstance,
    FixturePosition,
)

__all__ = [
    # Capabilities
    "AxisCapability",
    # Groups
    "BaseFixtureConfig",
    # DMX
    "ChannelWithConfig",
    "DiscreteCapability",
    "DiscreteState",
    "DmxMapping",
    "FixtureCapabilities",
    # Instances
    "FixtureConfig",
    "FixtureGroup",
    "FixtureGroupBuilder",
    "FixtureInstance",
    "FixturePosition",
    "InitialFixtureState",
    "SimplifiedFixtureInstance",
    "VisibilityCapability",
]
