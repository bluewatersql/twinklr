"""Motion enums - motion verb vocabulary.

Defines motion primitives for choreography.
"""

from enum import Enum


class MotionVerb(str, Enum):
    """Motion primitives for choreography.

    Describes the type of motion applied to display elements.
    Suitable for Christmas light displays (residential/commercial).

    Attributes:
        NONE: No motion (static).
        PULSE: Rhythmic brightness change.
        SWEEP: Linear motion across display.
        WAVE: Smooth wave-like motion.
        RIPPLE: Expanding wave propagation.
        CHASE: Sequential activation pattern.
        STROBE: Rapid on/off (safe rates <8Hz).
        BOUNCE: Back-and-forth motion.
        SPARKLE: Random twinkling elements.
        FADE: Gradual brightness transition.
        WIPE: Progressive reveal/conceal.
        TWINKLE: Slow random brightness variation.
        SHIMMER: Subtle brightness oscillation.
        ROLL: Continuous rotation.
        FLIP: 180-degree position change.
    """

    NONE = "NONE"
    PULSE = "PULSE"
    SWEEP = "SWEEP"
    WAVE = "WAVE"
    RIPPLE = "RIPPLE"
    CHASE = "CHASE"
    STROBE = "STROBE"
    BOUNCE = "BOUNCE"
    SPARKLE = "SPARKLE"
    FADE = "FADE"
    WIPE = "WIPE"
    TWINKLE = "TWINKLE"
    SHIMMER = "SHIMMER"
    ROLL = "ROLL"
    FLIP = "FLIP"
