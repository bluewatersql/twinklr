"""Dimmer/intensity pattern library - Python-based with type safety.

Provides dimmer curve patterns for intensity control over time.
"""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, ConfigDict, Field

from blinkb0t.core.domains.sequencing.libraries.moving_heads.base import (
    AlternativeCurve,
    CategoricalIntensity,
    CurveCategory,
    CurveMapping,
    CurveType,
)


class DimmerID(str, Enum):
    """All available dimmer pattern identifiers."""

    BREATHE = "breathe"
    PULSE = "pulse"
    SWELL = "swell"
    FADE_IN = "fade_in"
    FADE_OUT = "fade_out"
    STROBE = "strobe"
    HOLD = "hold"


class DimmerCategoricalParams(BaseModel):
    """Categorical parameters for dimmer intensity levels."""

    model_config = ConfigDict(frozen=True)

    min_intensity: int = Field(ge=0, le=255)
    max_intensity: int = Field(ge=0, le=255)
    period: float = Field(gt=0.0)  # Period in bars


class DimmerPattern(BaseModel):
    """Complete dimmer pattern definition."""

    model_config = ConfigDict(frozen=True)

    id: DimmerID
    name: str
    description: str
    expected_behavior: str

    primary_curve: CurveMapping
    base_params: dict[str, int | float | str] = Field(default_factory=dict)
    categorical_params: dict[CategoricalIntensity, DimmerCategoricalParams]
    alternatives: list[AlternativeCurve] = Field(default_factory=list)


# ============================================================================
# Dimmer Library - Content
# ============================================================================

# Default categorical params for dimmers (3-level system)
DEFAULT_DIMMER_PARAMS = {
    CategoricalIntensity.SMOOTH: DimmerCategoricalParams(
        min_intensity=0, max_intensity=128, period=4.0
    ),
    CategoricalIntensity.DRAMATIC: DimmerCategoricalParams(
        min_intensity=0, max_intensity=224, period=1.25
    ),
    CategoricalIntensity.INTENSE: DimmerCategoricalParams(
        min_intensity=0, max_intensity=255, period=0.25
    ),
}

DIMMER_LIBRARY: dict[DimmerID, DimmerPattern] = {
    DimmerID.BREATHE: DimmerPattern(
        id=DimmerID.BREATHE,
        name="Breathe",
        description="Slow cyclic intensity between min/max over N bars",
        expected_behavior=(
            "The intensity pattern should feel smooth and organic, gradually increasing "
            "and decreasing in a cyclic manner, akin to a natural breathing rhythm."
        ),
        primary_curve=CurveMapping(
            curve=CurveType.SINE,
            curve_category=CurveCategory.NATIVE,
            fitness_score=95,
            reasoning=(
                "The SINE curve is ideal for creating smooth, cyclic transitions that "
                "mimic natural breathing patterns."
            ),
        ),
        base_params={"min_intensity": 0, "max_intensity": 255},
        categorical_params={
            CategoricalIntensity.SMOOTH: DimmerCategoricalParams(
                min_intensity=0, max_intensity=128, period=8.0
            ),
            CategoricalIntensity.DRAMATIC: DimmerCategoricalParams(
                min_intensity=0, max_intensity=255, period=2.0
            ),
            CategoricalIntensity.INTENSE: DimmerCategoricalParams(
                min_intensity=0, max_intensity=255, period=1.0
            ),
        },
        alternatives=[
            AlternativeCurve(
                curve=CurveType.COSINE,
                fitness=90,
                note="COSINE is similar to SINE but starts at the peak intensity",
                params={},
            )
        ],
    ),
    DimmerID.FADE_IN: DimmerPattern(
        id=DimmerID.FADE_IN,
        name="Fade In",
        description="Linear fade from 0 to full intensity",
        expected_behavior="Smoothly increases intensity from minimum to maximum over the duration.",
        primary_curve=CurveMapping(
            curve=CurveType.RAMP,
            curve_category=CurveCategory.NATIVE,
            fitness_score=95,
            reasoning="RAMP provides linear increase perfect for fade in",
        ),
        base_params={"min_intensity": 0, "max_intensity": 255},
        categorical_params={
            CategoricalIntensity.SMOOTH: DimmerCategoricalParams(
                min_intensity=0, max_intensity=128, period=4.0
            ),
            CategoricalIntensity.DRAMATIC: DimmerCategoricalParams(
                min_intensity=0, max_intensity=255, period=1.0
            ),
            CategoricalIntensity.INTENSE: DimmerCategoricalParams(
                min_intensity=0, max_intensity=255, period=0.5
            ),
        },
        alternatives=[],
    ),
    DimmerID.FADE_OUT: DimmerPattern(
        id=DimmerID.FADE_OUT,
        name="Fade Out",
        description="Linear fade from full to 0 intensity",
        expected_behavior="Smoothly decreases intensity from maximum to minimum over the duration.",
        primary_curve=CurveMapping(
            curve=CurveType.RAMP,
            curve_category=CurveCategory.NATIVE,
            fitness_score=95,
            reasoning="RAMP (reversed) provides linear decrease perfect for fade out",
        ),
        base_params={"min_intensity": 0, "max_intensity": 255},
        categorical_params={
            CategoricalIntensity.SMOOTH: DimmerCategoricalParams(
                min_intensity=0, max_intensity=128, period=4.0
            ),
            CategoricalIntensity.DRAMATIC: DimmerCategoricalParams(
                min_intensity=0, max_intensity=255, period=1.0
            ),
            CategoricalIntensity.INTENSE: DimmerCategoricalParams(
                min_intensity=0, max_intensity=255, period=0.5
            ),
        },
        alternatives=[],
    ),
    DimmerID.HOLD: DimmerPattern(
        id=DimmerID.HOLD,
        name="Hold Intensity",
        description="Maintain constant intensity",
        expected_behavior="Maintains a constant intensity level throughout the duration.",
        primary_curve=CurveMapping(
            curve=CurveType.FLAT,
            curve_category=CurveCategory.NATIVE,
            fitness_score=100,
            reasoning="FLAT curve maintains constant value",
        ),
        base_params={"min_intensity": 255, "max_intensity": 255},
        categorical_params={
            CategoricalIntensity.SMOOTH: DimmerCategoricalParams(
                min_intensity=128, max_intensity=128, period=1.0
            ),
            CategoricalIntensity.DRAMATIC: DimmerCategoricalParams(
                min_intensity=255, max_intensity=255, period=1.0
            ),
            CategoricalIntensity.INTENSE: DimmerCategoricalParams(
                min_intensity=255, max_intensity=255, period=1.0
            ),
        },
        alternatives=[],
    ),
    DimmerID.PULSE: DimmerPattern(
        id=DimmerID.PULSE,
        name="Pulse",
        description="Sharp on/off pulsing",
        expected_behavior="Creates rhythmic on/off intensity changes with sharp transitions.",
        primary_curve=CurveMapping(
            curve=CurveType.SQUARE,
            curve_category=CurveCategory.CUSTOM,
            fitness_score=95,
            reasoning="SQUARE wave creates sharp on/off transitions perfect for pulsing",
        ),
        base_params={"min_intensity": 0, "max_intensity": 255},
        categorical_params={
            CategoricalIntensity.SMOOTH: DimmerCategoricalParams(
                min_intensity=0, max_intensity=128, period=2.0
            ),
            CategoricalIntensity.DRAMATIC: DimmerCategoricalParams(
                min_intensity=0, max_intensity=255, period=0.5
            ),
            CategoricalIntensity.INTENSE: DimmerCategoricalParams(
                min_intensity=0, max_intensity=255, period=0.25
            ),
        },
        alternatives=[],
    ),
    # Additional patterns (minimal implementations)
    DimmerID.SWELL: DimmerPattern(
        id=DimmerID.SWELL,
        name="Swell",
        description="Gradual intensity swell",
        expected_behavior="Smooth crescendo from low to high intensity",
        primary_curve=CurveMapping(
            curve=CurveType.S_CURVE,
            curve_category=CurveCategory.CUSTOM,
            fitness_score=93,
            reasoning="S-curve provides natural swell",
        ),
        base_params={"min_intensity": 0, "max_intensity": 255},
        categorical_params=DEFAULT_DIMMER_PARAMS,
        alternatives=[],
    ),
    DimmerID.STROBE: DimmerPattern(
        id=DimmerID.STROBE,
        name="Strobe",
        description="Fast on/off strobe effect",
        expected_behavior="Rapid flickering strobe",
        primary_curve=CurveMapping(
            curve=CurveType.SQUARE,
            curve_category=CurveCategory.CUSTOM,
            fitness_score=98,
            reasoning="Square wave perfect for strobe",
        ),
        base_params={"min_intensity": 0, "max_intensity": 255},
        categorical_params={
            CategoricalIntensity.SMOOTH: DimmerCategoricalParams(
                min_intensity=0, max_intensity=128, period=1.0
            ),
            CategoricalIntensity.DRAMATIC: DimmerCategoricalParams(
                min_intensity=0, max_intensity=255, period=0.25
            ),
            CategoricalIntensity.INTENSE: DimmerCategoricalParams(
                min_intensity=0, max_intensity=255, period=0.125
            ),
        },
        alternatives=[],
    ),
}


# ============================================================================
# Accessor Functions
# ============================================================================


def get_dimmer(dimmer_id: DimmerID) -> DimmerPattern:
    """Get dimmer pattern by ID.

    Args:
        dimmer_id: Dimmer pattern enum value

    Returns:
        Complete dimmer pattern definition

    Example:
        pattern = get_dimmer(DimmerID.BREATHE)
        print(pattern.name)  # "Breathe"
    """
    return DIMMER_LIBRARY[dimmer_id]


def get_dimmer_params(
    dimmer_id: DimmerID, intensity: CategoricalIntensity
) -> DimmerCategoricalParams:
    """Get categorical parameters for dimmer at intensity level.

    Args:
        dimmer_id: Dimmer pattern enum value
        intensity: Categorical intensity level

    Returns:
        Parameters for specified intensity level

    Example:
        params = get_dimmer_params(
            DimmerID.BREATHE,
            CategoricalIntensity.DRAMATIC
        )
        print(params.max_intensity)  # 255
    """
    pattern = DIMMER_LIBRARY[dimmer_id]
    return pattern.categorical_params[intensity]


def list_dimmers() -> list[DimmerID]:
    """Get list of all available dimmer IDs.

    Returns:
        List of dimmer enum values
    """
    return list(DIMMER_LIBRARY.keys())
