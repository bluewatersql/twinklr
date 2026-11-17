"""Movement identifiers `TemplateStep.movement` validates."""

from __future__ import annotations

from enum import StrEnum


class MovementType(StrEnum):
    """All available movement pattern identifiers."""

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
    TRAMPOLINE = "trampoline"

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
    CROSS_PATTERN = "cross_pattern"

    NONE = "none"
