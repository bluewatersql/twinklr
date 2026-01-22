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
    """Convert offset-centered movement curve to DMX values."""
    result: list[CurvePoint] = []
    for p in points:
        value = base_dmx + amplitude_dmx * (p.v - 0.5)
        clamped = max(clamp_min, min(clamp_max, value))
        result.append(CurvePoint(t=p.t, v=clamped))
    return result


def dimmer_curve_to_dmx(
    points: list[CurvePoint],
    clamp_min: float,
    clamp_max: float,
) -> list[CurvePoint]:
    """Convert absolute dimmer curve to DMX values."""
    result: list[CurvePoint] = []
    for p in points:
        value = clamp_min + p.v * (clamp_max - clamp_min)
        clamped = max(clamp_min, min(clamp_max, value))
        result.append(CurvePoint(t=p.t, v=clamped))
    return result
