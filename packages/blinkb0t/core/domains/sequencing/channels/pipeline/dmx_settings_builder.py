"""DMX settings string builder for xLights EffectDB entries.

Handles conversion of channel states and value curves to xLights DMX effect settings strings.
Follows separation of concerns - only builds settings strings, no business logic.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from blinkb0t.core.config.fixtures import FixtureInstance
    from blinkb0t.core.domains.sequencing.channels.state import ChannelState
    from blinkb0t.core.domains.sequencing.infrastructure.curves.xlights_adapter import (
        CustomCurveSpec,
    )
    from blinkb0t.core.domains.sequencing.models.channels import DmxEffect
    from blinkb0t.core.domains.sequencing.models.curves import ValueCurveSpec

logger = logging.getLogger(__name__)


class DmxSettingsBuilder:
    """Builds xLights DMX effect settings strings from channel states.

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

    def build_settings_string(self, dmx_effect: DmxEffect) -> str:
        """Build xLights DMX effect settings string.

        Args:
            dmx_effect: DMX effect with channel states

        Returns:
            Settings string like "B_CHOICE_BufferStyle=...,E_CHECKBOX_INVDMX1=0,..."

        Example:
            >>> builder = DmxSettingsBuilder(fixture)
            >>> settings = builder.build_settings_string(dmx_effect)
            >>> print(settings)
            "B_CHOICE_BufferStyle=Per Model Default,E_CHECKBOX_INVDMX1=0,..."
        """
        # Collect channel values and curves
        channel_values: dict[int, int] = {}
        channel_curves: dict[int, ValueCurveSpec | CustomCurveSpec] = {}

        logger.info(f"[CURVE_TRACE] DmxEffect has {len(dmx_effect.channels)} channels")
        for channel_name, channel_state in dmx_effect.channels.items():
            logger.info(
                f"[CURVE_TRACE] Channel {channel_name}: value_curves={list(channel_state.value_curves.keys())}"
            )
            self._extract_channel_data(channel_name, channel_state, channel_values, channel_curves)

        logger.info(f"[CURVE_TRACE] After extraction: channel_curves={list(channel_curves.keys())}")

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
        for ch, curve_spec in channel_curves.items():
            curve_str = curve_spec.to_xlights_string(ch)
            parts.append(f"E_VALUECURVE_DMX{ch}={curve_str}")

        return ",".join(parts)

    def _extract_channel_data(
        self,
        channel_name: str,
        channel_state: ChannelState,
        channel_values: dict[int, int],
        channel_curves: dict[int, ValueCurveSpec | CustomCurveSpec],
    ) -> None:
        """Extract DMX values and curves from channel state.

        Args:
            channel_name: Logical channel name (pan, tilt, dimmer, etc.)
            channel_state: Channel state with DMX value and optional curve
            channel_values: Output dict for DMX values
            channel_curves: Output dict for value curves
        """
        # Get DMX channel number from fixture mapping
        dmx_channel = self._get_dmx_channel_number(channel_name)
        if dmx_channel is None:
            return

        # Get DMX value
        dmx_value = channel_state.get_channel(channel_name)
        if dmx_value is not None:
            channel_values[dmx_channel] = int(dmx_value)

        # Get value curve if present (value_curves is a dict[int, ValueCurveSpec])
        if dmx_channel in channel_state.value_curves:
            channel_curves[dmx_channel] = channel_state.value_curves[dmx_channel]

    def _get_dmx_channel_number(self, channel_name: str) -> int | None:
        """Map logical channel name to DMX channel number.

        Args:
            channel_name: Logical channel name (pan, tilt, dimmer, etc.)

        Returns:
            DMX channel number, or None if channel not mapped
        """
        mapping = {
            "pan": self.dmx_mapping.pan_channel,
            "tilt": self.dmx_mapping.tilt_channel,
            "dimmer": self.dmx_mapping.dimmer_channel,
            "shutter": self.dmx_mapping.shutter,
            "color": self.dmx_mapping.color,
            "gobo": self.dmx_mapping.gobo,
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
        channel_curves: dict[int, ValueCurveSpec | CustomCurveSpec],
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
