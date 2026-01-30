from __future__ import annotations

from enum import Enum

from twinklr.core.curves.models import CurvePoint


class CurveModifier(str, Enum):
    """Curve transformation modifiers.

    Applied to base curves to create variations without defining new curve types.
    Can be combined for complex effects.
    """

    REVERSE = "reverse"  # Flip curve horizontally (reverse time)
    BOUNCE = "bounce"  # Bounce off boundaries (reflect)
    MIRROR = "mirror"  # Mirror curve vertically (flip values)
    REPEAT = "repeat"  # Repeat curve multiple times
    PINGPONG = "pingpong"  # Alternate forward/reverse repetitions


def reverse_curve(points: list[CurvePoint]) -> list[CurvePoint]:
    """Reverse curve values (invert vertically)."""
    return [CurvePoint(t=1.0 - p.t, v=p.v) for p in reversed(points)]


def mirror_curve(points: list[CurvePoint]) -> list[CurvePoint]:
    """Mirror curve vertically (flip values)."""
    return [CurvePoint(t=p.t, v=1.0 - p.v) for p in points]


def bounce_curve(points: list[CurvePoint]) -> list[CurvePoint]:
    """Bounce or reflect curve off boundaries (0 -> 1 -> 0)."""
    return [CurvePoint(t=p.t, v=1.0 - abs(p.v - 0.5) * 2) for p in points]


def ping_pong_curve(points: list[CurvePoint]) -> list[CurvePoint]:
    """Alternate forward/reverse repetitions."""
    return points[::-1] + points


def repeat_curve(points: list[CurvePoint]) -> list[CurvePoint]:
    """Repeat curve multiple times."""
    return points * 2
