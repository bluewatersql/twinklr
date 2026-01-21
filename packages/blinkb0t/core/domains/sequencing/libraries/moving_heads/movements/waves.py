"""Wave and complex sweep movement patterns.

Contains wave patterns, spirals, diagonals, and other complex multi-axis movements.
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

# Wave and complex patterns - multi-axis and sequential movements
WAVE_MOVEMENTS: dict[MovementID, MovementPattern] = {
    MovementID.WAVE_HORIZONTAL: MovementPattern(
        id=MovementID.WAVE_HORIZONTAL,
        name="Horizontal Wave",
        description="Horizontal wave across fixtures",
        expected_behavior="Sequential left-to-right wave",
        primary_curve=CurveMapping(
            curve=CurveType.SINE,
            curve_category=CurveCategory.NATIVE,
            fitness_score=95,
            reasoning="Smooth wave motion",
        ),
        base_params={},
        categorical_params={
            CategoricalIntensity.SMOOTH: CategoricalParams(
                amplitude=0.4, frequency=0.5, center=128
            ),
            CategoricalIntensity.DRAMATIC: CategoricalParams(
                amplitude=0.565, frequency=1.05, center=128
            ),
            CategoricalIntensity.INTENSE: CategoricalParams(
                amplitude=0.85, frequency=2.0, center=128
            ),
        },
        alternatives=[],
    ),
    MovementID.WAVE_VERTICAL: MovementPattern(
        id=MovementID.WAVE_VERTICAL,
        name="Vertical Wave",
        description="Vertical wave across fixtures",
        expected_behavior="Sequential up/down wave",
        primary_curve=CurveMapping(
            curve=CurveType.SINE,
            curve_category=CurveCategory.NATIVE,
            fitness_score=95,
            reasoning="Smooth wave motion",
        ),
        base_params={},
        categorical_params={
            CategoricalIntensity.SMOOTH: CategoricalParams(
                amplitude=0.4, frequency=0.5, center=128
            ),
            CategoricalIntensity.DRAMATIC: CategoricalParams(
                amplitude=0.55, frequency=1.05, center=128
            ),
            CategoricalIntensity.INTENSE: CategoricalParams(
                amplitude=0.8, frequency=2.0, center=128
            ),
        },
        alternatives=[],
    ),
    MovementID.ZIGZAG: MovementPattern(
        id=MovementID.ZIGZAG,
        name="Zigzag",
        description="Sharp angular zigzag motion",
        expected_behavior="Angular back-and-forth pattern",
        primary_curve=CurveMapping(
            curve=CurveType.TRIANGLE,
            curve_category=CurveCategory.CUSTOM,
            fitness_score=93,
            reasoning="Sharp angles for zigzag",
        ),
        base_params={},
        categorical_params={
            CategoricalIntensity.SMOOTH: CategoricalParams(
                amplitude=0.4, frequency=1.0, center=128
            ),
            CategoricalIntensity.DRAMATIC: CategoricalParams(
                amplitude=0.5900000000000001, frequency=1.75, center=128
            ),
            CategoricalIntensity.INTENSE: CategoricalParams(
                amplitude=0.9, frequency=3.0, center=128
            ),
        },
        alternatives=[],
    ),
    MovementID.SPIRAL: MovementPattern(
        id=MovementID.SPIRAL,
        name="Spiral",
        description="Spiral pattern with varying radius",
        expected_behavior="Expanding/contracting spiral",
        primary_curve=CurveMapping(
            curve=CurveType.LISSAJOUS,
            curve_category=CurveCategory.CUSTOM,
            fitness_score=95,
            reasoning="LISSAJOUS creates smooth spiral paths via parametric curves",
        ),
        base_params={},
        categorical_params={
            CategoricalIntensity.SMOOTH: CategoricalParams(
                amplitude=0.3, frequency=0.4, center=128
            ),
            CategoricalIntensity.DRAMATIC: CategoricalParams(
                amplitude=0.525, frequency=0.85, center=128
            ),
            CategoricalIntensity.INTENSE: CategoricalParams(
                amplitude=0.9, frequency=1.5, center=128
            ),
        },
        alternatives=[],
    ),
    MovementID.DIAGONAL_SWEEP: MovementPattern(
        id=MovementID.DIAGONAL_SWEEP,
        name="Diagonal Sweep",
        description="Diagonal sweep motion",
        expected_behavior="Smooth diagonal sweep",
        primary_curve=CurveMapping(
            curve=CurveType.SINE,
            curve_category=CurveCategory.NATIVE,
            fitness_score=95,
            reasoning="Smooth diagonal motion",
        ),
        base_params={},
        categorical_params={
            CategoricalIntensity.SMOOTH: CategoricalParams(
                amplitude=0.4, frequency=0.5, center=128
            ),
            CategoricalIntensity.DRAMATIC: CategoricalParams(
                amplitude=0.5900000000000001, frequency=1.05, center=128
            ),
            CategoricalIntensity.INTENSE: CategoricalParams(
                amplitude=0.9, frequency=2.0, center=128
            ),
        },
        alternatives=[],
    ),
    MovementID.CORNER_TO_CORNER: MovementPattern(
        id=MovementID.CORNER_TO_CORNER,
        name="Corner to Corner",
        description="Corner-to-corner movement",
        expected_behavior="Moves between stage corners",
        primary_curve=CurveMapping(
            curve=CurveType.SINE,
            curve_category=CurveCategory.NATIVE,
            fitness_score=95,
            reasoning="Smooth corner transitions",
        ),
        base_params={},
        categorical_params={
            CategoricalIntensity.SMOOTH: CategoricalParams(
                amplitude=0.5, frequency=0.4, center=128
            ),
            CategoricalIntensity.DRAMATIC: CategoricalParams(
                amplitude=0.685, frequency=0.85, center=128
            ),
            CategoricalIntensity.INTENSE: CategoricalParams(
                amplitude=1.0, frequency=1.5, center=128
            ),
        },
        alternatives=[],
    ),
    MovementID.DUAL_SWEEP: MovementPattern(
        id=MovementID.DUAL_SWEEP,
        name="Dual Sweep",
        description="Dual-axis simultaneous sweep",
        expected_behavior="Pan and tilt sweep simultaneously",
        primary_curve=CurveMapping(
            curve=CurveType.SINE,
            curve_category=CurveCategory.NATIVE,
            fitness_score=95,
            reasoning="Smooth dual-axis motion",
        ),
        base_params={},
        categorical_params={
            CategoricalIntensity.SMOOTH: CategoricalParams(
                amplitude=0.4, frequency=0.5, center=128
            ),
            CategoricalIntensity.DRAMATIC: CategoricalParams(
                amplitude=0.5900000000000001, frequency=1.05, center=128
            ),
            CategoricalIntensity.INTENSE: CategoricalParams(
                amplitude=0.9, frequency=2.0, center=128
            ),
        },
        alternatives=[],
    ),
    MovementID.CROSS_PATTERN: MovementPattern(
        id=MovementID.CROSS_PATTERN,
        name="Cross Pattern",
        description="X-pattern movement",
        expected_behavior="Creates X-shaped crossing pattern",
        primary_curve=CurveMapping(
            curve=CurveType.LISSAJOUS,
            curve_category=CurveCategory.CUSTOM,
            fitness_score=90,
            reasoning="Creates complex oscillating patterns",
        ),
        base_params={},
        categorical_params={
            CategoricalIntensity.SMOOTH: CategoricalParams(
                amplitude=0.4, frequency=0.6, center=128
            ),
            CategoricalIntensity.DRAMATIC: CategoricalParams(
                amplitude=0.565, frequency=1.1, center=128
            ),
            CategoricalIntensity.INTENSE: CategoricalParams(
                amplitude=0.85, frequency=2.0, center=128
            ),
        },
        alternatives=[],
    ),
    MovementID.FAN_IRIS: MovementPattern(
        id=MovementID.FAN_IRIS,
        name="Fan Iris",
        description="Progressive fan expansion/collapse",
        expected_behavior=(
            "Fan-like effect where fixtures progressively spread out (open) or converge (close). "
            "Smooth interpolation for organic effect."
        ),
        primary_curve=CurveMapping(
            curve=CurveType.SMOOTH_STEP,
            curve_category=CurveCategory.CUSTOM,
            fitness_score=92,
            reasoning="SMOOTH_STEP provides smooth acceleration/deceleration for fan movements",
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
                curve=CurveType.EASE_IN_OUT_SINE,
                fitness=85,
                note="EASE_IN_OUT_SINE for more organic fan movements",
                params={},
            )
        ],
    ),
    MovementID.RADIAL_FAN: MovementPattern(
        id=MovementID.RADIAL_FAN,
        name="Radial Fan",
        description="Radial fan pattern",
        expected_behavior=(
            "Smooth sweeping motion of a fan blade - consistent arc with "
            "smooth transitions and constant speed."
        ),
        primary_curve=CurveMapping(
            curve=CurveType.EASE_IN_OUT_SINE,
            curve_category=CurveCategory.CUSTOM,
            fitness_score=95,
            reasoning="EASE_IN_OUT_SINE provides smooth fan-like sweeping with natural acceleration",
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
                note="Phase-shifted alternative",
                params={"amplitude": 0.8, "frequency": 1.0},
            )
        ],
    ),
}
