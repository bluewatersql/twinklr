"""Channel state management for DMX effects."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from blinkb0t.core.domains.sequencing.infrastructure.curves.xlights_adapter import CustomCurveSpec
from blinkb0t.core.domains.sequencing.models.curves import ValueCurveSpec
from blinkb0t.core.utils.math import clamp

if TYPE_CHECKING:
    from blinkb0t.core.config.fixtures import FixtureInstance

logger = logging.getLogger(__name__)


class ChannelState:
    """Manages DMX channel values for an effect instance.

    Provides high-level channel manipulation with automatic:
    - Value resolution (named values → DMX)
    - Clamping to channel limits
    - Inversion handling
    - Value curve support

    Now uses FixtureInstance directly instead of ChannelRegistry.
    """

    def __init__(self, fixture: FixtureInstance):
        """Initialize channel state.

        Args:
            fixture: Fixture instance for DMX channel mapping
        """
        self.fixture = fixture
        self.values: dict[int, int] = {}  # DMX channel -> value
        self.value_curves: dict[int, ValueCurveSpec | CustomCurveSpec] = {}  # DMX channel -> curve

    def _get_dmx_channel(self, channel_name: str) -> int | None:
        """Get DMX channel number for a logical channel name.

        Args:
            channel_name: Logical channel name ("pan", "tilt", "dimmer", etc.)

        Returns:
            DMX channel number or None if channel doesn't exist
        """
        mapping = self.fixture.config.dmx_mapping

        # Helper to extract int from channel (handles ChannelWithConfig)
        def to_int(ch: int | object | None) -> int | None:
            if ch is None:
                return None
            if isinstance(ch, int):
                return ch
            # Check for ChannelWithConfig (has a 'channel' attribute that's an int)
            if hasattr(ch, "channel") and hasattr(ch.channel, "__int__"):
                return int(ch.channel)  # type: ignore
            # Try to convert directly (for Mock objects in tests)
            try:
                return int(ch)  # type: ignore
            except (TypeError, ValueError):
                return None

        channel_map = {
            "pan": to_int(mapping.pan_channel),
            "tilt": to_int(mapping.tilt_channel),
            "dimmer": to_int(mapping.dimmer_channel),
            "shutter": to_int(mapping.shutter),
            "color": to_int(mapping.color),
            "gobo": to_int(mapping.gobo),
        }
        return channel_map.get(channel_name)

    def _is_inverted(self, channel_name: str) -> bool:
        """Check if a channel is inverted.

        Args:
            channel_name: Logical channel name

        Returns:
            True if inverted, False otherwise
        """
        inversions = self.fixture.config.inversions
        inversion_map = {
            "pan": inversions.pan,
            "tilt": inversions.tilt,
            "dimmer": inversions.dimmer,
        }
        return inversion_map.get(channel_name, False)

    def set_channel(
        self,
        channel_name: str,
        value: int | str,
        value_curve: ValueCurveSpec | CustomCurveSpec | None = None,
    ) -> bool:
        """Set a channel value by logical name.

        Args:
            channel_name: Logical channel name ("pan", "shutter", "gobo")
            value: DMX integer value (0-255)
            value_curve: Optional value curve for smooth transitions

        Returns:
            True if channel was set, False if channel doesn't exist
        """
        dmx_channel = self._get_dmx_channel(channel_name)
        if dmx_channel is None or dmx_channel == 0:
            logger.debug(f"Channel '{channel_name}' not available on this fixture")
            return False

        # For now, only support integer values (no named value resolution)
        # Named value resolution (like "open" for shutter) can be added later if needed
        if isinstance(value, str):
            logger.warning(f"String value '{value}' not supported yet, skipping")
            return False

        dmx_value = int(value)

        # Clamp to 0-255
        dmx_value = clamp(dmx_value, 0, 255)

        # Apply inversion if configured
        if self._is_inverted(channel_name):
            dmx_value = 255 - dmx_value

        # Set value curve if provided
        if value_curve:
            self.value_curves[dmx_channel] = value_curve
            # When using value curves, do NOT set base value (avoids initial snap)
        else:
            # Set coarse channel only if no value curve
            self.values[dmx_channel] = dmx_value

        logger.debug(f"Set {channel_name} (DMX{dmx_channel}) = {dmx_value} (raw value: {value})")
        return True

    def get_channel(self, channel_name: str) -> int | None:
        """Get current DMX value for a channel.

        Args:
            channel_name: Logical channel name

        Returns:
            Current DMX value or None if not set
        """
        dmx_channel = self._get_dmx_channel(channel_name)
        if dmx_channel is None:
            return None
        return self.values.get(dmx_channel)

    def to_dmx_dict(self) -> dict[int, int]:
        """Get final DMX channel values.

        Returns:
            Dict mapping DMX channel number to value
        """
        return self.values.copy()

    def to_value_curves_dict(self) -> dict[int, ValueCurveSpec | CustomCurveSpec]:
        """Get value curves for channels.

        Returns:
            Dict mapping DMX channel number to ValueCurveSpec
        """
        return self.value_curves.copy()

    def merge(self, other: ChannelState) -> None:
        """Merge another channel state into this one.

        Args:
            other: Another ChannelState to merge from
        """
        self.values.update(other.values)
        self.value_curves.update(other.value_curves)
