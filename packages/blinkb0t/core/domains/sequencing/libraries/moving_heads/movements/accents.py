"""Accent and percussive movement patterns.

Contains sharp, impactful movements like snaps, hits, pops, and stomps.
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

# Accent patterns - sharp, percussive movements
ACCENT_MOVEMENTS: dict[MovementID, MovementPattern] = {
    MovementID.ACCENT_SNAP: MovementPattern(
        id=MovementID.ACCENT_SNAP,
        name="Accent Snap",
        description="Sharp snap to accent beat",
        expected_behavior="Instant position change",
        primary_curve=CurveMapping(
            curve=CurveType.FLAT,
            curve_category=CurveCategory.NATIVE,
            fitness_score=100,
            reasoning="Instant snap = flat curve",
        ),
        base_params={},
        categorical_params={
            CategoricalIntensity.SMOOTH: CategoricalParams(
                amplitude=0.4, frequency=0.5, center=128
            ),
            CategoricalIntensity.DRAMATIC: CategoricalParams(
                amplitude=0.625, frequency=1.05, center=128
            ),
            CategoricalIntensity.INTENSE: CategoricalParams(
                amplitude=1.0, frequency=2.0, center=128
            ),
        },
        alternatives=[],
    ),
    MovementID.POP_LOCK: MovementPattern(
        id=MovementID.POP_LOCK,
        name="Pop Lock",
        description="Sharp snap to positions",
        expected_behavior="Discrete position snaps",
        primary_curve=CurveMapping(
            curve=CurveType.SQUARE,
            curve_category=CurveCategory.CUSTOM,
            fitness_score=95,
            reasoning="Sharp transitions for pop-lock",
        ),
        base_params={},
        categorical_params={
            CategoricalIntensity.SMOOTH: CategoricalParams(
                amplitude=0.3, frequency=1.0, center=128
            ),
            CategoricalIntensity.DRAMATIC: CategoricalParams(
                amplitude=0.525, frequency=2.15, center=128
            ),
            CategoricalIntensity.INTENSE: CategoricalParams(
                amplitude=0.9, frequency=4.0, center=128
            ),
        },
        alternatives=[],
    ),
    MovementID.LASER_SNAP: MovementPattern(
        id=MovementID.LASER_SNAP,
        name="Laser Snap",
        description="Quick precise repositions",
        expected_behavior=(
            "Rapid, precise transitions between positions like a laser pointer snapping "
            "from target to target. Sharp and immediate."
        ),
        primary_curve=CurveMapping(
            curve=CurveType.TRIANGLE,
            curve_category=CurveCategory.CUSTOM,
            fitness_score=92,
            reasoning="TRIANGLE provides sharp, linear oscillation ideal for precise snapping movements",
        ),
        base_params={"amplitude": 0.8, "center": 128, "frequency": 2.0},
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
                curve=CurveType.SQUARE,
                fitness=75,
                note="SQUARE for binary transitions",
                params={"amplitude": 0.7, "frequency": 2.0},
            )
        ],
    ),
    MovementID.HIT: MovementPattern(
        id=MovementID.HIT,
        name="Hit",
        description="Fast snap to position, hold, then return (3-phase percussive movement)",
        expected_behavior=(
            "Sharp percussive effect with three phases: (1) fast snap with acceleration, "
            "(2) brief hold at full intensity, (3) smooth return with deceleration."
        ),
        primary_curve=CurveMapping(
            curve=CurveType.EASE_IN_CUBIC,
            curve_category=CurveCategory.CUSTOM,
            fitness_score=90,
            reasoning="EASE_IN_CUBIC for snap phase; combined with static hold and EASE_OUT_CUBIC return",
        ),
        base_params={
            "hit_pan_offset_deg": 90,
            "hit_tilt_offset_deg": 30,
            "snap_time_ms": 150,
            "hold_time_ms": 100,
            "return_time_ms": 150,
        },
        categorical_params={
            CategoricalIntensity.SMOOTH: CategoricalParams(
                amplitude=0.5, frequency=0.3, center=128
            ),
            CategoricalIntensity.DRAMATIC: CategoricalParams(
                amplitude=0.7749999999999999, frequency=0.75, center=128
            ),
            CategoricalIntensity.INTENSE: CategoricalParams(
                amplitude=1.0, frequency=1.5, center=128
            ),
        },
        alternatives=[
            AlternativeCurve(
                curve=CurveType.EASE_IN_QUAD,
                fitness=85,
                note="Less aggressive acceleration for softer hits",
                params={},
            )
        ],
    ),
    MovementID.STOMP: MovementPattern(
        id=MovementID.STOMP,
        name="Stomp",
        description="Heavy downward hits",
        expected_behavior=(
            "Forceful downward motion like stomping - quick impactful descent "
            "with sudden stop and potential rebound."
        ),
        primary_curve=CurveMapping(
            curve=CurveType.BOUNCE_OUT,
            curve_category=CurveCategory.CUSTOM,
            fitness_score=90,
            reasoning="BOUNCE_OUT captures rapid descent and abrupt stop with slight rebound",
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
                curve=CurveType.EXPONENTIAL,
                fitness=75,
                note="Rapid acceleration but lacks rebound",
                params={"amplitude": 0.7, "frequency": 1.0},
            )
        ],
    ),
}
