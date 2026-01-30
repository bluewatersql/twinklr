"""Curve taxonomy and classification system.

Categorizes all curves by family and parameterization support.
"""

from __future__ import annotations

from enum import Enum

from twinklr.core.curves.library import CurveLibrary


class CurveFamily(Enum):
    """Curve family classification.

    Groups curves by their fundamental behavior and use case.
    """

    WAVE = "wave"  # Periodic waves (sine, triangle, pulse)
    EASING = "easing"  # Easing functions (ease in/out)
    DYNAMIC = "dynamic"  # Physical effects (bounce, elastic)
    PARAMETRIC = "parametric"  # Mathematically defined (bezier, lissajous)
    MUSICAL = "musical"  # Beat-aligned timing curves
    NOISE = "noise"  # Noise-based patterns


class CurveParameterization(Enum):
    """How a curve responds to intensity parameters.

    Defines the level of support for categorical intensity parameters
    (amplitude, frequency, center_offset).
    """

    FULL = "full"  # Accepts amplitude + frequency directly
    PARTIAL = "partial"  # Accepts some params or needs adaptation
    TIMING_ONLY = "timing_only"  # Only responds to cycles/duration
    FIXED = "fixed"  # No parameterization, fixed behavior


# Classify all curves by family and parameterization
CURVE_TAXONOMY: dict[CurveLibrary, tuple[CurveFamily, CurveParameterization]] = {
    # Wave curves - FULL parameterization
    CurveLibrary.SINE: (CurveFamily.WAVE, CurveParameterization.FULL),
    CurveLibrary.COSINE: (CurveFamily.WAVE, CurveParameterization.FULL),
    CurveLibrary.TRIANGLE: (CurveFamily.WAVE, CurveParameterization.FULL),
    CurveLibrary.PULSE: (CurveFamily.WAVE, CurveParameterization.PARTIAL),
    CurveLibrary.SQUARE: (CurveFamily.WAVE, CurveParameterization.TIMING_ONLY),
    # Movement curves - FULL or PARTIAL parameterization
    CurveLibrary.MOVEMENT_SINE: (CurveFamily.WAVE, CurveParameterization.FULL),
    CurveLibrary.MOVEMENT_COSINE: (CurveFamily.WAVE, CurveParameterization.FULL),
    CurveLibrary.MOVEMENT_TRIANGLE: (CurveFamily.WAVE, CurveParameterization.FULL),
    CurveLibrary.MOVEMENT_PULSE: (CurveFamily.WAVE, CurveParameterization.PARTIAL),
    CurveLibrary.MOVEMENT_PERLIN_NOISE: (CurveFamily.NOISE, CurveParameterization.PARTIAL),
    # Smooth transitions
    CurveLibrary.S_CURVE: (CurveFamily.EASING, CurveParameterization.FIXED),
    CurveLibrary.SMOOTH_STEP: (CurveFamily.EASING, CurveParameterization.FIXED),
    CurveLibrary.SMOOTHER_STEP: (CurveFamily.EASING, CurveParameterization.FIXED),
    # Easing sine curves - FIXED behavior
    CurveLibrary.EASE_IN_SINE: (CurveFamily.EASING, CurveParameterization.FIXED),
    CurveLibrary.EASE_OUT_SINE: (CurveFamily.EASING, CurveParameterization.FIXED),
    CurveLibrary.EASE_IN_OUT_SINE: (CurveFamily.EASING, CurveParameterization.FIXED),
    # Easing quad curves - FIXED behavior
    CurveLibrary.EASE_IN_QUAD: (CurveFamily.EASING, CurveParameterization.FIXED),
    CurveLibrary.EASE_OUT_QUAD: (CurveFamily.EASING, CurveParameterization.FIXED),
    CurveLibrary.EASE_IN_OUT_QUAD: (CurveFamily.EASING, CurveParameterization.FIXED),
    # Easing cubic curves - FIXED behavior
    CurveLibrary.EASE_IN_CUBIC: (CurveFamily.EASING, CurveParameterization.FIXED),
    CurveLibrary.EASE_OUT_CUBIC: (CurveFamily.EASING, CurveParameterization.FIXED),
    CurveLibrary.EASE_IN_OUT_CUBIC: (CurveFamily.EASING, CurveParameterization.FIXED),
    # Easing back curves - FIXED behavior
    CurveLibrary.EASE_IN_BACK: (CurveFamily.EASING, CurveParameterization.FIXED),
    CurveLibrary.EASE_OUT_BACK: (CurveFamily.EASING, CurveParameterization.FIXED),
    CurveLibrary.EASE_IN_OUT_BACK: (CurveFamily.EASING, CurveParameterization.FIXED),
    # Dynamic curves - FIXED behavior
    CurveLibrary.BOUNCE_IN: (CurveFamily.DYNAMIC, CurveParameterization.FIXED),
    CurveLibrary.BOUNCE_OUT: (CurveFamily.DYNAMIC, CurveParameterization.FIXED),
    CurveLibrary.ELASTIC_IN: (CurveFamily.DYNAMIC, CurveParameterization.FIXED),
    CurveLibrary.ELASTIC_OUT: (CurveFamily.DYNAMIC, CurveParameterization.FIXED),
    # Parametric curves - PARTIAL (need special adapters)
    CurveLibrary.BEZIER: (CurveFamily.PARAMETRIC, CurveParameterization.PARTIAL),
    CurveLibrary.LISSAJOUS: (CurveFamily.PARAMETRIC, CurveParameterization.PARTIAL),
    CurveLibrary.MOVEMENT_LISSAJOUS: (CurveFamily.PARAMETRIC, CurveParameterization.PARTIAL),
    # Musical curves - TIMING_ONLY
    CurveLibrary.MUSICAL_ACCENT: (CurveFamily.MUSICAL, CurveParameterization.TIMING_ONLY),
    CurveLibrary.MUSICAL_SWELL: (CurveFamily.MUSICAL, CurveParameterization.TIMING_ONLY),
    CurveLibrary.BEAT_PULSE: (CurveFamily.MUSICAL, CurveParameterization.TIMING_ONLY),
    # Motion helpers
    CurveLibrary.ANTICIPATE: (CurveFamily.EASING, CurveParameterization.FIXED),
    CurveLibrary.OVERSHOOT: (CurveFamily.EASING, CurveParameterization.FIXED),
    # Basic curves
    CurveLibrary.LINEAR: (CurveFamily.WAVE, CurveParameterization.TIMING_ONLY),
    CurveLibrary.HOLD: (CurveFamily.WAVE, CurveParameterization.FIXED),
    CurveLibrary.MOVEMENT_LINEAR: (CurveFamily.WAVE, CurveParameterization.TIMING_ONLY),
    CurveLibrary.MOVEMENT_HOLD: (CurveFamily.WAVE, CurveParameterization.FIXED),
}


def get_curve_family(curve: CurveLibrary) -> CurveFamily:
    """Get the family classification for a curve.

    Args:
        curve: Curve to classify

    Returns:
        Curve family

    Raises:
        KeyError: If curve not in taxonomy
    """
    return CURVE_TAXONOMY[curve][0]


def get_curve_parameterization(curve: CurveLibrary) -> CurveParameterization:
    """Get the parameterization level for a curve.

    Args:
        curve: Curve to check

    Returns:
        Parameterization level

    Raises:
        KeyError: If curve not in taxonomy
    """
    return CURVE_TAXONOMY[curve][1]


def is_intensity_parameterizable(curve: CurveLibrary) -> bool:
    """Check if a curve supports intensity parameters.

    Args:
        curve: Curve to check

    Returns:
        True if curve accepts amplitude/frequency (FULL or PARTIAL)
    """
    param = get_curve_parameterization(curve)
    return param in (CurveParameterization.FULL, CurveParameterization.PARTIAL)


def is_fixed_behavior(curve: CurveLibrary) -> bool:
    """Check if a curve has fixed behavior.

    Args:
        curve: Curve to check

    Returns:
        True if curve doesn't accept intensity parameters
    """
    param = get_curve_parameterization(curve)
    return param == CurveParameterization.FIXED
