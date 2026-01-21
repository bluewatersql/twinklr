"""Curve to DMX Converter for the moving head sequencer.

Converts normalized curves from IR segments to absolute DMX values.
Handles both offset-centered curves (for movement) and absolute
curves (for dimmer).

Conversion modes:
- Offset-centered: dmx = base + (v - 0.5) * amplitude
- Absolute: dmx = lerp(clamp_min, clamp_max, v)
"""

from pydantic import BaseModel, ConfigDict, Field

from blinkb0t.core.curves.models import BaseCurve, CurvePoint, PointsCurve
from blinkb0t.core.sequencer.moving_heads.models.ir import ChannelSegment


class DMXPoint(BaseModel):
    """A point with time in [0,1] and value in DMX range [0,255].

    Unlike CurvePoint which has v in [0,1], DMXPoint holds
    absolute DMX values.

    Attributes:
        t: Time position [0, 1].
        v: DMX value [0, 255].
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    t: float = Field(..., ge=0.0, le=1.0)
    v: int = Field(..., ge=0, le=255)


def convert_offset_centered(
    value: float,
    base_dmx: int,
    amplitude_dmx: int,
    clamp_min: int = 0,
    clamp_max: int = 255,
) -> int:
    """Convert normalized curve value to DMX using offset-centered mode.

    For movement curves where v=0.5 means no motion.
    Formula: dmx = base + (v - 0.5) * amplitude

    Args:
        value: Normalized curve value [0, 1].
        base_dmx: Base DMX value (center position).
        amplitude_dmx: Movement amplitude in DMX units.
        clamp_min: Minimum allowed DMX value.
        clamp_max: Maximum allowed DMX value.

    Returns:
        Clamped DMX value [clamp_min, clamp_max].

    Example:
        >>> convert_offset_centered(0.5, base_dmx=128, amplitude_dmx=64)
        128
        >>> convert_offset_centered(1.0, base_dmx=128, amplitude_dmx=64)
        160
    """
    # Calculate offset from center (v=0.5)
    offset = (value - 0.5) * amplitude_dmx

    # Apply to base
    dmx = base_dmx + offset

    # Clamp to valid range
    return int(max(clamp_min, min(clamp_max, dmx)))


def convert_absolute(
    value: float,
    clamp_min: int = 0,
    clamp_max: int = 255,
) -> int:
    """Convert normalized curve value to DMX using absolute mode.

    For dimmer curves where v=0 is off and v=1 is full.
    Formula: dmx = lerp(clamp_min, clamp_max, v)

    Args:
        value: Normalized curve value [0, 1].
        clamp_min: Minimum DMX output value.
        clamp_max: Maximum DMX output value.

    Returns:
        Clamped DMX value [clamp_min, clamp_max].

    Example:
        >>> convert_absolute(0.0, clamp_min=0, clamp_max=255)
        0
        >>> convert_absolute(1.0, clamp_min=0, clamp_max=255)
        255
    """
    # Clamp input value to [0, 1]
    clamped_value = max(0.0, min(1.0, value))

    # Linear interpolation
    dmx = clamp_min + clamped_value * (clamp_max - clamp_min)

    return int(dmx)


class DMXCurve(BaseModel):
    """A curve with DMX values (0-255).

    Represents a curve that has been converted from normalized
    values to absolute DMX values.

    Attributes:
        points: List of DMXPoints with t in [0,1] and v in DMX range [0,255].

    Example:
        >>> points = [DMXPoint(t=0.0, v=0), DMXPoint(t=1.0, v=255)]
        >>> curve = DMXCurve(points=points)
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    points: list[DMXPoint] = Field(..., min_length=1)

    def to_xlights_string(self, channel: int) -> str:
        """Convert to xLights custom curve format string.

        xLights custom curves use normalized values (0-1) on a 255 scale.
        This method converts DMX values back to normalized for xLights.

        Args:
            channel: DMX channel number for the curve ID.

        Returns:
            xLights-formatted custom curve string.

        Example:
            >>> curve.to_xlights_string(11)
            'Active=TRUE|Id=ID_VALUECURVE_DMX11|Type=Custom|...'
        """
        # Build normalized time:value pairs
        # Value needs to be normalized: dmx_value / 255.0
        pairs = []
        for point in self.points:
            # Normalize DMX value to 0-1 on 255 scale
            normalized_value = point.v / 255.0
            # Format: time:value (4 decimal places for time, 2 for value)
            pair = f"{point.t:.4f}:{normalized_value:.2f}"
            pairs.append(pair)

        values_str = ";".join(pairs)

        # Build xLights parameter string
        parts = [
            "Active=TRUE",
            f"Id=ID_VALUECURVE_DMX{channel}",
            "Type=Custom",
            "Min=0.00",
            "Max=255.00",
            "RV=FALSE",
            f"Values={values_str}",
        ]

        return "|".join(parts) + "|"


def convert_segment_to_dmx(segment: ChannelSegment) -> DMXCurve:
    """Convert an IR segment's curve to DMX values.

    Handles static segments, offset-centered curves, and absolute curves.

    Args:
        segment: IR ChannelSegment to convert.

    Returns:
        DMXCurve with absolute DMX values.

    Example:
        >>> segment = ChannelSegment(...)
        >>> dmx_curve = convert_segment_to_dmx(segment)
    """
    # Handle static segments
    if segment.static_dmx is not None:
        # Create flat curve at static value
        return DMXCurve(
            points=[
                DMXPoint(t=0.0, v=segment.static_dmx),
                DMXPoint(t=1.0, v=segment.static_dmx),
            ]
        )

    # Get curve points
    curve = segment.curve
    if curve is None:
        raise ValueError("Segment has neither static_dmx nor curve")

    # Get points from curve
    points = _get_curve_points(curve)

    # Convert each point
    dmx_points: list[DMXPoint] = []

    for point in points:
        if segment.offset_centered:
            # Offset-centered conversion (movement)
            if segment.base_dmx is None or segment.amplitude_dmx is None:
                raise ValueError("offset_centered segment requires base_dmx and amplitude_dmx")
            dmx_value = convert_offset_centered(
                value=point.v,
                base_dmx=segment.base_dmx,
                amplitude_dmx=segment.amplitude_dmx,
                clamp_min=segment.clamp_min,
                clamp_max=segment.clamp_max,
            )
        else:
            # Absolute conversion (dimmer)
            dmx_value = convert_absolute(
                value=point.v,
                clamp_min=segment.clamp_min,
                clamp_max=segment.clamp_max,
            )

        dmx_points.append(DMXPoint(t=point.t, v=dmx_value))

    return DMXCurve(points=dmx_points)


def _get_curve_points(curve: BaseCurve) -> list[CurvePoint]:
    """Extract points from a curve.

    Currently only supports PointsCurve. Could be extended to
    sample NativeCurve if needed.

    Args:
        curve: Curve to extract points from.

    Returns:
        List of CurvePoints.

    Raises:
        ValueError: If curve type is not supported.
    """
    if isinstance(curve, PointsCurve):
        return list(curve.points)
    else:
        raise ValueError(f"Unsupported curve type: {type(curve).__name__}")
