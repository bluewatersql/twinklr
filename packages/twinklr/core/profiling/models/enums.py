"""Shared enums for profiling models.

Use enums for categorical values that are reused, filtered, joined, or passed
between profiling components.
"""

from __future__ import annotations

from enum import Enum


class FileKind(str, Enum):
    """Classified file kind in a sequence package."""

    SEQUENCE = "sequence"
    RGB_EFFECTS = "rgb_effects"
    ASSET = "asset"
    SHADER = "shader"
    OTHER = "other"


class StartChannelFormat(str, Enum):
    """Start-channel format parsed from xLights layout models."""

    UNIVERSE_CHANNEL = "universe:channel"
    CHAINED = "chained"
    ABSOLUTE = "absolute"


class ModelCategory(str, Enum):
    """Top-level category for a layout model."""

    DISPLAY = "display"
    DMX_FIXTURE = "dmx_fixture"
    AUXILIARY = "auxiliary"
    INACTIVE = "inactive"


class SemanticSize(str, Enum):
    """Coarse semantic size classification for display models."""

    MEGA = "mega"
    MINI = "mini"


class ParameterValueType(str, Enum):
    """Inferred scalar type for an EffectDB parameter value."""

    INT = "int"
    FLOAT = "float"
    BOOL = "bool"
    STRING = "string"
    EMPTY = "empty"


class TargetKind(str, Enum):
    """Join result kind when mapping effect targets to layout entries."""

    MODEL = "model"
    GROUP = "group"
    UNKNOWN = "unknown"
