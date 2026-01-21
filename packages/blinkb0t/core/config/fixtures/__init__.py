"""Type-safe fixture configuration models.

Industry-standard Pydantic models for moving head fixture configuration.
Provides clear separation of concerns, sensible defaults, and type safety.

Design Principles:
- Pydantic for validation and serialization
- Sensible defaults (system works with minimal config)
- Type-safe conversions (DMX ↔ degrees)
- Clear separation: DMX, physical, capabilities, orientation
- Standard poses for common positions

This package is organized into focused modules:
- dmx: DMX channel configuration and mapping
- physical: Physical movement and orientation
- capabilities: Fixture capabilities and performance specs
- instances: Fixture instances, configurations, and poses
- groups: Fixture grouping and batch configuration
"""

from __future__ import annotations

# Capabilities module exports
from blinkb0t.core.config.fixtures.capabilities import (
    FixtureCapabilities,
    MovementSpeed,
)
from blinkb0t.core.config.fixtures.dmx import (
    ChannelInversions,
    ChannelWithConfig,
    DmxChannelConfig,
    DmxMapping,
    ShutterMap,
)

# Groups module exports
from blinkb0t.core.config.fixtures.groups import (
    BaseFixtureConfig,
    FixtureGroup,
    FixtureGroupBuilder,
    SimplifiedFixtureInstance,
)

# Instances module exports
from blinkb0t.core.config.fixtures.instances import (
    FixtureConfig,
    FixtureInstance,
    FixturePosition,
    Pose,
)

# Physical module exports
from blinkb0t.core.config.fixtures.physical import (
    MovementLimits,
    Orientation,
    PanTiltRange,
    RestingPosition,
)

__all__ = [
    # DMX
    "ChannelInversions",
    "ChannelWithConfig",
    "DmxChannelConfig",
    "DmxMapping",
    "ShutterMap",
    # Physical
    "MovementLimits",
    "Orientation",
    "PanTiltRange",
    "RestingPosition",
    # Capabilities
    "FixtureCapabilities",
    "MovementSpeed",
    # Instances
    "FixtureConfig",
    "FixtureInstance",
    "FixturePosition",
    "Pose",
    # Groups
    "BaseFixtureConfig",
    "FixtureGroup",
    "FixtureGroupBuilder",
    "SimplifiedFixtureInstance",
]
