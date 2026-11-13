"""Event intensity to xLights brightness.

Intensity is the planner's categorical level resolved to 0.0-1.0. It also drives
effect energy and density, where a low value is meaningful. As a brightness it is
not: 15% brightness reads as dark on a display, so the quietest level is lifted to
a visible floor and the remaining range is spread above it.
"""

from __future__ import annotations

# Brightness of an event at intensity 0.0, as a fraction of full brightness.
MIN_VISIBLE_BRIGHTNESS = 0.35


def intensity_to_brightness(intensity: float) -> float:
    """Map an event intensity (0.0-1.0) to a brightness fraction.

    Args:
        intensity: Normalized event intensity.

    Returns:
        Brightness in ``MIN_VISIBLE_BRIGHTNESS``-1.0, monotonic in ``intensity``.
    """
    clamped = max(0.0, min(1.0, intensity))
    return MIN_VISIBLE_BRIGHTNESS + (1.0 - MIN_VISIBLE_BRIGHTNESS) * clamped


__all__ = [
    "MIN_VISIBLE_BRIGHTNESS",
    "intensity_to_brightness",
]
