"""Channel and DMX enums for moving head fixtures.

This module defines the core enumeration types for DMX channel addressing
and segment blending modes.
"""

from enum import Enum


class ChannelName(str, Enum):
    """DMX channel names for moving head fixtures.

    These represent the primary controllable channels on a moving head fixture.

    Attributes:
        PAN: Horizontal rotation/position channel.
        TILT: Vertical rotation/position channel.
        DIMMER: Brightness/intensity channel.

    Example:
        >>> channel = ChannelName.PAN
        >>> channel.value
        'PAN'
    """

    PAN = "pan"
    TILT = "tilt"
    DIMMER = "dimmer"
    SHUTTER = "shutter"
    COLOR = "color"
    GOBO = "gobo"


class BlendMode(str, Enum):
    """How to blend overlapping channel segments.

    Defines the behavior when multiple segments affect the same channel
    at the same time.

    Attributes:
        OVERRIDE: Later segment completely replaces earlier segment values.
        ADD: Values are summed together (reserved for future use).

    Example:
        >>> mode = BlendMode.OVERRIDE
        >>> mode.value
        'OVERRIDE'
    """

    OVERRIDE = "OVERRIDE"
    ADD = "ADD"
