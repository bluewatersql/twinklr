"""Curve modifier functions.

Individual modifier functions that transform curve points.
All modifiers take list[CurvePoint] and return list[CurvePoint].
"""

from blinkb0t.core.domains.sequencing.models.curves import CurvePoint


def reverse(points: list[CurvePoint]) -> list[CurvePoint]:
    """Reverse curve values (invert vertically).

    Transforms values by computing 1.0 - value, effectively flipping
    the curve vertically. Time values remain unchanged.

    Args:
        points: Original curve points

    Returns:
        Curve points with inverted values

    Examples:
        >>> points = [CurvePoint(time=0.0, value=0.0), CurvePoint(time=1.0, value=1.0)]
        >>> reversed_points = reverse(points)
        >>> reversed_points[0].value  # 1.0
        >>> reversed_points[1].value  # 0.0
    """
    return [CurvePoint(time=p.time, value=1.0 - p.value) for p in points]
