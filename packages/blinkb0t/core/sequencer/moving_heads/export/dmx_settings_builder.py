"""DMX settings string builder for xLights EffectDB entries.

Handles conversion of FixtureSegment channel values to xLights DMX effect settings strings.
Follows separation of concerns - only builds settings strings, no business logic.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from blinkb0t.core.config.fixtures.instances import FixtureInstance
    from blinkb0t.core.sequencer.moving_heads.channels.state import ChannelValue, FixtureSegment

from blinkb0t.core.curves.models import CurvePoint
from blinkb0t.core.sequencer.models.enum import ChannelName

logger = logging.getLogger(__name__)


class DmxSettingsBuilder:
    """Builds xLights DMX effect settings strings from FixtureSegment.

    Follows project guidelines:
    - Uses FixtureInstance for configuration
    - Separation of concerns - only builds strings
    - Proper type hints and documentation
    - No business logic or side effects

    Example:
        >>> builder = DmxSettingsBuilder(fixture)
        >>> settings = builder.build_settings_string(segment)
        >>> print(settings)
        "B_CHOICE_BufferStyle=Per Model Default,E_CHECKBOX_INVDMX1=0,..."
    """

    def __init__(self, fixture: FixtureInstance):
        """Initialize builder with fixture configuration.

        Args:
            fixture: Fixture instance providing DMX mapping and inversion flags
        """
        self.fixture = fixture
        self.dmx_mapping = fixture.config.dmx_mapping
        self.inversions = fixture.config.inversions

    def build_settings_string(self, segment: FixtureSegment) -> str:
        """Build xLights DMX effect settings string from FixtureSegment.

        Args:
            segment: FixtureSegment with channel values

        Returns:
            Settings string like "B_CHOICE_BufferStyle=...,E_CHECKBOX_INVDMX1=0,..."

        Example:
            >>> builder = DmxSettingsBuilder(fixture)
            >>> settings = builder.build_settings_string(segment)
            >>> print(settings)
            "B_CHOICE_BufferStyle=Per Model Default,E_CHECKBOX_INVDMX1=0,..."
        """
        # Collect channel values and curves
        channel_values: dict[int, int] = {}
        channel_curves: dict[int, list[CurvePoint]] = {}

        logger.debug(f"Building settings for {len(segment.channels)} channels")

        for channel_name, channel_value in segment.channels.items():
            self._extract_channel_data(channel_name, channel_value, channel_values, channel_curves)

        logger.debug(f"Extracted {len(channel_values)} static values, {len(channel_curves)} curves")

        # Determine max channel for output
        max_channel = self._calculate_max_channel(channel_values, channel_curves)

        # Build settings parts in required order
        parts: list[str] = []

        # 1. Buffer style (required)
        parts.append("B_CHOICE_BufferStyle=Per Model Default")

        # 2. Inversion flags for all channels (required)
        inv_dict = self._get_inversion_dict()
        for ch in range(1, max_channel + 1):
            parts.append(f"E_CHECKBOX_INVDMX{ch}={int(inv_dict.get(ch, 0))}")

        # 3. Notebook setting (required)
        parts.append("E_NOTEBOOK1=Channels 1-16")

        # 4. Channel values (E_SLIDER_DMX)
        # CRITICAL: E_SLIDER_DMX must be 0 when value curve is defined
        for ch in range(1, max_channel + 1):
            if ch in channel_curves:
                # Value curve present - slider must be 0
                parts.append(f"E_SLIDER_DMX{ch}=0")
            else:
                # No curve - use discrete value
                parts.append(f"E_SLIDER_DMX{ch}={int(channel_values.get(ch, 0))}")

        # 5. Value curves (E_VALUECURVE_DMX) - only if present
        for ch, curve_points in channel_curves.items():
            curve_str = self._curve_points_to_xlights_string(ch, curve_points)
            parts.append(f"E_VALUECURVE_DMX{ch}={curve_str}")

        return ",".join(parts)

    def _extract_channel_data(
        self,
        channel_name: ChannelName,
        channel_value: ChannelValue,
        channel_values: dict[int, int],
        channel_curves: dict[int, list[CurvePoint]],
    ) -> None:
        """Extract DMX values and curves from channel value.

        Args:
            channel_name: Logical channel name (PAN, TILT, DIMMER, etc.)
            channel_value: ChannelValue with DMX value and optional curve
            channel_values: Output dict for DMX values
            channel_curves: Output dict for value curves
        """
        # Get DMX channel number from fixture mapping
        dmx_channel = self._get_dmx_channel_number(channel_name)
        if dmx_channel is None:
            return

        # Get DMX value - static or base value
        if channel_value.static_dmx is not None:
            channel_values[dmx_channel] = int(channel_value.static_dmx)
        elif channel_value.base_dmx is not None:
            # For curves with base_dmx, use base as static value
            channel_values[dmx_channel] = int(channel_value.base_dmx)

        # Get value curve if present
        if channel_value.value_points:
            # Convert curve to DMX and normalize for xLights export
            from blinkb0t.core.curves.dmx_conversion import (
                dimmer_curve_to_dmx,
                movement_curve_to_dmx,
            )

            if channel_value.offset_centered:
                # Movement curve (pan/tilt): apply offset formula with base and amplitude
                # Formula: dmx = base_dmx + amplitude_dmx * (v - 0.5), then clamp
                normalized_points = movement_curve_to_dmx(
                    points=channel_value.value_points,
                    base_dmx=float(channel_value.base_dmx or 128),
                    amplitude_dmx=float(channel_value.amplitude_dmx or 64),
                    clamp_min=float(channel_value.clamp_min),
                    clamp_max=float(channel_value.clamp_max),
                )
            else:
                # Dimmer curve: scale directly to [clamp_min, clamp_max]
                # Formula: dmx = clamp_min + v * (clamp_max - clamp_min)
                normalized_points = dimmer_curve_to_dmx(
                    points=channel_value.value_points,
                    clamp_min=float(channel_value.clamp_min),
                    clamp_max=float(channel_value.clamp_max),
                )

            # Store normalized points for xLights value curve format
            channel_curves[dmx_channel] = normalized_points

    def _get_dmx_channel_number(self, channel_name: ChannelName) -> int | None:
        """Map logical channel name to DMX channel number.

        Args:
            channel_name: Logical channel name (PAN, TILT, DIMMER, etc.)

        Returns:
            DMX channel number, or None if channel not mapped
        """
        mapping = {
            ChannelName.PAN: self.dmx_mapping.pan_channel,
            ChannelName.TILT: self.dmx_mapping.tilt_channel,
            ChannelName.DIMMER: self.dmx_mapping.dimmer_channel,
            ChannelName.SHUTTER: self.dmx_mapping.shutter,
            ChannelName.COLOR: self.dmx_mapping.color,
            ChannelName.GOBO: self.dmx_mapping.gobo,
        }
        channel = mapping.get(channel_name)

        # Handle ChannelWithConfig objects - extract the channel number
        if channel is None:
            return None
        if isinstance(channel, int):
            return channel
        # ChannelWithConfig has a 'channel' attribute with the DMX channel number
        if hasattr(channel, "channel"):
            return int(channel.channel)
        return None

    def _get_inversion_dict(self) -> dict[int, int]:
        """Get inversion flags for all DMX channels.

        Returns:
            Dict mapping DMX channel numbers to inversion flags (0 or 1)
        """
        inv: dict[int, int] = {}

        # Helper to extract int from channel (handles ChannelWithConfig)
        def to_int(ch: int | object | None) -> int | None:
            if ch is None:
                return None
            if isinstance(ch, int):
                return ch
            if hasattr(ch, "channel"):
                return int(ch.channel)  # type: ignore
            return None

        # Map logical channels to DMX channels with inversion flags
        pan_ch = to_int(self.dmx_mapping.pan_channel)
        if pan_ch is not None:
            inv[pan_ch] = 1 if self.inversions.pan else 0

        tilt_ch = to_int(self.dmx_mapping.tilt_channel)
        if tilt_ch is not None:
            inv[tilt_ch] = 1 if self.inversions.tilt else 0

        dimmer_ch = to_int(self.dmx_mapping.dimmer_channel)
        if dimmer_ch is not None:
            inv[dimmer_ch] = 1 if self.inversions.dimmer else 0

        shutter_ch = to_int(self.dmx_mapping.shutter)
        if shutter_ch is not None:
            inv[shutter_ch] = 1 if self.inversions.shutter else 0

        color_ch = to_int(self.dmx_mapping.color)
        if color_ch is not None:
            inv[color_ch] = 1 if self.inversions.color else 0

        gobo_ch = to_int(self.dmx_mapping.gobo)
        if gobo_ch is not None:
            inv[gobo_ch] = 1 if self.inversions.gobo else 0

        # Handle 16-bit pan/tilt fine channels
        if self.dmx_mapping.use_16bit_pan_tilt:
            pan_fine_ch = to_int(self.dmx_mapping.pan_fine_channel)
            if pan_fine_ch is not None:
                inv[pan_fine_ch] = 1 if self.inversions.pan else 0

            tilt_fine_ch = to_int(self.dmx_mapping.tilt_fine_channel)
            if tilt_fine_ch is not None:
                inv[tilt_fine_ch] = 1 if self.inversions.tilt else 0

        return inv

    def _calculate_max_channel(
        self,
        channel_values: dict[int, int],
        channel_curves: dict[int, list[CurvePoint]],
    ) -> int:
        """Calculate maximum channel number to output.

        Args:
            channel_values: DMX channel values
            channel_curves: Value curve specs

        Returns:
            Maximum channel number, rounded up to nearest 16
        """
        max_channel = 16  # Minimum sensible channel count

        # Check all channels with values or curves
        for ch in channel_values.keys():
            max_channel = max(max_channel, ch)

        for ch in channel_curves.keys():
            max_channel = max(max_channel, ch)

        # Round up to nearest 16 (DMX convention)
        max_channel = ((max_channel + 15) // 16) * 16

        return max_channel

    def _curve_points_to_xlights_string(
        self, dmx_channel: int, curve_points: list[CurvePoint]
    ) -> str:
        """Convert curve points to xLights value curve string.

        Args:
            dmx_channel: DMX channel number
            curve_points: List of normalized curve points (t and v both in [0,1])

        Returns:
            xLights value curve string with time:value pairs anchored at 0.0 and 1.0

        Example:
            >>> builder._curve_points_to_xlights_string(1, [
            ...     CurvePoint(t=0.0, v=0.0),
            ...     CurvePoint(t=0.5, v=0.5),
            ...     CurvePoint(t=1.0, v=1.0),
            ... ])
            "Active=TRUE|Id=ID_VALUECURVE_DMX1|Type=Custom|Min=0.00|Max=255.00|RV=FALSE|Values=0.00:0.00;0.50:0.50;1.00:1.00|"
        """
        if not curve_points:
            return ""

        # Build time:value pairs
        # Both time and value are already normalized [0, 1]
        pairs = []
        for point in curve_points:
            # Format: time:value (both normalized 0-1)
            # Use 2 decimal places for both time and value
            # Round values safely to avoid precision issues
            t_rounded = round(point.t, 2)
            v_rounded = round(point.v, 2)
            pair = f"{t_rounded:.2f}:{v_rounded:.2f}"
            pairs.append(pair)

        # Ensure anchors at 0.0 and 1.0
        # Check if first point is at t=0.0
        if curve_points and curve_points[0].t > 0.01:
            # Prepend anchor at 0.0 using first point's value
            v_start = round(curve_points[0].v, 2)
            pairs.insert(0, f"0.00:{v_start:.2f}")

        # Check if last point is at t=1.0
        if curve_points and curve_points[-1].t < 0.99:
            # Append anchor at 1.0 using last point's value
            v_end = round(curve_points[-1].v, 2)
            pairs.append(f"1.00:{v_end:.2f}")

        # Join with semicolons
        values_str = ";".join(pairs)

        # Build xLights value curve string
        # Format: Active=TRUE|Id=ID_VALUECURVE_DMXn|Type=Custom|Min=0.00|Max=255.00|RV=FALSE|Values=t:v;t:v;...|
        parts = [
            "Active=TRUE",
            f"Id=ID_VALUECURVE_DMX{dmx_channel}",
            "Type=Custom",
            "Min=0.00",
            "Max=255.00",
            "RV=FALSE",
            f"Values={values_str}",
        ]

        # xLights format requires trailing pipe
        return "|".join(parts) + "|"
