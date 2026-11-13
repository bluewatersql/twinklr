"""Event intensity to xLights brightness.

Intensity is the planner's categorical level resolved to 0.0-1.0. It also drives
effect energy and density, where a low value is meaningful. As a brightness it is
not: 15% brightness reads as dark on a display, so the quietest level is lifted to
a visible floor and the remaining range is spread above it.

A palette's own intensity scaler composes with the event intensity but cannot take
the result below that floor. Show coordination's focal-role scale is different: it
dims a group on purpose so the lead stands out, so it multiplies the lit brightness
and has its own, lower floor.
"""

from __future__ import annotations

# Brightness of an event at intensity 0.0, as a fraction of full brightness.
MIN_VISIBLE_BRIGHTNESS = 0.35

# Lowest brightness a focal-role scale may dim an event to.
MIN_RESTING_BRIGHTNESS = 0.10


def intensity_to_brightness(intensity: float) -> float:
    """Map an event intensity (0.0-1.0) to a brightness fraction.

    Args:
        intensity: Normalized event intensity.

    Returns:
        Brightness in ``MIN_VISIBLE_BRIGHTNESS``-1.0, monotonic in ``intensity``.
    """
    clamped = max(0.0, min(1.0, intensity))
    return MIN_VISIBLE_BRIGHTNESS + (1.0 - MIN_VISIBLE_BRIGHTNESS) * clamped


def event_brightness_percent(
    intensity: float,
    *,
    palette_brightness: int | None = None,
    scale: float = 1.0,
) -> int:
    """Resolve the xLights brightness (0-100) an event is written with.

    Args:
        intensity: Normalized event intensity.
        palette_brightness: Brightness already on the palette (0-100), from a
            palette intensity scaler. ``None`` means full.
        scale: Focal-role scale from show coordination (1.0 = not dimmed).

    Returns:
        Brightness percent. Never below ``MIN_VISIBLE_BRIGHTNESS`` for an undimmed
        event, and never below ``MIN_RESTING_BRIGHTNESS`` for a dimmed one.
    """
    base = 1.0 if palette_brightness is None else max(0, min(100, palette_brightness)) / 100.0
    lit = max(MIN_VISIBLE_BRIGHTNESS, base * intensity_to_brightness(intensity))
    clamped_scale = max(0.0, min(1.0, scale))
    if clamped_scale < 1.0:
        lit = max(MIN_RESTING_BRIGHTNESS, lit * clamped_scale)
    return round(lit * 100)


__all__ = [
    "MIN_RESTING_BRIGHTNESS",
    "MIN_VISIBLE_BRIGHTNESS",
    "event_brightness_percent",
    "intensity_to_brightness",
]
