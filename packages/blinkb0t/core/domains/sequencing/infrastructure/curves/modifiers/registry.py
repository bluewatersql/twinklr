"""Curve modifier registry and application.

Central registry for curve modifiers with application logic.
"""

from collections.abc import Callable

from blinkb0t.core.domains.sequencing.infrastructure.curves.enums import CurveModifier
from blinkb0t.core.domains.sequencing.infrastructure.curves.modifiers.functions import (
    reverse,
)
from blinkb0t.core.domains.sequencing.models.curves import CurvePoint

# Type alias for modifier functions
ModifierFunction = Callable[[list[CurvePoint]], list[CurvePoint]]


# Registry: Maps each CurveModifier to its implementation function
ModifierRegistry: dict[CurveModifier, ModifierFunction] = {
    CurveModifier.REVERSE: reverse,
    # Future modifiers can be added here:
    # CurveModifier.WRAP: wrap,
    # CurveModifier.BOUNCE: bounce,
    # CurveModifier.MIRROR: mirror,
    # CurveModifier.REPEAT: repeat,
    # CurveModifier.PINGPONG: pingpong,
}


def apply_modifiers(
    points: list[CurvePoint],
    modifiers: list[str],
) -> list[CurvePoint]:
    """Apply a sequence of modifiers to curve points.

    Modifiers are applied in order. Unknown modifiers are skipped gracefully.

    Args:
        points: Original curve points
        modifiers: List of modifier names to apply (e.g., ["reverse", "wrap"])

    Returns:
        Curve points with all modifiers applied in sequence

    Examples:
        >>> points = [CurvePoint(time=0.0, value=0.0), CurvePoint(time=1.0, value=1.0)]
        >>> result = apply_modifiers(points, ["reverse"])
        >>> result[0].value  # 1.0
        >>> result[1].value  # 0.0
    """
    result = points

    for modifier_str in modifiers:
        try:
            # Parse modifier enum
            modifier = CurveModifier(modifier_str)
        except ValueError:
            # Skip unknown modifiers gracefully
            continue

        # Get modifier function from registry
        modifier_func = ModifierRegistry.get(modifier)
        if modifier_func is not None:
            result = modifier_func(result)

    return result
