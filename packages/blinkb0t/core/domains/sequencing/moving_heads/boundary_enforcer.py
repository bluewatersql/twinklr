"""Centralized boundary enforcement for DMX values.

This module provides a unified service for clamping and validating DMX values
across all channels, with support for:
- Fixture hardware limits
- Avoid-backward constraints for pan
- Channel-specific limits
- Optional geometry constraints
- Value curve parameter validation
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from blinkb0t.core.domains.sequencing.infrastructure.curves.enums import NativeCurveType
from blinkb0t.core.utils.math import clamp

if TYPE_CHECKING:
    from blinkb0t.core.config.fixtures import FixtureInstance

logger = logging.getLogger(__name__)


class BoundaryEnforcer:
    """Centralized boundary enforcement for all DMX values.

    Simple operations delegate to FixtureConfig methods. BoundaryEnforcer only adds
    geometry constraint intersection logic.

    Design principles:
    - FixtureInstance is the single source of truth
    - Fixture limits are always respected (hardware safety)
    - Geometry constraints narrow fixture limits (intersection)
    - Explicit control over which constraints to apply
    - All clamping decisions are logged for debugging
    """

    def __init__(
        self,
        fixture: FixtureInstance,
        geometry_pan_min: int | None = None,
        geometry_pan_max: int | None = None,
        geometry_tilt_min: int | None = None,
        geometry_tilt_max: int | None = None,
    ):
        """Initialize boundary enforcer.

        Args:
            fixture: Fixture instance with configuration
            geometry_pan_min: Optional minimum pan constraint from geometry
            geometry_pan_max: Optional maximum pan constraint from geometry
            geometry_tilt_min: Optional minimum tilt constraint from geometry
            geometry_tilt_max: Optional maximum tilt constraint from geometry
        """
        self.fixture = fixture
        self.geometry_pan_min = geometry_pan_min
        self.geometry_pan_max = geometry_pan_max
        self.geometry_tilt_min = geometry_tilt_min
        self.geometry_tilt_max = geometry_tilt_max

        # Calculate effective pan limits with avoid_backward
        self._pan_effective_min, self._pan_effective_max = self._calculate_avoid_backward_limits()

        logger.debug(
            f"BoundaryEnforcer initialized for {fixture.fixture_id}: "
            f"pan=[{self._pan_effective_min}, {self._pan_effective_max}], "
            f"tilt=[{fixture.config.limits.tilt_min}, {fixture.config.limits.tilt_max}]"
        )

    def _calculate_avoid_backward_limits(self) -> tuple[int, int]:
        """Calculate effective pan limits considering avoid_backward constraint.

        Returns:
            Tuple of (effective_pan_min, effective_pan_max)
        """
        limits = self.fixture.config.limits

        if not limits.avoid_backward:
            return limits.pan_min, limits.pan_max

        # Calculate ±90° in DMX units
        pan_range = self.fixture.config.pan_tilt_range
        dmx_per_deg = 255.0 / pan_range.pan_range_deg
        delta_90deg = int(round(90.0 * dmx_per_deg))

        # Calculate safe range centered on front position
        pan_front = self.fixture.config.orientation.pan_front_dmx
        safe_min = pan_front - delta_90deg
        safe_max = pan_front + delta_90deg

        # Clamp to hardware limits
        effective_min = max(limits.pan_min, safe_min)
        effective_max = min(limits.pan_max, safe_max)

        logger.debug(
            f"avoid_backward: pan_front={pan_front}, ±90°={delta_90deg} DMX, "
            f"effective [{effective_min}, {effective_max}]"
        )

        return effective_min, effective_max

    def clamp_pan(self, value: int, respect_geometry: bool = False) -> int:
        """Clamp pan value to effective limits.

        Delegates to FixtureConfig.clamp_pan() and optionally applies geometry constraints.

        Args:
            value: Pan DMX value to clamp
            respect_geometry: If True, also apply geometry constraints

        Returns:
            Clamped pan value
        """
        # Start with fixture clamping (includes avoid_backward)
        min_val = self._pan_effective_min
        max_val = self._pan_effective_max

        # Apply geometry constraints if requested (intersection with fixture limits)
        if respect_geometry:
            if self.geometry_pan_min is not None:
                min_val = max(min_val, self.geometry_pan_min)
            if self.geometry_pan_max is not None:
                max_val = min(max_val, self.geometry_pan_max)

        clamped = int(clamp(value, min_val, max_val))

        if clamped != value:
            logger.debug(f"Pan clamped: {value} -> {clamped} (limits: [{min_val}, {max_val}])")

        return clamped

    def clamp_tilt(self, value: int, respect_geometry: bool = False) -> int:
        """Clamp tilt value to limits.

        Delegates to FixtureConfig.clamp_tilt() and optionally applies geometry constraints.

        Args:
            value: Tilt DMX value to clamp
            respect_geometry: If True, also apply geometry constraints

        Returns:
            Clamped tilt value
        """
        # Start with fixture limits
        min_val = self.fixture.config.limits.tilt_min
        max_val = self.fixture.config.limits.tilt_max

        # Apply geometry constraints if requested (intersection)
        if respect_geometry:
            if self.geometry_tilt_min is not None:
                min_val = max(min_val, self.geometry_tilt_min)
            if self.geometry_tilt_max is not None:
                max_val = min(max_val, self.geometry_tilt_max)

        clamped = int(clamp(value, min_val, max_val))

        if clamped != value:
            logger.debug(f"Tilt clamped: {value} -> {clamped} (limits: [{min_val}, {max_val}])")

        return clamped

    def clamp_channel(self, channel_name: str, value: int) -> int:
        """Clamp any channel by name.

        Args:
            channel_name: Logical channel name (e.g., "dimmer", "shutter")
            value: DMX value to clamp

        Returns:
            Clamped value
        """
        # Default to full DMX range
        limits = (0, 255)

        # Get channel-specific limits from dmx_mapping config if available
        if channel_name == "dimmer":
            # Dimmer uses full range by default
            limits = (0, 255)
        elif channel_name == "pan":
            limits = (self.fixture.config.limits.pan_min, self.fixture.config.limits.pan_max)
        elif channel_name == "tilt":
            limits = (self.fixture.config.limits.tilt_min, self.fixture.config.limits.tilt_max)

        clamped = int(clamp(value, limits[0], limits[1]))

        if clamped != value:
            logger.debug(f"Channel {channel_name} clamped: {value} -> {clamped} (limits: {limits})")

        return clamped

    def deg_to_pan_dmx(self, deg: float, respect_geometry: bool = False) -> int:
        """Convert pan degrees to DMX value with clamping.

        Delegates to FixtureConfig.deg_to_pan_dmx() but can apply geometry constraints.

        Args:
            deg: Pan angle in degrees (relative to center/front)
            respect_geometry: If True, also apply geometry constraints

        Returns:
            DMX value (0-255) clamped to effective limits
        """
        # Use FixtureConfig for conversion
        dmx = self.fixture.config.deg_to_pan_dmx(deg)

        # Re-clamp with geometry if requested
        if respect_geometry:
            dmx = self.clamp_pan(dmx, respect_geometry=True)

        return dmx

    def deg_to_tilt_dmx(self, deg: float, respect_geometry: bool = False) -> int:
        """Convert tilt degrees to DMX value with clamping.

        Delegates to FixtureConfig.deg_to_tilt_dmx() but can apply geometry constraints.

        Args:
            deg: Tilt angle in degrees (0 = horizontal, positive = up)
            respect_geometry: If True, also apply geometry constraints

        Returns:
            DMX value (0-255) clamped to limits
        """
        # Use FixtureConfig for conversion
        dmx = self.fixture.config.deg_to_tilt_dmx(deg)

        # Re-clamp with geometry if requested
        if respect_geometry:
            dmx = self.clamp_tilt(dmx, respect_geometry=True)

        return dmx

    def pan_deg_to_dmx_delta(self, deg: float) -> int:
        """Convert pan degrees to DMX delta (no clamping).

        Delegates to FixtureConfig.pan_deg_to_dmx_delta().

        Args:
            deg: Pan delta in degrees

        Returns:
            DMX delta value
        """
        return self.fixture.config.pan_deg_to_dmx_delta(deg)

    def tilt_deg_to_dmx_delta(self, deg: float) -> int:
        """Convert tilt degrees to DMX delta (no clamping).

        Delegates to FixtureConfig.tilt_deg_to_dmx_delta().

        Args:
            deg: Tilt delta in degrees

        Returns:
            DMX delta value
        """
        return self.fixture.config.tilt_deg_to_dmx_delta(deg)

    def pct_to_dmx(self, pct: float) -> int:
        """Convert percentage (0-100) to DMX value (0-255).

        Args:
            pct: Percentage value

        Returns:
            DMX value clamped to 0-255
        """
        return int(clamp(round((pct / 100.0) * 255.0), 0, 255))

    @property
    def pan_limits(self) -> tuple[int, int]:
        """Get effective pan limits (min, max) considering avoid_backward."""
        return self._pan_effective_min, self._pan_effective_max

    @property
    def tilt_limits(self) -> tuple[int, int]:
        """Get tilt limits (min, max)."""
        return self.fixture.config.limits.tilt_min, self.fixture.config.limits.tilt_max

    def clamp_value_curve_sine(
        self,
        p1: float | None,
        p2: float | None,
        p3: float | None,
        p4: float | None,
        min_limit: int,
        max_limit: int,
        channel_name: str,
    ) -> tuple[float | None, float | None, float | None, float | None]:
        """Clamp sine/abs-sine curve parameters to respect boundaries.

        Sine curves: P1=phase, P2=amplitude, P3=cycles, P4=center

        Args:
            p1-p4: Curve parameters
            min_limit: Minimum allowed DMX value
            max_limit: Maximum allowed DMX value
            channel_name: Channel name for logging

        Returns:
            Tuple of (p1, p2, p3, p4) with clamped values
        """
        # Extract amplitude and center
        amplitude = p2 if p2 is not None else 0.0
        center = p4 if p4 is not None else 127.5

        # Calculate intended range
        intended_min = center - amplitude
        intended_max = center + amplitude

        # Check if range exceeds limits
        if intended_min < min_limit or intended_max > max_limit:
            logger.debug(
                f"Sine curve {channel_name}: range [{intended_min:.1f}, {intended_max:.1f}] "
                f"exceeds limits [{min_limit}, {max_limit}]. Clamping."
            )

            # Calculate maximum allowed amplitude
            allowed_range = max_limit - min_limit
            max_amplitude = allowed_range / 2.0

            # Reduce amplitude if too large
            if amplitude > max_amplitude:
                amplitude = max_amplitude
                logger.debug(f"  Reduced amplitude to {amplitude:.1f} DMX")

            # Recenter if needed to fit within bounds
            new_min = center - amplitude
            new_max = center + amplitude

            if new_min < min_limit:
                # Shift center up
                center = min_limit + amplitude
                logger.debug(f"  Shifted center to {center:.1f} DMX")
            elif new_max > max_limit:
                # Shift center down
                center = max_limit - amplitude
                logger.debug(f"  Shifted center to {center:.1f} DMX")

            p2 = amplitude
            p4 = center

        return p1, p2, p3, p4

    def clamp_value_curve_ramp(
        self,
        p1: float | None,
        p2: float | None,
        p3: float | None,
        p4: float | None,
        min_limit: int,
        max_limit: int,
        channel_name: str,
        is_ramp_up_down: bool = False,
    ) -> tuple[float | None, float | None, float | None, float | None]:
        """Clamp ramp/ramp-up-down curve parameters.

        Ramp: P1=start, P2=end
        Ramp Up/Down: P1=start, P2=peak, P3=end

        Args:
            p1-p4: Curve parameters
            min_limit: Minimum allowed DMX value
            max_limit: Maximum allowed DMX value
            channel_name: Channel name for logging
            is_ramp_up_down: True if this is a ramp-up-down curve

        Returns:
            Tuple of (p1, p2, p3, p4) with clamped values
        """
        start_val = p1 if p1 is not None else float(min_limit)
        peak_or_end_val = p2 if p2 is not None else float(max_limit)

        # Clamp start and peak/end
        clamped_start = clamp(start_val, min_limit, max_limit)
        clamped_peak_or_end = clamp(peak_or_end_val, min_limit, max_limit)

        # For ramp-up-down, also clamp P3 (end value)
        clamped_p3 = p3
        if is_ramp_up_down and p3 is not None:
            end_val = float(p3)
            clamped_p3 = clamp(end_val, min_limit, max_limit)

            if end_val != clamped_p3:
                logger.warning(
                    f"Ramp Up/Down {channel_name}: clamped end value (P3) "
                    f"from {end_val:.1f} to {clamped_p3:.1f} (bounds: [{min_limit}, {max_limit}])"
                )

        if start_val != clamped_start or peak_or_end_val != clamped_peak_or_end:
            logger.warning(
                f"Ramp {channel_name}: clamped [{start_val:.1f}, {peak_or_end_val:.1f}] "
                f"to [{clamped_start:.1f}, {clamped_peak_or_end:.1f}] "
                f"(bounds: [{min_limit}, {max_limit}])"
            )

        return clamped_start, clamped_peak_or_end, clamped_p3, p4

    def clamp_value_curve_sawtooth(
        self,
        p1: float | None,
        p2: float | None,
        p3: float | None,
        p4: float | None,
        min_limit: int,
        max_limit: int,
        channel_name: str,
    ) -> tuple[float | None, float | None, float | None, float | None]:
        """Clamp sawtooth curve parameters.

        Sawtooth: P1=start, P2=end, P3=cycles

        Args:
            p1-p4: Curve parameters
            min_limit: Minimum allowed DMX value
            max_limit: Maximum allowed DMX value
            channel_name: Channel name for logging

        Returns:
            Tuple of (p1, p2, p3, p4) with clamped values
        """
        start_val = p1 if p1 is not None else float(min_limit)
        end_val = p2 if p2 is not None else float(max_limit)

        # Clamp to bounds
        clamped_start = clamp(start_val, min_limit, max_limit)
        clamped_end = clamp(end_val, min_limit, max_limit)

        if start_val != clamped_start or end_val != clamped_end:
            logger.warning(
                f"Saw Tooth {channel_name}: clamped [{start_val:.1f}, {end_val:.1f}] "
                f"to [{clamped_start:.1f}, {clamped_end:.1f}] "
                f"(bounds: [{min_limit}, {max_limit}])"
            )

        return clamped_start, clamped_end, p3, p4

    def clamp_value_curve_parabolic(
        self,
        p1: float | None,
        p2: float | None,
        p3: float | None,
        p4: float | None,
        min_limit: int,
        max_limit: int,
        channel_name: str,
    ) -> tuple[float | None, float | None, float | None, float | None]:
        """Clamp parabolic curve parameters.

        Parabolic: P1=slope, P2=base_value

        Args:
            p1-p4: Curve parameters
            min_limit: Minimum allowed DMX value
            max_limit: Maximum allowed DMX value
            channel_name: Channel name for logging

        Returns:
            Tuple of (p1, p2, p3, p4) with clamped values
        """
        slope = p1 if p1 is not None else 70.0
        base_val = p2 if p2 is not None else float(min_limit)

        # Clamp base value to bounds
        clamped_base = clamp(base_val, min_limit, max_limit)

        if base_val != clamped_base:
            logger.warning(
                f"Parabolic {channel_name}: clamped base value {base_val:.1f} "
                f"to {clamped_base:.1f} (bounds: [{min_limit}, {max_limit}])"
            )

        # Estimate peak and reduce slope if needed
        estimated_peak = clamped_base + (max_limit - min_limit) * (slope / 100.0)
        if estimated_peak > max_limit:
            # Reduce slope to fit within bounds
            max_slope = ((max_limit - clamped_base) / (max_limit - min_limit)) * 100.0
            adjusted_slope = min(slope, max_slope)
            if adjusted_slope != slope:
                logger.warning(
                    f"Parabolic {channel_name}: reduced slope {slope:.1f} "
                    f"to {adjusted_slope:.1f} to fit bounds"
                )
                slope = adjusted_slope

        return slope, clamped_base, p3, p4

    def clamp_value_curve_params(
        self,
        curve_type: NativeCurveType,
        p1: float | None,
        p2: float | None,
        p3: float | None,
        p4: float | None,
        min_limit: int,
        max_limit: int,
        channel_name: str,
    ) -> tuple[float | None, float | None, float | None, float | None]:
        """Clamp value curve parameters based on curve type.

        This is the main entry point for curve parameter clamping.
        Delegates to type-specific methods.

        Args:
            curve_type: Type of value curve
            p1-p4: Curve parameters
            min_limit: Minimum allowed DMX value
            max_limit: Maximum allowed DMX value
            channel_name: Channel name for logging

        Returns:
            Tuple of (p1, p2, p3, p4) with clamped values
        """
        if curve_type in (NativeCurveType.SINE, NativeCurveType.ABS_SINE):
            return self.clamp_value_curve_sine(p1, p2, p3, p4, min_limit, max_limit, channel_name)

        elif curve_type == NativeCurveType.RAMP:
            return self.clamp_value_curve_ramp(
                p1, p2, p3, p4, min_limit, max_limit, channel_name, is_ramp_up_down=False
            )

        elif curve_type == NativeCurveType.SAW_TOOTH:
            return self.clamp_value_curve_sawtooth(
                p1, p2, p3, p4, min_limit, max_limit, channel_name
            )

        elif curve_type == NativeCurveType.PARABOLIC:
            return self.clamp_value_curve_parabolic(
                p1, p2, p3, p4, min_limit, max_limit, channel_name
            )

        else:
            # For other curve types (exponential, logarithmic, etc.),
            # just clamp P1 and P2 if they represent start/end values
            if p1 is not None:
                p1 = clamp(p1, min_limit, max_limit)
            if p2 is not None:
                p2 = clamp(p2, min_limit, max_limit)

            return p1, p2, p3, p4
