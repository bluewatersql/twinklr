"""Enums for curve engine.

Defines all enumeration types used throughout the curve engine, including:
- CurveSource: Origin of curve definition (native, custom, preset)
- NativeCurveType: xLights native curve types
- CustomCurveType: Custom programmatic curve types
- CurveModifier: Curve transformation modifiers
- CategoricalLevel: LLM-friendly intensity categories
"""

from __future__ import annotations

from enum import Enum


class CurveSource(str, Enum):
    """Source of curve definition.

    Determines how the curve is generated and what parameters are available.

    - NATIVE: xLights built-in curves (Sine, Ramp, etc.) with p1-p4 parameters
    - CUSTOM: Programmatically generated point arrays (Cosine, Triangle, etc.)
    - PRESET: Named configurations that apply modifiers to base curves
    """

    NATIVE = "native"
    CUSTOM = "custom"
    PRESET = "preset"


class NativeCurveType(str, Enum):
    """xLights native curve types.

    These curves are rendered directly by xLights using parametric formulas
    controlled by p1-p4 parameters. More efficient than point arrays.

    Reference: xLights Value Curve types

    NOTE: Internal values are lowercase for compatibility. They are converted
    to title case when writing to XSQ files (xLights requires title case).
    """

    FLAT = "flat"  # Constant value (no variation)
    RAMP = "ramp"  # Linear progression (p1=start, p2=end)
    SINE = "sine"  # Sine wave (p2=amplitude, p4=center)
    ABS_SINE = "abs sine"  # Absolute value of sine wave
    PARABOLIC = "parabolic"  # Parabolic curve (p2=amplitude, p4=center)
    LOGARITHMIC = "logarithmic"  # Logarithmic curve
    EXPONENTIAL = "exponential"  # Exponential curve
    SAW_TOOTH = "saw tooth"  # Sawtooth wave (p1=min, p2=max)


class CustomCurveType(str, Enum):
    """Custom programmatic curve types.

    These curves are generated as point arrays since xLights doesn't support them natively.
    Provides additional curve shapes beyond xLights built-ins.

    Categories:
    - Native Equivalents: Custom implementations of xLights native curves for blending
    - Fundamental Waves: Cosine, Triangle, Square
    - Smooth Transitions: S-Curve, Smoother-Step
    - Advanced Easing: Anticipate, Overshoot
    - Dynamic Effects: Bounce variations, Elastic
    - Natural Motion: Perlin Noise, Spline
    - Parametric: Bezier, Lissajous, Spiral
    """

    # Native Curve Equivalents (custom implementations for blending support)
    FLAT_X = "flat_x"  # Custom version of FLAT (constant value)
    RAMP_X = "ramp_x"  # Custom version of RAMP (linear progression)
    SINE_X = "sine_x"  # Custom version of SINE (sine wave)
    ABS_SINE_X = "abs_sine_x"  # Custom version of ABS_SINE (absolute sine)
    PARABOLIC_X = "parabolic_x"  # Custom version of PARABOLIC (parabolic curve)
    LOGARITHMIC_X = "logarithmic_x"  # Custom version of LOGARITHMIC (log curve)
    EXPONENTIAL_X = "exponential_x"  # Custom version of EXPONENTIAL (exp curve)
    SAW_TOOTH_X = "saw_tooth_x"  # Custom version of SAW_TOOTH (sawtooth wave)

    # Fundamental Waves
    COSINE = "cosine"  # Cosine wave (complementary to sine)
    TRIANGLE = "triangle"  # Triangle wave (linear rise/fall)
    SQUARE = "square"  # Square wave (binary states)

    # Smooth Transitions
    S_CURVE = "s_curve"  # Sigmoid/S-shaped curve
    SMOOTH_STEP = "smooth_step"  # Smooth interpolation (3x^2 - 2x^3)
    SMOOTHER_STEP = "smoother_step"  # Smoother than smoothstep (6x^5 - 15x^4 + 10x^3)

    # Easing Sine Curves
    EASE_IN_SINE = "ease_in_sine"  # Sine ease-in
    EASE_OUT_SINE = "ease_out_sine"  # Sine ease-out
    EASE_IN_OUT_SINE = "ease_in_out_sine"  # Sine ease-in-out

    # Easing Quad Curves
    EASE_IN_QUAD = "ease_in_quad"  # Quadratic ease-in
    EASE_OUT_QUAD = "ease_out_quad"  # Quadratic ease-out
    EASE_IN_OUT_QUAD = "ease_in_out_quad"  # Quadratic ease-in-out

    # Easing Cubic Curves
    EASE_IN_CUBIC = "ease_in_cubic"  # Cubic ease-in
    EASE_OUT_CUBIC = "ease_out_cubic"  # Cubic ease-out
    EASE_IN_OUT_CUBIC = "ease_in_out_cubic"  # Cubic ease-in-out

    # Easing Exponential Curves (library) - Very Dramatic
    EASE_IN_EXPO = "ease_in_expo"  # 2^(10(x-1)) - Very slow start, explosive end
    EASE_OUT_EXPO = "ease_out_expo"  # 1-2^(-10x) - Explosive start, very slow end
    EASE_IN_OUT_EXPO = "ease_in_out_expo"  # Combined - Maximum drama S-curve

    # Easing Back Curves (library) - Anticipation/Overshoot
    EASE_IN_BACK = "ease_in_back"  # Pulls back before moving (anticipation)
    EASE_OUT_BACK = "ease_out_back"  # Overshoots target then settles
    EASE_IN_OUT_BACK = "ease_in_out_back"  # Both anticipation and overshoot

    # Dynamic Effects - Bounce
    BOUNCE_IN = "bounce_in"  # Bounce at start
    BOUNCE_OUT = "bounce_out"  # Bounce at end

    # Dynamic Effects - Elastic
    ELASTIC_IN = "elastic_in"  # Elastic oscillation at start
    ELASTIC_OUT = "elastic_out"  # Elastic oscillation at end

    # Musical Curves - Beat-Aligned Timing
    MUSICAL_ACCENT = "musical_accent"  # Sharp attack (10%), smooth decay (90%)
    MUSICAL_SWELL = "musical_swell"  # Smooth rise (90%), sharp cutoff (10%)
    BEAT_PULSE = "beat_pulse"  # Rhythmic pulse aligned to beat subdivisions

    # Natural Motion - Noise Algorithms
    PERLIN_NOISE = "perlin_noise"  # True Perlin noise (smooth, organic, configurable)
    SIMPLEX_NOISE = "simplex_noise"  # Simplex noise (faster, similar quality)

    # Parametric
    BEZIER = "bezier"  # Bezier curve (controllable control points)
    LISS_AJOUS = "lissajous"  # Figure-8 like patterns (Lissajous curves)

    # Advanced Easing
    ANTICIPATE = "anticipate"  # Pulls back before moving forward
    OVERSHOOT = "overshoot"  # Overshoots target then settles


class CurveModifier(str, Enum):
    """Curve transformation modifiers.

    Applied to base curves to create variations without defining new curve types.
    Can be combined for complex effects.
    """

    REVERSE = "reverse"  # Flip curve horizontally (reverse time)
    WRAP = "wrap"  # Wrap values that exceed boundaries
    BOUNCE = "bounce"  # Bounce off boundaries (reflect)
    MIRROR = "mirror"  # Mirror curve vertically (flip values)
    REPEAT = "repeat"  # Repeat curve multiple times
    PINGPONG = "pingpong"  # Alternate forward/reverse repetitions


class CategoricalLevel(str, Enum):
    """Categorical intensity levels for LLM-friendly parameters (5-level system).

    Replaces complex numerical parameters with intuitive categories.
    Simplifies LLM planning and ensures consistent behavior.

    Ordering: From gentle to extreme (intensity increases)

    Usage in prompts:
    - "Use 'smooth' for gentle audience scans"
    - "Use 'medium' for moderate transitions"
    - "Use 'dramatic' for impactful beat hits"
    - "Use 'intense' for high-energy climax moments"
    - "Use 'extreme' for maximum intensity sections"
    """

    SMOOTH = "smooth"  # Gentle, gradual transitions (20-40% intensity)
    MEDIUM = "medium"  # Moderate transitions (40-50% intensity)
    DRAMATIC = "dramatic"  # Strong, impactful movements (50-75% intensity)
    INTENSE = "intense"  # High-energy, rapid movements (75-90% intensity)
    EXTREME = "extreme"  # Maxed-out, maximum intensity (90-100% intensity)


# Type aliases for convenience
CurveSourceType = CurveSource
IntensityLevel = CategoricalLevel
