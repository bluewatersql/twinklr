"""Shared base models and enums for all libraries.

This module provides foundational types used across movement, geometry,
and dimmer libraries to ensure consistency and type safety.
"""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


class CurveType(str, Enum):
    """Curve types used across libraries (superset of NativeCurveType + CustomCurveType).

    This enum combines all curve types from both native xLights curves and
    custom programmatic curves. Values match the existing curve engine enums
    (core/domains/sequencing/curves/enums.py).

    NOTE: Values are lowercase to match existing curve engine conventions.
    They are converted to title case when writing to XSQ files (xLights requirement).

    This enum serves as the library-level reference that will be validated
    against the actual curve engine at runtime.
    """

    # ========================================================================
    # Native xLights Curves (from NativeCurveType)
    # ========================================================================
    FLAT = "flat"
    RAMP = "ramp"
    SINE = "sine"
    ABS_SINE = "abs sine"
    PARABOLIC = "parabolic"
    LOGARITHMIC = "logarithmic"
    EXPONENTIAL = "exponential"
    SAW_TOOTH = "saw tooth"

    # ========================================================================
    # Custom Curves - Fundamental Waves (from CustomCurveType)
    # ========================================================================
    COSINE = "cosine"
    TRIANGLE = "triangle"
    SQUARE = "square"

    # ========================================================================
    # Custom Curves - Smooth Transitions
    # ========================================================================
    S_CURVE = "s_curve"
    SMOOTH_STEP = "smooth_step"
    SMOOTHER_STEP = "smoother_step"

    # ========================================================================
    # Custom Curves - Easing Sine
    # ========================================================================
    EASE_IN_SINE = "ease_in_sine"
    EASE_OUT_SINE = "ease_out_sine"
    EASE_IN_OUT_SINE = "ease_in_out_sine"

    # ========================================================================
    # Custom Curves - Easing Quad
    # ========================================================================
    EASE_IN_QUAD = "ease_in_quad"
    EASE_OUT_QUAD = "ease_out_quad"
    EASE_IN_OUT_QUAD = "ease_in_out_quad"

    # ========================================================================
    # Custom Curves - Easing Cubic
    # ========================================================================
    EASE_IN_CUBIC = "ease_in_cubic"
    EASE_OUT_CUBIC = "ease_out_cubic"
    EASE_IN_OUT_CUBIC = "ease_in_out_cubic"

    # ========================================================================
    # Custom Curves - Dynamic Effects
    # ========================================================================
    BOUNCE_IN = "bounce_in"
    BOUNCE_OUT = "bounce_out"
    ELASTIC_IN = "elastic_in"
    ELASTIC_OUT = "elastic_out"

    # ========================================================================
    # Custom Curves - Natural Motion & Parametric
    # ========================================================================
    PERLIN_NOISE = "perlin_noise"
    BEZIER = "bezier"
    LISSAJOUS = "lissajous"

    # ========================================================================
    # Custom Curves - Advanced Easing
    # ========================================================================
    ANTICIPATE = "anticipate"
    OVERSHOOT = "overshoot"


class CurveCategory(str, Enum):
    """Curve implementation category (how curve is rendered).

    Only two categories exist:
    - NATIVE: xLights renders using parametric formula (p1-p4 parameters)
    - CUSTOM: xLights renders using point array (via Active flag)
    """

    NATIVE = "native"  # xLights native curve (p1-p4 parameters)
    CUSTOM = "custom"  # Custom curve (point array via Active flag)


class CategoricalIntensity(str, Enum):
    """Standard categorical intensity levels (3-level system).

    Used across movement, geometry, and dimmer libraries for consistent
    parameter mapping from semantic intent to numeric values.

    Levels:
    - SMOOTH: Gentle, tight, slow (20-40% power)
    - DRAMATIC: Strong, wide, fast (50-75% power)
    - INTENSE: Extreme, expansive, rapid (80-100% power)
    """

    SMOOTH = "SMOOTH"
    DRAMATIC = "DRAMATIC"
    INTENSE = "INTENSE"


class CurveMapping(BaseModel):
    """Curve selection with fitness score and reasoning.

    Documents which curve works best for a pattern and why.
    """

    model_config = ConfigDict(frozen=True)

    curve: CurveType
    curve_category: CurveCategory
    fitness_score: int = Field(ge=0, le=100)
    reasoning: str


class AlternativeCurve(BaseModel):
    """Alternative curve option with fitness and notes."""

    model_config = ConfigDict(frozen=True)

    curve: CurveType
    fitness: int = Field(ge=0, le=100)
    note: str
    params: dict[str, float] = Field(default_factory=dict)
