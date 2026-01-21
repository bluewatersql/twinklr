"""Curve function registry.

Central registry mapping CustomCurveType enums to their implementation functions.
Replaces the massive if/elif chain in CustomCurveProvider.
"""

from collections.abc import Callable

import numpy as np
from numpy.typing import NDArray

from blinkb0t.core.domains.sequencing.infrastructure.curves.enums import CustomCurveType
from blinkb0t.core.domains.sequencing.infrastructure.curves.functions import (
    anticipate,
    beat_pulse,
    bezier,
    bounce_in,
    bounce_out,
    cosine,
    ease_in_back,
    ease_in_cubic,
    ease_in_expo,
    ease_in_out_back,
    ease_in_out_cubic,
    ease_in_out_expo,
    ease_in_out_quad,
    ease_in_out_sine,
    ease_in_quad,
    ease_in_sine,
    ease_out_back,
    ease_out_cubic,
    ease_out_expo,
    ease_out_quad,
    ease_out_sine,
    elastic_in,
    elastic_out,
    lissajous,
    musical_accent,
    musical_swell,
    overshoot,
    perlin_noise,
    s_curve,
    simplex_noise,
    smooth_step,
    smoother_step,
    square,
    triangle,
)
from blinkb0t.core.domains.sequencing.infrastructure.curves.functions.native_equivalents import (
    abs_sine_x,
    exponential_x,
    flat_x,
    logarithmic_x,
    parabolic_x,
    ramp_x,
    saw_tooth_x,
    sine_x,
)

# Type alias for curve functions
CurveFunction = Callable[[NDArray[np.float64]], NDArray[np.float64]]


# Registry: Maps each CustomCurveType to its implementation function
CurveFunctionRegistry: dict[CustomCurveType, CurveFunction] = {
    # Native curve equivalents (for blending support)
    CustomCurveType.FLAT_X: flat_x,
    CustomCurveType.RAMP_X: ramp_x,
    CustomCurveType.SINE_X: sine_x,
    CustomCurveType.ABS_SINE_X: abs_sine_x,
    CustomCurveType.PARABOLIC_X: parabolic_x,
    CustomCurveType.LOGARITHMIC_X: logarithmic_x,
    CustomCurveType.EXPONENTIAL_X: exponential_x,
    CustomCurveType.SAW_TOOTH_X: saw_tooth_x,
    # Basic waves
    CustomCurveType.COSINE: cosine,
    CustomCurveType.TRIANGLE: triangle,
    CustomCurveType.SQUARE: square,
    # Smooth transitions
    CustomCurveType.S_CURVE: s_curve,
    CustomCurveType.SMOOTH_STEP: smooth_step,
    CustomCurveType.SMOOTHER_STEP: smoother_step,
    # Easing - Sine
    CustomCurveType.EASE_IN_SINE: ease_in_sine,
    CustomCurveType.EASE_OUT_SINE: ease_out_sine,
    CustomCurveType.EASE_IN_OUT_SINE: ease_in_out_sine,
    # Easing - Quad
    CustomCurveType.EASE_IN_QUAD: ease_in_quad,
    CustomCurveType.EASE_OUT_QUAD: ease_out_quad,
    CustomCurveType.EASE_IN_OUT_QUAD: ease_in_out_quad,
    # Easing - Cubic
    CustomCurveType.EASE_IN_CUBIC: ease_in_cubic,
    CustomCurveType.EASE_OUT_CUBIC: ease_out_cubic,
    CustomCurveType.EASE_IN_OUT_CUBIC: ease_in_out_cubic,
    # Easing - Exponential
    CustomCurveType.EASE_IN_EXPO: ease_in_expo,
    CustomCurveType.EASE_OUT_EXPO: ease_out_expo,
    CustomCurveType.EASE_IN_OUT_EXPO: ease_in_out_expo,
    # Easing - Back/Overshoot
    CustomCurveType.EASE_IN_BACK: ease_in_back,
    CustomCurveType.EASE_OUT_BACK: ease_out_back,
    CustomCurveType.EASE_IN_OUT_BACK: ease_in_out_back,
    # Motion - Bounce
    CustomCurveType.BOUNCE_IN: bounce_in,
    CustomCurveType.BOUNCE_OUT: bounce_out,
    # Motion - Elastic
    CustomCurveType.ELASTIC_IN: elastic_in,
    CustomCurveType.ELASTIC_OUT: elastic_out,
    # Motion - Advanced
    CustomCurveType.ANTICIPATE: anticipate,
    CustomCurveType.OVERSHOOT: overshoot,
    # Musical curves (beat-aligned)
    CustomCurveType.MUSICAL_ACCENT: musical_accent,
    CustomCurveType.MUSICAL_SWELL: musical_swell,
    CustomCurveType.BEAT_PULSE: beat_pulse,
    # Advanced curves
    CustomCurveType.PERLIN_NOISE: perlin_noise,
    CustomCurveType.SIMPLEX_NOISE: simplex_noise,
    CustomCurveType.LISS_AJOUS: lissajous,
    CustomCurveType.BEZIER: bezier,
}


def get_curve_function(curve_type: CustomCurveType) -> CurveFunction:
    """Get the curve generation function for a given curve type.

    Args:
        curve_type: The type of curve to generate

    Returns:
        Curve generation function that takes normalized time array [0, 1]
        and returns normalized values [0, 1]

    Raises:
        KeyError: If curve_type is not registered

    Examples:
        >>> t = np.linspace(0, 1, 100)
        >>> func = get_curve_function(CustomCurveType.COSINE)
        >>> values = func(t)
    """
    return CurveFunctionRegistry[curve_type]


# Validation: Ensure all enum values are registered (at module load time)
_missing_types = set(CustomCurveType) - set(CurveFunctionRegistry.keys())
if _missing_types:
    raise RuntimeError(f"CurveFunctionRegistry is incomplete. Missing types: {_missing_types}")
