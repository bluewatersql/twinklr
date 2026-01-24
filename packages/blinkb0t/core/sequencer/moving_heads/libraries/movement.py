from __future__ import annotations

import math
from enum import Enum

from blinkb0t.core.curves.library import CurveLibrary
from blinkb0t.core.sequencer.models.enum import Intensity
from blinkb0t.core.sequencer.moving_heads.libraries.geometry import GeometryType
from pydantic import BaseModel, ConfigDict, Field


class MovementCategoricalParams(BaseModel):
    """Categorical parameters for movement intensity levels."""

    model_config = ConfigDict(frozen=True)

    amplitude: float = Field(ge=0.0, le=1.0, description="Movement amplitude [0,1]")
    frequency: float = Field(ge=0.0, le=10.0, description="Movement frequency [0,10]")
    center: int = Field(default=128, ge=0, le=255, description="Center DMX value")


class MovementFlags(BaseModel):
    model_config = ConfigDict(extra="forbid")

    disable_geometry_overrides: bool = False


class MovementPattern(BaseModel):
    """Definition of a movement pattern."""

    model_config = ConfigDict(frozen=True)

    id: str
    name: str
    description: str

    pan_curve: CurveLibrary
    base_tilt_curve: CurveLibrary
    base_params: dict[str, float | int | str] = Field(default_factory=dict)
    categorical_params: dict[Intensity, MovementCategoricalParams]
    flags: MovementFlags = Field(default_factory=MovementFlags)
    geometry_modifiers: dict[GeometryType, CurveLibrary] = Field(default_factory=dict)

    def resolve_tilt_curve(self, geometry_type: GeometryType) -> CurveLibrary:
        """Resolve tilt curve based on geometry type.

        Args:
            geometry_type: Geometry type.
        """
        if self.flags.disable_geometry_overrides:
            return self.base_tilt_curve

        if geometry_type in self.geometry_modifiers:
            return self.geometry_modifiers[geometry_type]

        return self.base_tilt_curve


DEFAULT_MOVEMENT_PARAMS = {
    Intensity.SMOOTH: MovementCategoricalParams(amplitude=0.3, frequency=0.5, center=128),
    Intensity.DRAMATIC: MovementCategoricalParams(amplitude=0.65, frequency=1.5, center=128),
}


class MovementType(str, Enum):
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


class MovementLibrary:
    """Library of predefined movement patterns."""

    PATTERNS: dict[MovementType, MovementPattern] = {
        # ============================================================================
        # Core Patterns
        # ============================================================================
        MovementType.SWEEP_LR: MovementPattern(
            id="sweep_lr",
            name="Left/Right Sweep",
            description="Smooth horizontal sweep across the performance space",
            pan_curve=CurveLibrary.MOVEMENT_TRIANGLE,
            base_tilt_curve=CurveLibrary.MOVEMENT_HOLD,
            base_params={"amplitude": 0.8, "center": 128, "frequency": 1.0},
            geometry_modifiers={GeometryType.SCATTERED_CHAOS: CurveLibrary.MOVEMENT_PERLIN_NOISE},
            categorical_params={
                Intensity.SMOOTH: MovementCategoricalParams(
                    amplitude=0.3, frequency=0.5, center=128
                ),
                Intensity.DRAMATIC: MovementCategoricalParams(
                    amplitude=0.6, frequency=1.25, center=128
                ),
            },
        ),
        MovementType.SWEEP_UD: MovementPattern(
            id="sweep_ud",
            name="Up/Down Sweep",
            description="Smooth vertical sweep across the performance space",
            pan_curve=CurveLibrary.MOVEMENT_HOLD,
            base_tilt_curve=CurveLibrary.MOVEMENT_TRIANGLE,
            base_params={"amplitude": 0.6, "center": 128, "frequency": 1.0},
            categorical_params={
                Intensity.SMOOTH: MovementCategoricalParams(
                    amplitude=0.3, frequency=0.5, center=128
                ),
                Intensity.DRAMATIC: MovementCategoricalParams(
                    amplitude=0.6, frequency=1.25, center=128
                ),
            },
        ),
        MovementType.CIRCLE: MovementPattern(
            id="circle",
            name="Circular Motion",
            description="Pan and tilt coordinated for circular path",
            pan_curve=CurveLibrary.MOVEMENT_SINE,
            base_tilt_curve=CurveLibrary.MOVEMENT_COSINE,
            base_params={"amplitude": 0.7, "frequency": 1.0, "center": 128},
            categorical_params={
                Intensity.SMOOTH: MovementCategoricalParams(
                    amplitude=0.3, frequency=0.5, center=128
                ),
                Intensity.DRAMATIC: MovementCategoricalParams(
                    amplitude=0.6, frequency=1.25, center=128
                ),
            },
        ),
        MovementType.FIGURE8: MovementPattern(
            id="figure8",
            name="Figure-8 Pattern",
            description="Creates figure-8 or infinity symbol pattern",
            pan_curve=CurveLibrary.MOVEMENT_LISSAJOUS,
            base_tilt_curve=CurveLibrary.MOVEMENT_LISSAJOUS,
            base_params={
                "amplitude": 0.7,
                "frequency": 1.0,
                "center": 128,
                "curve_tilt_b": 2,
                "curve_tilt_delta": math.pi / 2,
            },
            categorical_params={
                Intensity.SMOOTH: MovementCategoricalParams(
                    amplitude=0.3, frequency=0.5, center=128
                ),
                Intensity.DRAMATIC: MovementCategoricalParams(
                    amplitude=0.6, frequency=1.25, center=128
                ),
            },
        ),
        MovementType.INFINITY: MovementPattern(
            id="infinity",
            name="Infinity Symbol",
            description="Infinity/figure-8 pattern",
            pan_curve=CurveLibrary.MOVEMENT_LISSAJOUS,
            base_tilt_curve=CurveLibrary.MOVEMENT_LISSAJOUS,
            base_params={},
            categorical_params={
                Intensity.SMOOTH: MovementCategoricalParams(
                    amplitude=0.3, frequency=0.5, center=128
                ),
                Intensity.DRAMATIC: MovementCategoricalParams(
                    amplitude=0.525, frequency=0.95, center=128
                ),
            },
        ),
        MovementType.HOLD: MovementPattern(
            id="hold",
            name="Hold Position",
            description="Maintain current position (no movement)",
            pan_curve=CurveLibrary.MOVEMENT_HOLD,
            base_tilt_curve=CurveLibrary.MOVEMENT_HOLD,
            base_params={},
            categorical_params={
                Intensity.SMOOTH: MovementCategoricalParams(
                    amplitude=0.0, frequency=0.0, center=128
                ),
                Intensity.DRAMATIC: MovementCategoricalParams(
                    amplitude=0.0, frequency=0.0, center=128
                ),
            },
        ),
        MovementType.RANDOM_WALK: MovementPattern(
            id="random_walk",
            name="Random Walk",
            description="Organic random movement",
            pan_curve=CurveLibrary.MOVEMENT_PERLIN_NOISE,
            base_tilt_curve=CurveLibrary.MOVEMENT_PERLIN_NOISE,
            base_params={},
            categorical_params={
                Intensity.SMOOTH: MovementCategoricalParams(
                    amplitude=0.2, frequency=0.3, center=128
                ),
                Intensity.DRAMATIC: MovementCategoricalParams(
                    amplitude=0.425, frequency=0.75, center=128
                ),
            },
        ),
        # ============================================================================
        # Shake Patterns
        # ============================================================================
        MovementType.PAN_SHAKE: MovementPattern(
            id="pan_shake",
            name="Pan Shake",
            description="Horizontal shake/vibrate",
            pan_curve=CurveLibrary.MOVEMENT_TRIANGLE,
            base_tilt_curve=CurveLibrary.MOVEMENT_HOLD,
            base_params={},
            geometry_modifiers={GeometryType.SCATTERED_CHAOS: CurveLibrary.MOVEMENT_PERLIN_NOISE},
            categorical_params={
                Intensity.SMOOTH: MovementCategoricalParams(
                    amplitude=0.15, frequency=2.0, center=128
                ),
                Intensity.DRAMATIC: MovementCategoricalParams(
                    amplitude=0.32, frequency=4.25, center=128
                ),
            },
        ),
        MovementType.TILT_ROCK: MovementPattern(
            id="tilt_rock",
            name="Tilt Rock",
            description="Vertical rocking motion",
            pan_curve=CurveLibrary.MOVEMENT_HOLD,
            base_tilt_curve=CurveLibrary.MOVEMENT_SINE,
            base_params={},
            categorical_params={
                Intensity.SMOOTH: MovementCategoricalParams(
                    amplitude=0.2, frequency=0.5, center=128
                ),
                Intensity.DRAMATIC: MovementCategoricalParams(
                    amplitude=0.39, frequency=1.05, center=128
                ),
            },
        ),
        MovementType.BOUNCE: MovementPattern(
            id="bounce",
            name="Bounce",
            description="Bouncing motion with decay",
            pan_curve=CurveLibrary.MOVEMENT_TRIANGLE,
            base_tilt_curve=CurveLibrary.MOVEMENT_TRIANGLE,
            base_params={},
            categorical_params={
                Intensity.SMOOTH: MovementCategoricalParams(
                    amplitude=0.3, frequency=0.8, center=128
                ),
                Intensity.DRAMATIC: MovementCategoricalParams(
                    amplitude=0.525, frequency=1.65, center=128
                ),
            },
        ),
        MovementType.PENDULUM: MovementPattern(
            id="pendulum",
            name="Pendulum",
            description="Pendulum swing motion",
            pan_curve=CurveLibrary.MOVEMENT_SINE,
            base_tilt_curve=CurveLibrary.MOVEMENT_HOLD,
            base_params={},
            geometry_modifiers={GeometryType.SCATTERED_CHAOS: CurveLibrary.MOVEMENT_PERLIN_NOISE},
            categorical_params={
                Intensity.SMOOTH: MovementCategoricalParams(
                    amplitude=0.3, frequency=0.3, center=128
                ),
                Intensity.DRAMATIC: MovementCategoricalParams(
                    amplitude=0.485, frequency=0.75, center=128
                ),
            },
        ),
        MovementType.TILT_BOUNCE: MovementPattern(
            id="tilt_bounce",
            name="Tilt Bounce",
            description="Vertical bounce (trampoline, stomp)",
            pan_curve=CurveLibrary.MOVEMENT_HOLD,
            base_tilt_curve=CurveLibrary.MOVEMENT_TRIANGLE,
            base_params={"amplitude": 0.8, "center": 128, "frequency": 1.0},
            categorical_params={
                Intensity.SMOOTH: MovementCategoricalParams(
                    amplitude=0.3, frequency=0.5, center=128
                ),
                Intensity.DRAMATIC: MovementCategoricalParams(
                    amplitude=0.6, frequency=1.25, center=128
                ),
            },
        ),
        MovementType.GROOVE_SWAY: MovementPattern(
            id="groove_sway",
            name="Groove Sway",
            description="Subtle organic sway (breathing)",
            pan_curve=CurveLibrary.MOVEMENT_PERLIN_NOISE,
            base_tilt_curve=CurveLibrary.MOVEMENT_PERLIN_NOISE,
            base_params={"amplitude": 0.5, "center": 128, "frequency": 0.8},
            categorical_params={
                Intensity.SMOOTH: MovementCategoricalParams(
                    amplitude=0.3, frequency=0.5, center=128
                ),
                Intensity.DRAMATIC: MovementCategoricalParams(
                    amplitude=0.6, frequency=1.25, center=128
                ),
            },
        ),
        MovementType.TRAMPOLINE: MovementPattern(
            id="trampoline",
            name="Trampoline",
            description="Gentle bounce (floating)",
            pan_curve=CurveLibrary.MOVEMENT_HOLD,
            base_tilt_curve=CurveLibrary.MOVEMENT_TRIANGLE,
            base_params={"amplitude": 0.7, "center": 128, "frequency": 1.0},
            categorical_params={
                Intensity.SMOOTH: MovementCategoricalParams(
                    amplitude=0.3, frequency=0.5, center=128
                ),
                Intensity.DRAMATIC: MovementCategoricalParams(
                    amplitude=0.6, frequency=1.25, center=128
                ),
            },
        ),
        # ============================================================================
        # Accent Patterns
        # ============================================================================
        MovementType.ACCENT_SNAP: MovementPattern(
            id="accent_snap",
            name="Accent Snap",
            description="Sharp snap to accent beat",
            pan_curve=CurveLibrary.MOVEMENT_HOLD,
            base_tilt_curve=CurveLibrary.MOVEMENT_HOLD,
            base_params={},
            geometry_modifiers={GeometryType.SCATTERED_CHAOS: CurveLibrary.MOVEMENT_PERLIN_NOISE},
            categorical_params={
                Intensity.SMOOTH: MovementCategoricalParams(
                    amplitude=0.4, frequency=0.5, center=128
                ),
                Intensity.DRAMATIC: MovementCategoricalParams(
                    amplitude=0.625, frequency=1.05, center=128
                ),
            },
        ),
        MovementType.POP_LOCK: MovementPattern(
            id="pop_lock",
            name="Pop Lock",
            description="Sharp snap to positions",
            pan_curve=CurveLibrary.MOVEMENT_PULSE,
            base_tilt_curve=CurveLibrary.MOVEMENT_PULSE,
            base_params={},
            categorical_params={
                Intensity.SMOOTH: MovementCategoricalParams(
                    amplitude=0.3, frequency=1.0, center=128
                ),
                Intensity.DRAMATIC: MovementCategoricalParams(
                    amplitude=0.525, frequency=2.15, center=128
                ),
            },
        ),
        MovementType.LASER_SNAP: MovementPattern(
            id="laser_snap",
            name="Laser Snap",
            description="Quick precise repositions",
            pan_curve=CurveLibrary.MOVEMENT_TRIANGLE,
            base_tilt_curve=CurveLibrary.MOVEMENT_TRIANGLE,
            base_params={"amplitude": 0.8, "center": 128, "frequency": 2.0},
            categorical_params={
                Intensity.SMOOTH: MovementCategoricalParams(
                    amplitude=0.3, frequency=0.5, center=128
                ),
                Intensity.DRAMATIC: MovementCategoricalParams(
                    amplitude=0.6, frequency=1.25, center=128
                ),
            },
        ),
        MovementType.HIT: MovementPattern(
            id="hit",
            name="Hit",
            description="Fast snap to position, hold, then return",
            pan_curve=CurveLibrary.MOVEMENT_PULSE,
            base_tilt_curve=CurveLibrary.MOVEMENT_PULSE,
            base_params={
                "hit_pan_offset_deg": 90,
                "hit_tilt_offset_deg": 30,
                "snap_time_ms": 150,
                "hold_time_ms": 100,
                "return_time_ms": 150,
            },
            categorical_params={
                Intensity.SMOOTH: MovementCategoricalParams(
                    amplitude=0.5, frequency=0.3, center=128
                ),
                Intensity.DRAMATIC: MovementCategoricalParams(
                    amplitude=0.775, frequency=0.75, center=128
                ),
            },
        ),
        MovementType.STOMP: MovementPattern(
            id="stomp",
            name="Stomp",
            description="Heavy downward hits",
            pan_curve=CurveLibrary.MOVEMENT_HOLD,
            base_tilt_curve=CurveLibrary.MOVEMENT_TRIANGLE,
            base_params={"amplitude": 0.8, "center": 128, "frequency": 1.0},
            categorical_params={
                Intensity.SMOOTH: MovementCategoricalParams(
                    amplitude=0.3, frequency=0.5, center=128
                ),
                Intensity.DRAMATIC: MovementCategoricalParams(
                    amplitude=0.6, frequency=1.25, center=128
                ),
            },
        ),
        # ============================================================================
        # Wave and Complex Patterns
        # ============================================================================
        MovementType.WAVE_HORIZONTAL: MovementPattern(
            id="wave_horizontal",
            name="Horizontal Wave",
            description="Horizontal wave across fixtures",
            pan_curve=CurveLibrary.MOVEMENT_SINE,
            base_tilt_curve=CurveLibrary.MOVEMENT_HOLD,
            base_params={},
            geometry_modifiers={GeometryType.SCATTERED_CHAOS: CurveLibrary.MOVEMENT_PERLIN_NOISE},
            categorical_params={
                Intensity.SMOOTH: MovementCategoricalParams(
                    amplitude=0.4, frequency=0.5, center=128
                ),
                Intensity.DRAMATIC: MovementCategoricalParams(
                    amplitude=0.565, frequency=1.05, center=128
                ),
            },
        ),
        MovementType.WAVE_VERTICAL: MovementPattern(
            id="wave_vertical",
            name="Vertical Wave",
            description="Vertical wave across fixtures",
            pan_curve=CurveLibrary.MOVEMENT_HOLD,
            base_tilt_curve=CurveLibrary.MOVEMENT_SINE,
            base_params={},
            categorical_params={
                Intensity.SMOOTH: MovementCategoricalParams(
                    amplitude=0.4, frequency=0.5, center=128
                ),
                Intensity.DRAMATIC: MovementCategoricalParams(
                    amplitude=0.55, frequency=1.05, center=128
                ),
            },
        ),
        MovementType.ZIGZAG: MovementPattern(
            id="zigzag",
            name="Zigzag",
            description="Sharp angular zigzag motion",
            pan_curve=CurveLibrary.MOVEMENT_TRIANGLE,
            base_tilt_curve=CurveLibrary.MOVEMENT_TRIANGLE,
            base_params={},
            categorical_params={
                Intensity.SMOOTH: MovementCategoricalParams(
                    amplitude=0.4, frequency=1.0, center=128
                ),
                Intensity.DRAMATIC: MovementCategoricalParams(
                    amplitude=0.59, frequency=1.75, center=128
                ),
            },
        ),
        MovementType.SPIRAL: MovementPattern(
            id="spiral",
            name="Spiral",
            description="Spiral pattern with varying radius",
            pan_curve=CurveLibrary.LISSAJOUS,
            base_tilt_curve=CurveLibrary.LISSAJOUS,
            base_params={},
            categorical_params={
                Intensity.SMOOTH: MovementCategoricalParams(
                    amplitude=0.3, frequency=0.4, center=128
                ),
                Intensity.DRAMATIC: MovementCategoricalParams(
                    amplitude=0.525, frequency=0.85, center=128
                ),
            },
        ),
        MovementType.DIAGONAL_SWEEP: MovementPattern(
            id="diagonal_sweep",
            name="Diagonal Sweep",
            description="Diagonal sweep motion",
            pan_curve=CurveLibrary.MOVEMENT_SINE,
            base_tilt_curve=CurveLibrary.MOVEMENT_SINE,
            base_params={},
            categorical_params={
                Intensity.SMOOTH: MovementCategoricalParams(
                    amplitude=0.4, frequency=0.5, center=128
                ),
                Intensity.DRAMATIC: MovementCategoricalParams(
                    amplitude=0.59, frequency=1.05, center=128
                ),
            },
        ),
        MovementType.CORNER_TO_CORNER: MovementPattern(
            id="corner_to_corner",
            name="Corner to Corner",
            description="Corner-to-corner movement",
            pan_curve=CurveLibrary.MOVEMENT_SINE,
            base_tilt_curve=CurveLibrary.MOVEMENT_SINE,
            base_params={},
            categorical_params={
                Intensity.SMOOTH: MovementCategoricalParams(
                    amplitude=0.5, frequency=0.4, center=128
                ),
                Intensity.DRAMATIC: MovementCategoricalParams(
                    amplitude=0.685, frequency=0.85, center=128
                ),
            },
        ),
        MovementType.DUAL_SWEEP: MovementPattern(
            id="dual_sweep",
            name="Dual Sweep",
            description="Dual-axis simultaneous sweep",
            pan_curve=CurveLibrary.MOVEMENT_SINE,
            base_tilt_curve=CurveLibrary.MOVEMENT_SINE,
            base_params={},
            categorical_params={
                Intensity.SMOOTH: MovementCategoricalParams(
                    amplitude=0.4, frequency=0.5, center=128
                ),
                Intensity.DRAMATIC: MovementCategoricalParams(
                    amplitude=0.59, frequency=1.05, center=128
                ),
            },
        ),
        MovementType.FAN_IRIS: MovementPattern(
            id="fan_iris",
            name="Fan Iris",
            description="Progressive fan expansion/collapse",
            pan_curve=CurveLibrary.MOVEMENT_LINEAR,
            base_tilt_curve=CurveLibrary.MOVEMENT_LINEAR,
            base_params={"amplitude": 0.8, "center": 128, "frequency": 1.0},
            categorical_params={
                Intensity.SMOOTH: MovementCategoricalParams(
                    amplitude=0.3, frequency=0.5, center=128
                ),
                Intensity.DRAMATIC: MovementCategoricalParams(
                    amplitude=0.6, frequency=1.25, center=128
                ),
            },
        ),
        MovementType.RADIAL_FAN: MovementPattern(
            id="radial_fan",
            name="Radial Fan",
            description="Radial fan pattern",
            pan_curve=CurveLibrary.MOVEMENT_TRIANGLE,
            base_tilt_curve=CurveLibrary.MOVEMENT_TRIANGLE,
            base_params={"amplitude": 0.8, "center": 128, "frequency": 1.0},
            categorical_params={
                Intensity.SMOOTH: MovementCategoricalParams(
                    amplitude=0.3, frequency=0.5, center=128
                ),
                Intensity.DRAMATIC: MovementCategoricalParams(
                    amplitude=0.6, frequency=1.25, center=128
                ),
            },
        ),
        MovementType.CROSS_PATTERN: MovementPattern(
            id="cross_pattern",
            name="Cross Pattern",
            description="X-pattern movement",
            pan_curve=CurveLibrary.LISSAJOUS,
            base_tilt_curve=CurveLibrary.LISSAJOUS,
            base_params={},
            categorical_params={
                Intensity.SMOOTH: MovementCategoricalParams(
                    amplitude=0.4, frequency=0.6, center=128
                ),
                Intensity.DRAMATIC: MovementCategoricalParams(
                    amplitude=0.565, frequency=1.1, center=128
                ),
            },
        ),
    }

    @classmethod
    def get_pattern(cls, movement_type: MovementType) -> MovementPattern:
        """Get movement pattern definition.

        Args:
            pattern_id: Pattern identifier (string or enum)
        """
        return cls.PATTERNS[movement_type]

    @classmethod
    def get_all_metadata(cls) -> list[dict[str, str]]:
        """Get metadata for all movement patterns (optimized for LLM context).

        Returns:
            List of dictionaries with pattern metadata
        """
        return [
            {
                "movement_id": pattern.id,
                "name": pattern.name,
                "description": pattern.description,
                "pan_curve": pattern.pan_curve.value,
                "base_tilt_curve": pattern.base_tilt_curve.value,
            }
            for pattern in cls.PATTERNS.values()
        ]
