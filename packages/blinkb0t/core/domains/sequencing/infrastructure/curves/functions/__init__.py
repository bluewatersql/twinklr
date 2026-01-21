"""Curve generation functions.

Pure mathematical functions for generating various curve shapes.
Organized by category: basic, easing, motion, advanced, and native equivalents.

All functions take normalized time array [0, 1] and return normalized values [0, 1].
"""

from blinkb0t.core.domains.sequencing.infrastructure.curves.functions.advanced import (
    bezier,
    lissajous,
    perlin_noise,
    simplex_noise,
)
from blinkb0t.core.domains.sequencing.infrastructure.curves.functions.basic import (
    cosine,
    s_curve,
    smooth_step,
    smoother_step,
    square,
    triangle,
)
from blinkb0t.core.domains.sequencing.infrastructure.curves.functions.easing import (
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
)
from blinkb0t.core.domains.sequencing.infrastructure.curves.functions.motion import (
    anticipate,
    bounce_in,
    bounce_out,
    elastic_in,
    elastic_out,
    overshoot,
)
from blinkb0t.core.domains.sequencing.infrastructure.curves.functions.musical import (
    beat_pulse,
    musical_accent,
    musical_swell,
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

__all__ = [
    # Native equivalents (for blending)
    "flat_x",
    "ramp_x",
    "sine_x",
    "abs_sine_x",
    "parabolic_x",
    "logarithmic_x",
    "exponential_x",
    "saw_tooth_x",
    # Basic
    "cosine",
    "triangle",
    "s_curve",
    "square",
    "smooth_step",
    "smoother_step",
    # Easing - Sine
    "ease_in_sine",
    "ease_out_sine",
    "ease_in_out_sine",
    # Easing - Quad
    "ease_in_quad",
    "ease_out_quad",
    "ease_in_out_quad",
    # Easing - Cubic
    "ease_in_cubic",
    "ease_out_cubic",
    "ease_in_out_cubic",
    # Easing - Exponential
    "ease_in_expo",
    "ease_out_expo",
    "ease_in_out_expo",
    # Easing - Back/Overshoot
    "ease_in_back",
    "ease_out_back",
    "ease_in_out_back",
    # Motion
    "bounce_in",
    "bounce_out",
    "elastic_in",
    "elastic_out",
    "anticipate",
    "overshoot",
    # Musical beat-aligned
    "musical_accent",
    "musical_swell",
    "beat_pulse",
    # Advanced
    "perlin_noise",
    "simplex_noise",
    "lissajous",
    "bezier",
]
