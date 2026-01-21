"""xLights format adapter for custom curve point arrays.

Converts custom curve points (normalized 0-1) to xLights XML format.
Handles DMX range mapping and formatting for xLights consumption.
"""

from __future__ import annotations

from dataclasses import dataclass

from blinkb0t.core.domains.sequencing.models.curves import CurvePoint, ValueCurveSpec
from blinkb0t.core.utils.math import trunc_to


@dataclass
class CustomCurveSpec:
    """Specification for xLights custom curve (point array).

    Unlike ValueCurveSpec (native curves with p1-p4 parameters), this represents
    a custom curve defined by explicit point values that will be interpolated
    by xLights.

    Custom curves are used when:
    - The curve shape is not available natively in xLights
    - Complex waveforms are needed (Lissajous, Perlin noise, etc.)
    - Physics-based motion (bounce, elastic) is required

    xLights Format:
        Active=TRUE|Id=ID_VALUECURVE_DMX{channel}|Type=Custom|Min={min}|Max={max}|RV={rev}|Values={t1:v1;t2:v2;...}|

    Where:
        - Min/Max: DMX range (0-255 or 0-65535)
        - RV: Reverse flag (TRUE/FALSE)
        - Values: Semicolon-separated time:value pairs
            - time: 0.00-1.00 (normalized position in time window)
            - value: 0.00-1.00 (normalized on 255 scale: dmx_value / 255.0)

    Attributes:
        points: List of CurvePoint with time [0,1] and value in DMX space [min_val, max_val]
        min_val: Minimum DMX value for output range
        max_val: Maximum DMX value for output range
        reverse: Reverse the curve direction
    """

    points: list[CurvePoint]
    min_val: int = 0
    max_val: int = 255
    reverse: bool = False

    def __post_init__(self) -> None:
        """Validate custom curve spec after initialization."""
        if not self.points:
            raise ValueError("Custom curve must have at least one point")

        if self.min_val >= self.max_val:
            raise ValueError(f"min_val ({self.min_val}) must be less than max_val ({self.max_val})")

    def to_xlights_string(self, channel: int) -> str:
        """Convert custom curve to xLights XML parameter string.

        NEW APPROACH:
        - Points contain DMX values (e.g., [75, 137.5, 200])
        - Normalize to [0-1] on 255 scale: value / 255.0
        - Output: time:normalized_value pairs

        Args:
            channel: DMX channel number (1-512)

        Returns:
            xLights custom curve parameter string:
            "Active=TRUE|Id=ID_VALUECURVE_DMX{channel}|Type=Custom|Min=0.00|Max=255.00|RV={rev}|Values={t:v;t:v;...}|"

        Examples:
            >>> # Example: Pan curve for range [75, 200]
            >>> points = [
            ...     CurvePoint(time=0.0, value=75.0),   # Min DMX
            ...     CurvePoint(time=0.5, value=200.0),  # Max DMX
            ...     CurvePoint(time=1.0, value=75.0)    # Min DMX
            ... ]
            >>> spec = CustomCurveSpec(points, min_val=0, max_val=255)
            >>> spec.to_xlights_string(11)
            # Output: Values=0.00:0.29;0.50:0.78;1.00:0.29 (normalized on 255 scale)
        """
        # Build normalized time:value pairs
        # Time is already normalized [0, 1]
        # Value needs to be normalized: dmx_value / 255.0
        pairs = []
        for point in self.points:
            # Normalize DMX value to 0-1 on 255 scale
            normalized_value = point.value / 255.0
            # Format is time:value
            # Use 4 decimal places for time to ensure even distribution (supports up to ~1000 points)
            # Use 2 decimal places for value (normalized 0-1 range)
            pair = f"{trunc_to(point.time, 4):.4f}:{trunc_to(normalized_value, 2):.2f}"
            pairs.append(pair)

        # Join with semicolons
        values_str = ";".join(pairs)

        # Build xLights parameter string
        # Min/Max are always 0 and 255 (xLights applies its own scaling)
        parts = [
            "Active=TRUE",
            f"Id=ID_VALUECURVE_DMX{channel}",
            "Type=Custom",
            "Min=0.00",
            "Max=255.00",
            f"RV={'TRUE' if self.reverse else 'FALSE'}",
            f"Values={values_str}",
        ]

        # xLights format requires trailing pipe
        return "|".join(parts) + "|"


class XLightsAdapter:
    """Unified adapter for converting curve specifications to xLights format.

    Provides a single interface for handling both:
    - Native curves (ValueCurveSpec with p1-p4 parameters)
    - Custom curves (point arrays)

    This abstraction simplifies the integration layer, allowing callers
    to work with curves without knowing whether they're native or custom.
    """

    @staticmethod
    def native_to_xlights(spec: ValueCurveSpec, channel: int) -> str:
        """Convert native curve spec to xLights format.

        Args:
            spec: Native curve specification (SINE, RAMP, etc.)
            channel: DMX channel number (1-512)

        Returns:
            xLights native curve parameter string

        Examples:
            >>> from blinkb0t.core.domains.sequencing.infrastructure.curves.enums import NativeCurveType
            >>> spec = ValueCurveSpec(
            ...     type=NativeCurveType.SINE,
            ...     p1=128.0,
            ...     p2=60.0,
            ...     min_val=0,
            ...     max_val=255
            ... )
            >>> XLightsAdapter.native_to_xlights(spec, 11)
            'Active=TRUE|Id=ID_VALUECURVE_DMX11|Type=Sine|Min=0|Max=255|P1=128.00|P2=60.00|RV=FALSE|'
        """
        return spec.to_xlights_string(channel)

    @staticmethod
    def custom_to_xlights(
        points: list[CurvePoint],
        channel: int,
        dmx_min: int = 0,
        dmx_max: int = 255,
        reverse: bool = False,
    ) -> str:
        """Convert custom curve points to xLights format.

        Args:
            points: List of normalized curve points (time and value in [0, 1])
            channel: DMX channel number (1-512)
            dmx_min: Minimum DMX output value (default: 0)
            dmx_max: Maximum DMX output value (default: 255)
            reverse: Reverse the curve direction (default: False)

        Returns:
            xLights custom curve parameter string with normalized time:value pairs

        Raises:
            ValueError: If points list is empty or DMX range is invalid

        Examples:
            >>> points = [
            ...     CurvePoint(time=0.0, value=0.0),
            ...     CurvePoint(time=0.25, value=0.5),
            ...     CurvePoint(time=0.5, value=1.0),
            ...     CurvePoint(time=0.75, value=0.5),
            ...     CurvePoint(time=1.0, value=0.0)
            ... ]
            >>> XLightsAdapter.custom_to_xlights(points, 11, dmx_min=0, dmx_max=255)
            'Active=TRUE|Id=ID_VALUECURVE_DMX11|Type=Custom|Min=0.00|Max=255.00|RV=FALSE|Values=0.00:0.00;0.25:0.50;0.50:1.00;0.75:0.50;1.00:0.00|'
        """
        spec = CustomCurveSpec(points, dmx_min, dmx_max, reverse)
        return spec.to_xlights_string(channel)

    @staticmethod
    def format_curve_string(
        curve_type: str,  # "native" or "custom"
        spec_or_points: ValueCurveSpec | list[CurvePoint],
        channel: int,
        dmx_min: int = 0,
        dmx_max: int = 255,
    ) -> str:
        """Universal curve formatter - routes to appropriate method.

        Convenience method that automatically determines the correct
        conversion path based on curve type.

        Args:
            curve_type: "native" or "custom"
            spec_or_points: Either ValueCurveSpec or list[CurvePoint]
            channel: DMX channel number
            dmx_min: Minimum DMX value (for custom curves)
            dmx_max: Maximum DMX value (for custom curves)

        Returns:
            xLights-formatted curve string

        Raises:
            ValueError: If curve_type is unknown or spec_or_points type doesn't match
        """
        if curve_type == "native":
            if not isinstance(spec_or_points, ValueCurveSpec):
                raise ValueError("Native curve requires ValueCurveSpec")
            return XLightsAdapter.native_to_xlights(spec_or_points, channel)

        elif curve_type == "custom":
            if not isinstance(spec_or_points, list):
                raise ValueError("Custom curve requires list[CurvePoint]")
            return XLightsAdapter.custom_to_xlights(spec_or_points, channel, dmx_min, dmx_max)

        else:
            raise ValueError(f"Unknown curve type: {curve_type}")
