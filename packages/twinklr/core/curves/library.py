"""Curve library for registering built-in curve generators."""

from __future__ import annotations

from enum import Enum
from typing import Any

from blinkb0t.core.curves.defaults import (
    DEFAULT_MOVEMENT_PARAMS,
    DEFAULT_PARAMETRIC_PARAMS,
    DEFAULT_WAVE_PARAMS,
)
from blinkb0t.core.curves.functions import (
    generate_anticipate,
    generate_beat_pulse,
    generate_bezier,
    generate_bounce_in,
    generate_bounce_out,
    generate_cosine,
    generate_ease_in_back,
    generate_ease_in_cubic,
    generate_ease_in_out_back,
    generate_ease_in_out_cubic,
    generate_ease_in_out_quad,
    generate_ease_in_out_sine,
    generate_ease_in_quad,
    generate_ease_in_sine,
    generate_ease_out_back,
    generate_ease_out_cubic,
    generate_ease_out_quad,
    generate_ease_out_sine,
    generate_elastic_in,
    generate_elastic_out,
    generate_hold,
    generate_linear,
    generate_lissajous,
    generate_movement_hold,
    generate_movement_linear,
    generate_movement_pulse,
    generate_movement_sine,
    generate_movement_triangle,
    generate_musical_accent,
    generate_musical_swell,
    generate_overshoot,
    generate_perlin_noise,
    generate_pulse,
    generate_s_curve,
    generate_sine,
    generate_smooth_step,
    generate_smoother_step,
    generate_square,
    generate_triangle,
)
from blinkb0t.core.curves.registry import CurveDefinition, CurveRegistry
from blinkb0t.core.curves.semantics import CurveKind


class CurveLibrary(str, Enum):
    """Identifiers for built-in curves."""

    # Basic Waves
    LINEAR = "linear"
    HOLD = "hold"
    SINE = "sine"
    PULSE = "pulse"
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

    # Parametric
    BEZIER = "bezier"  # Bezier curve (controllable control points)
    LISSAJOUS = "lissajous"  # Figure-8 like patterns (Lissajous curves)

    # Advanced Easing
    ANTICIPATE = "anticipate"  # Pulls back before moving forward
    OVERSHOOT = "overshoot"  # Overshoots target then settles

    # Movement
    MOVEMENT_LINEAR = "movement_linear"  # Linear ramp
    MOVEMENT_HOLD = "movement_hold"  # Hold at current value
    MOVEMENT_SINE = "movement_sine"  # Sine wave
    MOVEMENT_TRIANGLE = "movement_triangle"  # Triangle wave
    MOVEMENT_PULSE = "movement_pulse"  # Pulse wave
    MOVEMENT_PERLIN_NOISE = "movement_perlin_noise"  # Perlin noise as movement offset
    MOVEMENT_COSINE = "movement_cosine"
    MOVEMENT_LISSAJOUS = "movement_lissajous"


_DEFAULT_SAMPLES = 64


def build_default_registry() -> CurveRegistry:
    """Construct a registry containing all built-in curves."""
    registry = CurveRegistry()

    def register(
        curve_id: CurveLibrary, generator, kind: CurveKind, params: dict[str, Any] | None = None
    ) -> None:
        registry.register(
            CurveDefinition(
                curve_id=curve_id.value,
                generator=generator,
                kind=kind,
                default_samples=_DEFAULT_SAMPLES,
                default_params=params,
            )
        )

    # Base curves - USE GLOBAL DEFAULTS
    register(CurveLibrary.LINEAR, generate_linear, CurveKind.DIMMER_ABSOLUTE, params={})
    register(CurveLibrary.HOLD, generate_hold, CurveKind.DIMMER_ABSOLUTE, params={})
    register(
        CurveLibrary.SINE, generate_sine, CurveKind.DIMMER_ABSOLUTE, params=DEFAULT_WAVE_PARAMS
    )
    register(
        CurveLibrary.TRIANGLE,
        generate_triangle,
        CurveKind.DIMMER_ABSOLUTE,
        params=DEFAULT_WAVE_PARAMS,
    )
    register(
        CurveLibrary.PULSE, generate_pulse, CurveKind.DIMMER_ABSOLUTE, params=DEFAULT_WAVE_PARAMS
    )
    register(
        CurveLibrary.COSINE, generate_cosine, CurveKind.DIMMER_ABSOLUTE, params=DEFAULT_WAVE_PARAMS
    )
    register(CurveLibrary.SQUARE, generate_square, CurveKind.DIMMER_ABSOLUTE, params={})
    register(CurveLibrary.S_CURVE, generate_s_curve, CurveKind.DIMMER_ABSOLUTE, params={})
    register(CurveLibrary.SMOOTH_STEP, generate_smooth_step, CurveKind.DIMMER_ABSOLUTE, params={})
    register(
        CurveLibrary.SMOOTHER_STEP, generate_smoother_step, CurveKind.DIMMER_ABSOLUTE, params={}
    )

    # Easing
    register(CurveLibrary.EASE_IN_SINE, generate_ease_in_sine, CurveKind.DIMMER_ABSOLUTE)
    register(CurveLibrary.EASE_OUT_SINE, generate_ease_out_sine, CurveKind.DIMMER_ABSOLUTE)
    register(CurveLibrary.EASE_IN_OUT_SINE, generate_ease_in_out_sine, CurveKind.DIMMER_ABSOLUTE)
    register(CurveLibrary.EASE_IN_QUAD, generate_ease_in_quad, CurveKind.DIMMER_ABSOLUTE)
    register(CurveLibrary.EASE_OUT_QUAD, generate_ease_out_quad, CurveKind.DIMMER_ABSOLUTE)
    register(CurveLibrary.EASE_IN_OUT_QUAD, generate_ease_in_out_quad, CurveKind.DIMMER_ABSOLUTE)
    register(CurveLibrary.EASE_IN_CUBIC, generate_ease_in_cubic, CurveKind.DIMMER_ABSOLUTE)
    register(CurveLibrary.EASE_OUT_CUBIC, generate_ease_out_cubic, CurveKind.DIMMER_ABSOLUTE)
    register(CurveLibrary.EASE_IN_OUT_CUBIC, generate_ease_in_out_cubic, CurveKind.DIMMER_ABSOLUTE)
    register(CurveLibrary.EASE_IN_BACK, generate_ease_in_back, CurveKind.DIMMER_ABSOLUTE)
    register(CurveLibrary.EASE_OUT_BACK, generate_ease_out_back, CurveKind.DIMMER_ABSOLUTE)
    register(CurveLibrary.EASE_IN_OUT_BACK, generate_ease_in_out_back, CurveKind.DIMMER_ABSOLUTE)

    # Dynamics
    register(CurveLibrary.BOUNCE_IN, generate_bounce_in, CurveKind.DIMMER_ABSOLUTE)
    register(CurveLibrary.BOUNCE_OUT, generate_bounce_out, CurveKind.DIMMER_ABSOLUTE)
    register(CurveLibrary.ELASTIC_IN, generate_elastic_in, CurveKind.DIMMER_ABSOLUTE)
    register(CurveLibrary.ELASTIC_OUT, generate_elastic_out, CurveKind.DIMMER_ABSOLUTE)

    # Noise
    register(CurveLibrary.MOVEMENT_PERLIN_NOISE, generate_perlin_noise, CurveKind.MOVEMENT_OFFSET)

    # Parametric - USE PARAMETRIC DEFAULTS
    register(CurveLibrary.BEZIER, generate_bezier, CurveKind.DIMMER_ABSOLUTE, params={})
    register(
        CurveLibrary.LISSAJOUS,
        generate_lissajous,
        CurveKind.DIMMER_ABSOLUTE,
        params=DEFAULT_PARAMETRIC_PARAMS
        | {"b": 2, "delta": 0},  # Merge defaults with specific params
    )

    # Motion helpers
    register(CurveLibrary.ANTICIPATE, generate_anticipate, CurveKind.DIMMER_ABSOLUTE)
    register(CurveLibrary.OVERSHOOT, generate_overshoot, CurveKind.DIMMER_ABSOLUTE)

    # Movement curves - USE MOVEMENT/WAVE DEFAULTS
    register(
        CurveLibrary.MOVEMENT_LINEAR, generate_movement_linear, CurveKind.MOVEMENT_OFFSET, params={}
    )
    register(
        CurveLibrary.MOVEMENT_HOLD, generate_movement_hold, CurveKind.MOVEMENT_OFFSET, params={}
    )
    register(
        CurveLibrary.MOVEMENT_SINE,
        generate_movement_sine,
        CurveKind.MOVEMENT_OFFSET,
        params=DEFAULT_WAVE_PARAMS,
    )
    register(
        CurveLibrary.MOVEMENT_TRIANGLE,
        generate_movement_triangle,
        CurveKind.MOVEMENT_OFFSET,
        params=DEFAULT_MOVEMENT_PARAMS,
    )
    register(
        CurveLibrary.MOVEMENT_PULSE,
        generate_movement_pulse,
        CurveKind.MOVEMENT_OFFSET,
        params={
            "cycles": 1.0,
            "duty_cycle": 0.5,
            "high": 1.0,
            "low": 0.0,
            "frequency": 1.0,
        },
    )
    register(
        CurveLibrary.MOVEMENT_COSINE,
        generate_cosine,
        CurveKind.MOVEMENT_OFFSET,
        params=DEFAULT_WAVE_PARAMS,
    )
    register(
        CurveLibrary.MOVEMENT_LISSAJOUS,
        generate_lissajous,
        CurveKind.MOVEMENT_OFFSET,
        params=DEFAULT_PARAMETRIC_PARAMS | {"b": 2, "delta": 0},
    )

    # Musical curves
    register(CurveLibrary.MUSICAL_ACCENT, generate_musical_accent, CurveKind.DIMMER_ABSOLUTE)
    register(CurveLibrary.MUSICAL_SWELL, generate_musical_swell, CurveKind.DIMMER_ABSOLUTE)
    register(CurveLibrary.BEAT_PULSE, generate_beat_pulse, CurveKind.DIMMER_ABSOLUTE)

    return registry
