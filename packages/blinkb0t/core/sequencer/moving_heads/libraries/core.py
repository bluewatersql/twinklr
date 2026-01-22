"""Core fundamental movement patterns.

Contains basic building blocks: sweeps, circles, figure-8, hold, and random walk.
"""

from __future__ import annotations

from blinkb0t.core.domains.sequencing.libraries.moving_heads.base import (
    AlternativeCurve,
    CategoricalIntensity,
    CurveCategory,
    CurveMapping,
    CurveType,
)
from blinkb0t.core.domains.sequencing.libraries.moving_heads.movements.models import (
    CategoricalParams,
    MovementID,
    MovementPattern,
)

# Core movement patterns - fundamental building blocks
CORE_MOVEMENTS: dict[MovementID, MovementPattern] = {
    MovementID.SWEEP_LR: MovementPattern(
        id=MovementID.SWEEP_LR,
        name="Left/Right Sweep",
        description="Smooth horizontal sweep across the performance space",
        expected_behavior=(
            "The sweep_lr movement creates a smooth, continuous horizontal sweep from "
            "left to right and back. The motion should feel fluid and intentional, with "
            "smooth acceleration and deceleration at the endpoints."
        ),
        primary_curve=CurveMapping(
            curve=CurveType.EASE_IN_OUT_SINE,
            curve_category=CurveCategory.CUSTOM,
            fitness_score=95,
            reasoning=(
                "SINE provides smooth acceleration and deceleration at the sweep endpoints, "
                "creating natural-looking motion without harsh stops or starts."
            ),
        ),
        base_params={"amplitude": 0.8, "center": 128, "frequency": 1.0},
        categorical_params={
            CategoricalIntensity.SMOOTH: CategoricalParams(
                amplitude=0.3, frequency=0.5, center=128
            ),
            CategoricalIntensity.DRAMATIC: CategoricalParams(
                amplitude=0.6, frequency=1.25, center=128
            ),
            CategoricalIntensity.INTENSE: CategoricalParams(
                amplitude=1.0, frequency=2.5, center=128
            ),
        },
        alternatives=[
            AlternativeCurve(
                curve=CurveType.COSINE,
                fitness=90,
                note="COSINE works but SINE is smoother for sweeps",
                params={"amplitude": 0.7, "frequency": 1.0},
            )
        ],
    ),
    MovementID.SWEEP_UD: MovementPattern(
        id=MovementID.SWEEP_UD,
        name="Up/Down Sweep",
        description="Smooth vertical sweep across the performance space",
        expected_behavior=(
            "The sweep_ud movement creates a smooth vertical sweep from bottom to top and back. "
            "Similar to sweep_lr but in the vertical axis."
        ),
        primary_curve=CurveMapping(
            curve=CurveType.EASE_IN_OUT_SINE,
            curve_category=CurveCategory.CUSTOM,
            fitness_score=95,
            reasoning="SINE provides smooth acceleration/deceleration for vertical sweeps",
        ),
        base_params={"amplitude": 0.6, "center": 128, "frequency": 1.0},
        categorical_params={
            CategoricalIntensity.SMOOTH: CategoricalParams(
                amplitude=0.3, frequency=0.5, center=128
            ),
            CategoricalIntensity.DRAMATIC: CategoricalParams(
                amplitude=0.6, frequency=1.25, center=128
            ),
            CategoricalIntensity.INTENSE: CategoricalParams(
                amplitude=1.0, frequency=2.5, center=128
            ),
        },
        alternatives=[],
    ),
    MovementID.CIRCLE: MovementPattern(
        id=MovementID.CIRCLE,
        name="Circular Motion",
        description="Pan and tilt coordinated for circular path",
        expected_behavior=(
            "The circle movement creates a smooth circular path through pan/tilt coordination. "
            "The fixture traces a complete circle, maintaining consistent speed throughout."
        ),
        primary_curve=CurveMapping(
            curve=CurveType.LISSAJOUS,
            curve_category=CurveCategory.CUSTOM,
            fitness_score=95,
            reasoning=("LISSAJOUS creates true circular motion via parametric oscillation"),
        ),
        base_params={"amplitude": 0.7, "frequency": 1.0, "center": 128},
        categorical_params={
            CategoricalIntensity.SMOOTH: CategoricalParams(
                amplitude=0.3, frequency=0.5, center=128
            ),
            CategoricalIntensity.DRAMATIC: CategoricalParams(
                amplitude=0.6, frequency=1.25, center=128
            ),
            CategoricalIntensity.INTENSE: CategoricalParams(
                amplitude=1.0, frequency=2.5, center=128
            ),
        },
        alternatives=[
            AlternativeCurve(
                curve=CurveType.LISSAJOUS,
                fitness=85,
                note="LISSAJOUS can create more complex circular paths",
                params={},
            )
        ],
    ),
    MovementID.FIGURE8: MovementPattern(
        id=MovementID.FIGURE8,
        name="Figure-8 Pattern",
        description="Creates figure-8 or infinity symbol pattern",
        expected_behavior=(
            "The figure8 movement creates a smooth figure-8 pattern through coordinated "
            "pan and tilt movements with different frequencies."
        ),
        primary_curve=CurveMapping(
            curve=CurveType.LISSAJOUS,
            curve_category=CurveCategory.CUSTOM,
            fitness_score=95,
            reasoning="LISSAJOUS curves are designed for creating figure-8 patterns",
        ),
        base_params={"amplitude": 0.7, "frequency": 1.0, "center": 128},
        categorical_params={
            CategoricalIntensity.SMOOTH: CategoricalParams(
                amplitude=0.3, frequency=0.5, center=128
            ),
            CategoricalIntensity.DRAMATIC: CategoricalParams(
                amplitude=0.6, frequency=1.25, center=128
            ),
            CategoricalIntensity.INTENSE: CategoricalParams(
                amplitude=1.0, frequency=2.5, center=128
            ),
        },
        alternatives=[],
    ),
    MovementID.INFINITY: MovementPattern(
        id=MovementID.INFINITY,
        name="Infinity Symbol",
        description="Infinity/figure-8 pattern",
        expected_behavior="Smooth infinity symbol trace",
        primary_curve=CurveMapping(
            curve=CurveType.LISSAJOUS,
            curve_category=CurveCategory.CUSTOM,
            fitness_score=95,
            reasoning="Natural fit for infinity patterns",
        ),
        base_params={},
        categorical_params={
            CategoricalIntensity.SMOOTH: CategoricalParams(
                amplitude=0.3, frequency=0.5, center=128
            ),
            CategoricalIntensity.DRAMATIC: CategoricalParams(
                amplitude=0.525, frequency=0.9500000000000001, center=128
            ),
            CategoricalIntensity.INTENSE: CategoricalParams(
                amplitude=0.9, frequency=1.8, center=128
            ),
        },
        alternatives=[],
    ),
    MovementID.HOLD: MovementPattern(
        id=MovementID.HOLD,
        name="Hold Position",
        description="Maintain current position (no movement)",
        expected_behavior=(
            "Fixtures remain stationary at their current position. Used for static looks "
            "or as a pause between movement patterns."
        ),
        primary_curve=CurveMapping(
            curve=CurveType.FLAT,
            curve_category=CurveCategory.NATIVE,
            fitness_score=100,
            reasoning="FLAT curve maintains constant value - perfect for hold",
        ),
        base_params={},
        categorical_params={
            CategoricalIntensity.SMOOTH: CategoricalParams(
                amplitude=0.0, frequency=0.0, center=128
            ),
            CategoricalIntensity.DRAMATIC: CategoricalParams(
                amplitude=0.0, frequency=0.0, center=128
            ),
            CategoricalIntensity.INTENSE: CategoricalParams(
                amplitude=0.0, frequency=0.0, center=128
            ),
        },
        alternatives=[],
    ),
    MovementID.RANDOM_WALK: MovementPattern(
        id=MovementID.RANDOM_WALK,
        name="Random Walk",
        description="Organic random movement",
        expected_behavior="Natural-looking random motion",
        primary_curve=CurveMapping(
            curve=CurveType.PERLIN_NOISE,
            curve_category=CurveCategory.CUSTOM,
            fitness_score=95,
            reasoning="Organic randomness",
        ),
        base_params={},
        categorical_params={
            CategoricalIntensity.SMOOTH: CategoricalParams(
                amplitude=0.2, frequency=0.3, center=128
            ),
            CategoricalIntensity.DRAMATIC: CategoricalParams(
                amplitude=0.425, frequency=0.75, center=128
            ),
            CategoricalIntensity.INTENSE: CategoricalParams(
                amplitude=0.8, frequency=1.5, center=128
            ),
        },
        alternatives=[],
    ),
}
