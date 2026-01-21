"""Shared models for movement patterns.

Contains MovementID enum, CategoricalParams, and MovementPattern models used across all movement categories.
"""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, ConfigDict, Field

from blinkb0t.core.domains.sequencing.libraries.moving_heads.base import (
    AlternativeCurve,
    CategoricalIntensity,
    CurveMapping,
)


class MovementID(str, Enum):
    """All available movement pattern identifiers.

    This enum provides type-safe movement IDs that can be validated at
    compile time. Templates reference these IDs instead of strings.
    """

    # Core patterns
    SWEEP_LR = "sweep_lr"
    SWEEP_UD = "sweep_ud"
    CIRCLE = "circle"
    FIGURE8 = "figure8"
    INFINITY = "infinity"
    HOLD = "hold"
    RANDOM_WALK = "random_walk"

    # Shake patterns
    PAN_SHAKE = "pan_shake"
    TILT_ROCK = "tilt_rock"
    BOUNCE = "bounce"
    PENDULUM = "pendulum"
    TILT_BOUNCE = "tilt_bounce"
    GROOVE_SWAY = "groove_sway"

    # Accent patterns
    ACCENT_SNAP = "accent_snap"
    POP_LOCK = "pop_lock"
    LASER_SNAP = "laser_snap"
    HIT = "hit"
    STOMP = "stomp"

    # Wave and complex patterns
    WAVE_HORIZONTAL = "wave_horizontal"
    WAVE_VERTICAL = "wave_vertical"
    ZIGZAG = "zigzag"
    SPIRAL = "spiral"
    DIAGONAL_SWEEP = "diagonal_sweep"
    CORNER_TO_CORNER = "corner_to_corner"
    DUAL_SWEEP = "dual_sweep"
    FAN_IRIS = "fan_iris"
    RADIAL_FAN = "radial_fan"
    TRAMPOLINE = "trampoline"
    CROSS_PATTERN = "cross_pattern"


class CategoricalParams(BaseModel):
    """Categorical parameters for a specific intensity level.

    Maps categorical intensity (SMOOTH, DRAMATIC, etc.) to numeric
    curve parameters (amplitude, frequency, center).
    """

    model_config = ConfigDict(frozen=True)

    amplitude: float = Field(ge=0.0, le=1.0)
    frequency: float = Field(
        ge=0.0, le=10.0
    )  # Increased to 10.0 for high-speed movements like PAN_SHAKE
    center: int = Field(default=128, ge=0, le=255)


class MovementPattern(BaseModel):
    """Complete movement pattern definition.

    Defines a single movement pattern with its curve mappings,
    categorical parameters, and metadata.
    """

    model_config = ConfigDict(frozen=True)

    id: MovementID
    name: str
    description: str
    expected_behavior: str

    primary_curve: CurveMapping
    base_params: dict[str, float | int | str] = Field(default_factory=dict)
    categorical_params: dict[CategoricalIntensity, CategoricalParams]
    alternatives: list[AlternativeCurve] = Field(default_factory=list)


# Default categorical params (3-level system with better spacing)
DEFAULT_CATEGORICAL_PARAMS = {
    CategoricalIntensity.SMOOTH: CategoricalParams(amplitude=0.3, frequency=0.5, center=128),
    CategoricalIntensity.DRAMATIC: CategoricalParams(amplitude=0.65, frequency=1.5, center=128),
    CategoricalIntensity.INTENSE: CategoricalParams(amplitude=0.95, frequency=2.5, center=128),
}
