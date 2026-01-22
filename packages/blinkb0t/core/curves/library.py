"""Curve library for registering built-in curve generators."""

from __future__ import annotations

from enum import Enum

from blinkb0t.core.curves.generators import (
    generate_anticipate,
    generate_bezier,
    generate_bounce_in,
    generate_bounce_out,
    generate_ease_in_back,
    generate_ease_in_cubic,
    generate_ease_in_expo,
    generate_ease_in_out_back,
    generate_ease_in_out_cubic,
    generate_ease_in_out_expo,
    generate_ease_in_out_quad,
    generate_ease_in_out_sine,
    generate_ease_in_quad,
    generate_ease_in_sine,
    generate_ease_out_back,
    generate_ease_out_cubic,
    generate_ease_out_expo,
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
    generate_overshoot,
    generate_perlin_noise,
    generate_pulse,
    generate_simplex_noise,
    generate_sine,
    generate_triangle,
)
from blinkb0t.core.curves.registry import CurveGeneratorSpec, CurveRegistry
from blinkb0t.core.curves.semantics import CurveKind


class CurveId(str, Enum):
    """Identifiers for built-in curves."""

    LINEAR = "linear"
    HOLD = "hold"
    SINE = "sine"
    TRIANGLE = "triangle"
    PULSE = "pulse"

    EASE_IN_SINE = "ease_in_sine"
    EASE_OUT_SINE = "ease_out_sine"
    EASE_IN_OUT_SINE = "ease_in_out_sine"
    EASE_IN_QUAD = "ease_in_quad"
    EASE_OUT_QUAD = "ease_out_quad"
    EASE_IN_OUT_QUAD = "ease_in_out_quad"
    EASE_IN_CUBIC = "ease_in_cubic"
    EASE_OUT_CUBIC = "ease_out_cubic"
    EASE_IN_OUT_CUBIC = "ease_in_out_cubic"
    EASE_IN_EXPO = "ease_in_expo"
    EASE_OUT_EXPO = "ease_out_expo"
    EASE_IN_OUT_EXPO = "ease_in_out_expo"
    EASE_IN_BACK = "ease_in_back"
    EASE_OUT_BACK = "ease_out_back"
    EASE_IN_OUT_BACK = "ease_in_out_back"

    BOUNCE_IN = "bounce_in"
    BOUNCE_OUT = "bounce_out"
    ELASTIC_IN = "elastic_in"
    ELASTIC_OUT = "elastic_out"

    PERLIN_NOISE = "perlin_noise"
    SIMPLEX_NOISE = "simplex_noise"

    BEZIER = "bezier"
    LISSAJOUS = "lissajous"

    ANTICIPATE = "anticipate"
    OVERSHOOT = "overshoot"

    MOVEMENT_LINEAR = "movement_linear"
    MOVEMENT_HOLD = "movement_hold"
    MOVEMENT_SINE = "movement_sine"
    MOVEMENT_TRIANGLE = "movement_triangle"
    MOVEMENT_PULSE = "movement_pulse"


_DEFAULT_SAMPLES = 64


def build_default_registry() -> CurveRegistry:
    """Construct a registry containing all built-in curves."""
    registry = CurveRegistry()

    def register(curve_id: CurveId, generator, kind: CurveKind) -> None:
        registry.register(
            CurveGeneratorSpec(
                curve_id=curve_id.value,
                generator=generator,
                kind=kind,
                default_samples=_DEFAULT_SAMPLES,
            )
        )

    # Base curves
    register(CurveId.LINEAR, generate_linear, CurveKind.DIMMER_ABSOLUTE)
    register(CurveId.HOLD, generate_hold, CurveKind.DIMMER_ABSOLUTE)
    register(CurveId.SINE, generate_sine, CurveKind.DIMMER_ABSOLUTE)
    register(CurveId.TRIANGLE, generate_triangle, CurveKind.DIMMER_ABSOLUTE)
    register(CurveId.PULSE, generate_pulse, CurveKind.DIMMER_ABSOLUTE)

    # Easing
    register(CurveId.EASE_IN_SINE, generate_ease_in_sine, CurveKind.DIMMER_ABSOLUTE)
    register(CurveId.EASE_OUT_SINE, generate_ease_out_sine, CurveKind.DIMMER_ABSOLUTE)
    register(
        CurveId.EASE_IN_OUT_SINE, generate_ease_in_out_sine, CurveKind.DIMMER_ABSOLUTE
    )
    register(CurveId.EASE_IN_QUAD, generate_ease_in_quad, CurveKind.DIMMER_ABSOLUTE)
    register(CurveId.EASE_OUT_QUAD, generate_ease_out_quad, CurveKind.DIMMER_ABSOLUTE)
    register(
        CurveId.EASE_IN_OUT_QUAD, generate_ease_in_out_quad, CurveKind.DIMMER_ABSOLUTE
    )
    register(CurveId.EASE_IN_CUBIC, generate_ease_in_cubic, CurveKind.DIMMER_ABSOLUTE)
    register(CurveId.EASE_OUT_CUBIC, generate_ease_out_cubic, CurveKind.DIMMER_ABSOLUTE)
    register(
        CurveId.EASE_IN_OUT_CUBIC, generate_ease_in_out_cubic, CurveKind.DIMMER_ABSOLUTE
    )
    register(CurveId.EASE_IN_EXPO, generate_ease_in_expo, CurveKind.DIMMER_ABSOLUTE)
    register(CurveId.EASE_OUT_EXPO, generate_ease_out_expo, CurveKind.DIMMER_ABSOLUTE)
    register(
        CurveId.EASE_IN_OUT_EXPO, generate_ease_in_out_expo, CurveKind.DIMMER_ABSOLUTE
    )
    register(CurveId.EASE_IN_BACK, generate_ease_in_back, CurveKind.DIMMER_ABSOLUTE)
    register(CurveId.EASE_OUT_BACK, generate_ease_out_back, CurveKind.DIMMER_ABSOLUTE)
    register(
        CurveId.EASE_IN_OUT_BACK, generate_ease_in_out_back, CurveKind.DIMMER_ABSOLUTE
    )

    # Dynamics
    register(CurveId.BOUNCE_IN, generate_bounce_in, CurveKind.DIMMER_ABSOLUTE)
    register(CurveId.BOUNCE_OUT, generate_bounce_out, CurveKind.DIMMER_ABSOLUTE)
    register(CurveId.ELASTIC_IN, generate_elastic_in, CurveKind.DIMMER_ABSOLUTE)
    register(CurveId.ELASTIC_OUT, generate_elastic_out, CurveKind.DIMMER_ABSOLUTE)

    # Noise
    register(CurveId.PERLIN_NOISE, generate_perlin_noise, CurveKind.DIMMER_ABSOLUTE)
    register(CurveId.SIMPLEX_NOISE, generate_simplex_noise, CurveKind.DIMMER_ABSOLUTE)

    # Parametric
    register(CurveId.BEZIER, generate_bezier, CurveKind.DIMMER_ABSOLUTE)
    register(CurveId.LISSAJOUS, generate_lissajous, CurveKind.DIMMER_ABSOLUTE)

    # Motion helpers
    register(CurveId.ANTICIPATE, generate_anticipate, CurveKind.DIMMER_ABSOLUTE)
    register(CurveId.OVERSHOOT, generate_overshoot, CurveKind.DIMMER_ABSOLUTE)

    # Movement curves
    register(CurveId.MOVEMENT_LINEAR, generate_movement_linear, CurveKind.MOVEMENT_OFFSET)
    register(CurveId.MOVEMENT_HOLD, generate_movement_hold, CurveKind.MOVEMENT_OFFSET)
    register(CurveId.MOVEMENT_SINE, generate_movement_sine, CurveKind.MOVEMENT_OFFSET)
    register(
        CurveId.MOVEMENT_TRIANGLE,
        generate_movement_triangle,
        CurveKind.MOVEMENT_OFFSET,
    )
    register(CurveId.MOVEMENT_PULSE, generate_movement_pulse, CurveKind.MOVEMENT_OFFSET)

    return registry
