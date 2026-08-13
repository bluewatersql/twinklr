"""Shared enums for profiling models.

Use enums for categorical values that are reused, filtered, joined, or passed
between profiling components.
"""

from __future__ import annotations

from enum import StrEnum


class FileKind(StrEnum):
    """Classified file kind in a sequence package."""

    SEQUENCE = "sequence"
    RGB_EFFECTS = "rgb_effects"
    ASSET = "asset"
    SHADER = "shader"
    OTHER = "other"


class StartChannelFormat(StrEnum):
    """Start-channel format parsed from xLights layout models."""

    UNIVERSE_CHANNEL = "universe:channel"
    CHAINED = "chained"
    ABSOLUTE = "absolute"


class ModelCategory(StrEnum):
    """Top-level category for a layout model."""

    DISPLAY = "display"
    DMX_FIXTURE = "dmx_fixture"
    AUXILIARY = "auxiliary"
    INACTIVE = "inactive"


class SemanticSize(StrEnum):
    """Coarse semantic size classification for display models."""

    MEGA = "mega"
    MINI = "mini"


class ParameterValueType(StrEnum):
    """Inferred scalar type for an EffectDB parameter value."""

    INT = "int"
    FLOAT = "float"
    BOOL = "bool"
    STRING = "string"
    EMPTY = "empty"


class TargetKind(StrEnum):
    """Join result kind when mapping effect targets to layout entries."""

    MODEL = "model"
    GROUP = "group"
    UNKNOWN = "unknown"


class EffectDbNamespace(StrEnum):
    """Namespace prefix of an EffectDB parameter key."""

    E = "E"
    B = "B"
    T = "T"
    UNKNOWN = "UNKNOWN"


class EffectDbControlType(StrEnum):
    """Control type segment of an EffectDB parameter key."""

    SLIDER = "SLIDER"
    CHECKBOX = "CHECKBOX"
    CHOICE = "CHOICE"
    TEXTCTRL = "TEXTCTRL"
    VALUECURVE = "VALUECURVE"
    UNKNOWN = "UNKNOWN"


class EffectDbParseStatus(StrEnum):
    """Parse status for an EffectDB settings payload."""

    PARSED = "parsed"
    PARTIAL = "partial"
    FAILED = "failed"
    EMPTY = "empty"
