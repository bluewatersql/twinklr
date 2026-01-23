"""DMX conversion helpers for normalized curves."""

from __future__ import annotations

from blinkb0t.core.curves.models import CurvePoint


def movement_curve_to_dmx(
    points: list[CurvePoint],
    base_dmx: float,
    amplitude_dmx: float,
    clamp_min: float,
    clamp_max: float,
) -> list[CurvePoint]:
    """Convert offset-centered movement curve to DMX and normalize for xLights.

    Movement curves are offset-centered around 0.5. We apply the offset formula,
    clamp to boundaries, then normalize for xLights export.

    Formula: dmx = base_dmx + amplitude_dmx * (v - 0.5), then clamp, then normalize

    Args:
        points: Normalized curve points [0,1] centered at 0.5
        base_dmx: Base DMX position (0-255)
        amplitude_dmx: Movement amplitude (0-255)
        clamp_min: Minimum DMX boundary (0-255)
        clamp_max: Maximum DMX boundary (0-255)

    Returns:
        Normalized curve points [0,1] representing the final DMX values
    """
    result: list[CurvePoint] = []
    for p in points:
        # Apply offset-centered formula
        dmx_value = base_dmx + amplitude_dmx * (p.v - 0.5)
        # Clamp to boundaries
        clamped = max(clamp_min, min(clamp_max, dmx_value))
        # Normalize back to [0,1] for xLights value curve format
        normalized = clamped / 255.0
        result.append(CurvePoint(t=p.t, v=normalized))
    return result


def dimmer_curve_to_dmx(
    points: list[CurvePoint],
    clamp_min: float,
    clamp_max: float,
) -> list[CurvePoint]:
    """Convert absolute dimmer curve to DMX and normalize for xLights.

    Dimmer curves are absolute [0,1]. We scale to the DMX range,
    clamp to boundaries, then normalize for xLights export.

    Formula: dmx = clamp_min + v * (clamp_max - clamp_min), then normalize

    Args:
        points: Normalized curve points [0,1] (absolute values)
        clamp_min: Minimum DMX value (0-255)
        clamp_max: Maximum DMX value (0-255)

    Returns:
        Normalized curve points [0,1] representing the final DMX values
    """
    result: list[CurvePoint] = []
    for p in points:
        # Map [0,1] to [clamp_min, clamp_max] DMX range
        dmx_value = clamp_min + p.v * (clamp_max - clamp_min)
        # Clamp to boundaries (should already be in range)
        clamped = max(clamp_min, min(clamp_max, dmx_value))
        # Normalize back to [0,1] for xLights value curve format
        normalized = clamped / 255.0
        result.append(CurvePoint(t=p.t, v=normalized))
    return result


# Backwards compatibility alias
scale_curve_to_dmx_range = dimmer_curve_to_dmx
