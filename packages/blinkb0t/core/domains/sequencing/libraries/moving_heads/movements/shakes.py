"""Shake and oscillation movement patterns.

Contains rapid oscillations, rocks, bounces, and rhythmic swaying movements.
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

# Shake and oscillation patterns - rapid or rhythmic movements
SHAKE_MOVEMENTS: dict[MovementID, MovementPattern] = {
    MovementID.PAN_SHAKE: MovementPattern(
        id=MovementID.PAN_SHAKE,
        name="Pan Shake",
        description="Horizontal shake/vibrate",
        expected_behavior="Rapid horizontal oscillation",
        primary_curve=CurveMapping(
            curve=CurveType.TRIANGLE,
            curve_category=CurveCategory.CUSTOM,
            fitness_score=92,
            reasoning="Sharp oscillation for shake effect",
        ),
        base_params={},
        categorical_params={
            CategoricalIntensity.SMOOTH: CategoricalParams(
                amplitude=0.15, frequency=2.0, center=128
            ),
            CategoricalIntensity.DRAMATIC: CategoricalParams(
                amplitude=0.32, frequency=4.25, center=128
            ),
            CategoricalIntensity.INTENSE: CategoricalParams(
                amplitude=0.6, frequency=8.0, center=128
            ),
        },
        alternatives=[],
    ),
    MovementID.TILT_ROCK: MovementPattern(
        id=MovementID.TILT_ROCK,
        name="Tilt Rock",
        description="Vertical rocking motion",
        expected_behavior="Smooth up/down rocking",
        primary_curve=CurveMapping(
            curve=CurveType.COSINE,
            curve_category=CurveCategory.CUSTOM,
            fitness_score=95,
            reasoning="Smooth oscillation for rocking",
        ),
        base_params={},
        categorical_params={
            CategoricalIntensity.SMOOTH: CategoricalParams(
                amplitude=0.2, frequency=0.5, center=128
            ),
            CategoricalIntensity.DRAMATIC: CategoricalParams(
                amplitude=0.39, frequency=1.05, center=128
            ),
            CategoricalIntensity.INTENSE: CategoricalParams(
                amplitude=0.7, frequency=2.0, center=128
            ),
        },
        alternatives=[],
    ),
    MovementID.BOUNCE: MovementPattern(
        id=MovementID.BOUNCE,
        name="Bounce",
        description="Bouncing motion with decay",
        expected_behavior="Bouncing with decreasing amplitude",
        primary_curve=CurveMapping(
            curve=CurveType.BOUNCE_OUT,
            curve_category=CurveCategory.CUSTOM,
            fitness_score=95,
            reasoning="Natural bounce curve",
        ),
        base_params={},
        categorical_params={
            CategoricalIntensity.SMOOTH: CategoricalParams(
                amplitude=0.3, frequency=0.8, center=128
            ),
            CategoricalIntensity.DRAMATIC: CategoricalParams(
                amplitude=0.525, frequency=1.65, center=128
            ),
            CategoricalIntensity.INTENSE: CategoricalParams(
                amplitude=0.9, frequency=3.0, center=128
            ),
        },
        alternatives=[],
    ),
    MovementID.PENDULUM: MovementPattern(
        id=MovementID.PENDULUM,
        name="Pendulum",
        description="Pendulum swing motion",
        expected_behavior="Smooth pendulum swing",
        primary_curve=CurveMapping(
            curve=CurveType.SINE,
            curve_category=CurveCategory.NATIVE,
            fitness_score=95,
            reasoning="Sine mimics pendulum physics",
        ),
        base_params={},
        categorical_params={
            CategoricalIntensity.SMOOTH: CategoricalParams(
                amplitude=0.3, frequency=0.3, center=128
            ),
            CategoricalIntensity.DRAMATIC: CategoricalParams(
                amplitude=0.485, frequency=0.75, center=128
            ),
            CategoricalIntensity.INTENSE: CategoricalParams(
                amplitude=0.8, frequency=1.5, center=128
            ),
        },
        alternatives=[],
    ),
    MovementID.TILT_BOUNCE: MovementPattern(
        id=MovementID.TILT_BOUNCE,
        name="Tilt Bounce",
        description="Vertical bounce (trampoline, stomp)",
        expected_behavior=(
            "Mimics bouncing physics - rapid descent followed by quick rebound, "
            "slowing at peak. Dynamic and energetic."
        ),
        primary_curve=CurveMapping(
            curve=CurveType.BOUNCE_OUT,
            curve_category=CurveCategory.CUSTOM,
            fitness_score=95,
            reasoning="BOUNCE_OUT simulates bounce physics with quick deceleration and rapid acceleration",
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
                curve=CurveType.ELASTIC_OUT,
                fitness=85,
                note="Spring-like rebound effect",
                params={"amplitude": 0.7},
            )
        ],
    ),
    MovementID.GROOVE_SWAY: MovementPattern(
        id=MovementID.GROOVE_SWAY,
        name="Groove Sway",
        description="Subtle organic sway (breathing)",
        expected_behavior=(
            "Gentle, rhythmic sway that mimics natural breathing. Smooth, continuous, "
            "and organic with no abrupt changes."
        ),
        primary_curve=CurveMapping(
            curve=CurveType.PERLIN_NOISE,
            curve_category=CurveCategory.CUSTOM,
            fitness_score=95,
            reasoning="PERLIN_NOISE provides organic, natural-looking randomness perfect for breathing/swaying",
        ),
        base_params={"amplitude": 0.5, "center": 128, "frequency": 0.8},
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
                note="COSINE phase-shifted alternative",
                params={"amplitude": 0.5, "frequency": 0.8},
            )
        ],
    ),
    MovementID.TRAMPOLINE: MovementPattern(
        id=MovementID.TRAMPOLINE,
        name="Trampoline",
        description="Gentle bounce (floating)",
        expected_behavior=(
            "Gentle rhythmic bouncing resembling trampoline - smooth, buoyant "
            "with gradual rise/fall giving floating impression."
        ),
        primary_curve=CurveMapping(
            curve=CurveType.BOUNCE_OUT,
            curve_category=CurveCategory.CUSTOM,
            fitness_score=92,
            reasoning="BOUNCE_OUT simulates gentle bounce with smooth floating feel",
        ),
        base_params={"amplitude": 0.7, "center": 128, "frequency": 1.0},
        categorical_params={
            CategoricalIntensity.SMOOTH: CategoricalParams(
                amplitude=0.3, frequency=0.5, center=128
            ),
            CategoricalIntensity.DRAMATIC: CategoricalParams(
                amplitude=0.6, frequency=1.25, center=128
            ),
            CategoricalIntensity.INTENSE: CategoricalParams(
                amplitude=0.95, frequency=2.5, center=128
            ),
        },
        alternatives=[
            AlternativeCurve(
                curve=CurveType.EASE_OUT_SINE,
                fitness=80,
                note="Smooth deceleration for gentle bounce",
                params={"amplitude": 0.7, "frequency": 1.0},
            )
        ],
    ),
}
