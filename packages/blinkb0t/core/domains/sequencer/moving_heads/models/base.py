"""Sequencing v2 core models (Step 1 – MVP).

This module defines the foundational Pydantic models for a clean,
compiler-based moving-head sequencing architecture.

Guiding principles implemented here:
- Fixtures, groups, and orders are *rig config* (not templates)
- Pydantic for all models
- Validation ensures config correctness early
- Models are data-only (no rendering); helpers are minimal and side-effect free

You can drop this into your repo and wire it up via DI.
"""

from __future__ import annotations

from enum import Enum


class ChannelName(str, Enum):
    PAN = "PAN"
    TILT = "TILT"
    DIMMER = "DIMMER"


class BlendMode(str, Enum):
    OVERRIDE = "OVERRIDE"
    ADD = "ADD"
    MULTIPLY = "MULTIPLY"
    MAX = "MAX"


class Category(str, Enum):
    LOW_ENERGY = "low_energy"
    MEDIUM_ENERGY = "medium_energy"
    HIGH_ENERGY = "high_energy"


class TimingMode(str, Enum):
    MUSICAL = "musical"


class QuantizePoint(str, Enum):
    DOWNBEAT = "downbeat"
    BEAT = "beat"
    BAR = "bar"
    NONE = "none"


class TransitionMode(str, Enum):
    """Transition blending modes."""

    SNAP = "snap"
    CROSSFADE = "crossfade"
    FADE_THROUGH_BLACK = "fade_through_black"


class RepeatMode(str, Enum):
    CLOSED = "CLOSED"
    PING_PONG = "PING_PONG"
    JOINER = "JOINER"


class RemainderPolicy(str, Enum):
    HOLD_LAST_POSE = "HOLD_LAST_POSE"
    TRUNCATE_LAST = "TRUNCATE_LAST"
    RESAMPLE_TIME = "RESAMPLE_TIME"
    APPEND_EXIT_STEP = "APPEND_EXIT_STEP"


class BoundaryTransition(str, Enum):
    CONTINUOUS = "CONTINUOUS"
    JOINED = "JOINED"


class PhaseUnit(str, Enum):
    BARS = "bars"


class PhaseOffsetMode(str, Enum):
    NONE = "NONE"
    GROUP_ORDER = "GROUP_ORDER"


class OrderMode(str, Enum):
    LEFT_TO_RIGHT = "LEFT_TO_RIGHT"
    RIGHT_TO_LEFT = "RIGHT_TO_LEFT"
    OUTSIDE_IN = "OUTSIDE_IN"
    INSIDE_OUT = "INSIDE_OUT"
    ODD_EVEN = "ODD_EVEN"
    EVEN_ODD = "EVEN_ODD"


class SemanticGroup(str, Enum):
    ALL = "ALL"
    LEFT = "LEFT"
    RIGHT = "RIGHT"
    INNER = "INNER"
    OUTER = "OUTER"
    ODD = "ODD"
    EVEN = "EVEN"


class Distribution(str, Enum):
    LINEAR = "LINEAR"


class AimZone(str, Enum):
    SKY = "SKY"
    HORIZON = "HORIZON"
    CROWD = "CROWD"
    STAGE = "STAGE"


class TemplateRole(str, Enum):
    OUTER_LEFT = "OUTER_LEFT"
    INNER_LEFT = "INNER_LEFT"
    INNER_RIGHT = "INNER_RIGHT"
    OUTER_RIGHT = "OUTER_RIGHT"
    FAR_LEFT = "FAR_LEFT"
    FAR_RIGHT = "FAR_RIGHT"
    MID_LEFT = "MID_LEFT"
    MID_RIGHT = "MID_RIGHT"
    CENTER_LEFT = "CENTER_LEFT"
    CENTER_RIGHT = "CENTER_RIGHT"
    CENTER = "CENTER"


class IntensityLevel(str, Enum):
    SMOOTH = "smooth"  # Gentle, gradual transitions (20-40% intensity)
    DRAMATIC = "dramatic"  # Strong, impactful movements (50-75% intensity)
    INTENSE = "intense"  # Maxed-out, maximum intensity (90-100% intensity)
