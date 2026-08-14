"""DMX settings string builder for xLights EffectDB entries.

Handles conversion of FixtureSegment channel values to xLights DMX effect settings strings.
Follows separation of concerns - only builds settings strings, no business logic.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from twinklr.core.config.fixtures.instances import FixtureInstance
    from twinklr.core.sequencer.moving_heads.channels.state import ChannelValue, FixtureSegment

from twinklr.core.config.adapter import get_max_channel
from twinklr.core.curves.models import CurvePoint
from twinklr.core.sequencer.models.enum import ChannelName

logger = logging.getLogger(__name__)


class DmxSettingsBuilder:
    """Builds xLights DMX effect settings strings from FixtureSegment.

    Follows project guidelines:
    - Uses FixtureInstance for configuration
    - Separation of concerns - only builds strings
    - Proper type hints and documentation
    - No business logic or side effects
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
        """
        # Collect channel values and curves
        channel_values: dict[int, int] = {}
        channel_curves: dict[int, list[CurvePoint]] = {}

        for channel_name, channel_value in segment.channels.items():
            self._extract_channel_data(channel_name, channel_value, channel_values, channel_curves)

        # Determine the emitted window from the fixture's real channel count, not from
        # a floor-16/round-to-16 guess over channels the renderer happened to write
        # (P1P-T6 / P4-F3): a shutter mapped above 16 must still get its declared
        # default, and `get_max_channel` includes every declared role, so it does.
        max_channel = get_max_channel(self.dmx_mapping)

        # Channels the fixture maps but the renderer did not write get the fixture's
        # declared default instead of a zero-fill (P1P-T6 / P4-F3 / P5-V1): shutter
        # opens ("usually open"), color/gobo settle on their configured "open" value.
        declared_defaults = self._declared_defaults()

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
        # CRITICAL: E_SLIDER_DMX must be 0 when value curve is defined.
        # A channel with neither a written value, a curve, nor a declared default is
        # not mapped by this fixture at all -- omitted entirely rather than zero-filled,
        # left to whatever the console already holds for it.
        for ch in range(1, max_channel + 1):
            if ch in channel_curves:
                # Value curve present - slider must be 0
                parts.append(f"E_SLIDER_DMX{ch}=0")
            elif ch in channel_values:
                parts.append(f"E_SLIDER_DMX{ch}={int(channel_values[ch])}")
            elif ch in declared_defaults:
                parts.append(f"E_SLIDER_DMX{ch}={declared_defaults[ch]}")

        # 5. Value curves (E_VALUECURVE_DMX) - only if present, in channel order so
        # the string does not depend on the order channels happened to be built in
        for ch, curve_points in sorted(channel_curves.items()):
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

        # Get value curve if present.
        # `value_points` is the compiler's channel curve; a ChannelValue built
        # elsewhere may carry its curve only on `curve` (every transition segment
        # does, and reading just these three fields dropped the whole blend, so each
        # section boundary exported a one-second all-zero blackout).
        value_points = channel_value.value_points or self._curve_points(channel_value)

        if value_points:
            # Convert curve to DMX and normalize for xLights export
            from twinklr.core.curves.dmx_conversion import (
                dimmer_curve_to_dmx,
                movement_curve_to_dmx,
            )

            if channel_value.offset_centered:
                # Movement curve (pan/tilt): apply offset formula with base and amplitude
                # Formula: dmx = base_dmx + amplitude_dmx * (v - 0.5), then clamp
                normalized_points = movement_curve_to_dmx(
                    points=value_points,
                    base_dmx=float(channel_value.base_dmx or 128),
                    amplitude_dmx=float(channel_value.amplitude_dmx or 64),
                    clamp_min=float(channel_value.clamp_min),
                    clamp_max=float(channel_value.clamp_max),
                )
            else:
                # Dimmer curve: scale directly to [clamp_min, clamp_max]
                # Formula: dmx = clamp_min + v * (clamp_max - clamp_min)
                normalized_points = dimmer_curve_to_dmx(
                    points=value_points,
                    clamp_min=float(channel_value.clamp_min),
                    clamp_max=float(channel_value.clamp_max),
                )

            # Store normalized points for xLights value curve format
            channel_curves[dmx_channel] = normalized_points

    @staticmethod
    def _curve_points(channel_value: ChannelValue) -> list[CurvePoint] | None:
        """Points carried on `ChannelValue.curve`, when it is a points curve."""
        curve = channel_value.curve
        points = getattr(curve, "points", None) if curve is not None else None
        return list(points) if points else None

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

    def _declared_defaults(self) -> dict[int, int]:
        """Fixture-declared defaults for mapped channels the renderer did not write.

        Only shutter, colour and gobo have a declared "at rest" value in this
        repo's fixture config: `DmxMapping.shutter_default` (255, "usually open"),
        and each of `color_map`/`gobo_map`'s `"open"` entry. Pan/tilt/dimmer and
        16-bit fine channels have no such declaration, so if one is ever mapped
        but unwritten it is omitted rather than assigned an invented value
        (P1P-T6; see the policy note on `build_settings_string`).

        Returns:
            Dict mapping DMX channel number to its declared default value.
        """
        defaults: dict[int, int] = {}

        shutter_channel = self._get_dmx_channel_number(ChannelName.SHUTTER)
        if shutter_channel is not None:
            defaults[shutter_channel] = int(self.dmx_mapping.shutter_default)

        color_channel = self._get_dmx_channel_number(ChannelName.COLOR)
        if color_channel is not None:
            defaults[color_channel] = int(self.dmx_mapping.color_map.get("open", 0))

        gobo_channel = self._get_dmx_channel_number(ChannelName.GOBO)
        if gobo_channel is not None:
            defaults[gobo_channel] = int(self.dmx_mapping.gobo_map.get("open", 0))

        return defaults

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
                return int(ch.channel)
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
            "Active=TRUE|Id=ID_VALUECURVE_DMX1|Type=Custom|Min=0.00|Max=255.00|RV=FALSE|Values=0.0000:0.0000;0.5000:0.5000;1.0000:1.0000|"
        """
        if not curve_points:
            return ""

        # Build time:value pairs
        # Both time and value are already normalized [0, 1]
        #
        # 4 decimal places (P1P-T6 / P4-F10): `Min=0.00|Max=255.00` means a `v`
        # resolution of 0.01 is 2.55 DMX steps -- a curve could not express a
        # one-step change, and repeated values were visible in the goldens as
        # quantisation. 4 decimals gives ~0.026 DMX resolution and, at this
        # curve's `n_samples` grid, leaves no two points sharing a `t` key.
        pairs = []
        for point in curve_points:
            t_rounded = round(point.t, 4)
            v_rounded = round(point.v, 4)
            pair = f"{t_rounded:.4f}:{v_rounded:.4f}"

            # if dmx_channel == 13:
            #     logger.debug(f"{dmx_channel}: {point.t}|{t_rounded}|{point.v}|{v_rounded}")
            pairs.append(pair)

        # Ensure anchors at 0.0 and 1.0
        # Check if first point is at t=0.0
        if curve_points and curve_points[0].t > 0.01:
            # Prepend anchor at 0.0 using first point's value
            v_start = round(curve_points[0].v, 4)
            pairs.insert(0, f"0.0000:{v_start:.4f}")

        # Check if last point is at t=1.0
        if curve_points and curve_points[-1].t < 0.99:
            # Append anchor at 1.0 using last point's value
            v_end = round(curve_points[-1].v, 4)
            pairs.append(f"1.0000:{v_end:.4f}")

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
