"""DMX channel configuration and mapping models.

Defines DMX channel assignments, configurations, and mappings for moving head fixtures.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, model_validator


class ShutterMap(BaseModel):
    """DMX values for shutter states."""

    model_config = ConfigDict(frozen=True)

    closed: int = Field(default=0, ge=0, le=255, description="Shutter closed")
    open: int = Field(default=255, ge=0, le=255, description="Shutter fully open")
    strobe_slow: int = Field(default=64, ge=0, le=255, description="Slow strobe")
    strobe_medium: int = Field(default=127, ge=0, le=255, description="Medium strobe")
    strobe_fast: int = Field(default=190, ge=0, le=255, description="Fast strobe")


class DmxChannelConfig(BaseModel):
    """Configuration for a single DMX channel."""

    model_config = ConfigDict(frozen=True)

    channel_min: int = Field(default=0, ge=0, le=255, description="Minimum channel value")
    channel_max: int = Field(default=255, ge=0, le=255, description="Maximum channel value")
    channel_default: int = Field(default=0, ge=0, le=255, description="Default channel value")
    channel_inverted: bool = Field(default=False, description="Invert channel value")
    channel_value_map: dict[str, int] = Field(
        default_factory=dict, description="Value map for channel"
    )
    channel_calibration: dict[str, dict] = Field(
        default_factory=dict, description="Calibration for channel"
    )


class ChannelWithConfig(BaseModel):
    """Channel number with optional configuration."""

    model_config = ConfigDict(frozen=True)

    channel: int = Field(..., ge=1, le=512, description="DMX channel number")
    config: DmxChannelConfig = Field(
        default_factory=DmxChannelConfig, description="Channel configuration"
    )


class ChannelInversions(BaseModel):
    """Flags for inverting channel behaviors.

    Some fixtures may require inverted control for proper orientation.
    """

    model_config = ConfigDict(frozen=False)

    pan: bool = Field(default=False, description="Invert pan direction")
    tilt: bool = Field(default=False, description="Invert tilt direction")
    dimmer: bool = Field(default=False, description="Invert dimmer curve")
    shutter: bool = Field(default=False, description="Invert shutter values")
    color: bool = Field(default=False, description="Invert color wheel")
    gobo: bool = Field(default=False, description="Invert gobo wheel")


class DmxMapping(BaseModel):
    """Complete DMX channel assignments and mappings.

    Defines which DMX channels control which fixture parameters.
    Supports both 8-bit and 16-bit (fine) control.
    """

    model_config = ConfigDict(frozen=False)

    # Primary channels (required) - accept int or ChannelWithConfig
    pan_channel: int | ChannelWithConfig = Field(..., description="Pan coarse channel")
    tilt_channel: int | ChannelWithConfig = Field(..., description="Tilt coarse channel")
    dimmer_channel: int | ChannelWithConfig = Field(..., description="Dimmer/intensity channel")

    # Fine control (16-bit) - optional
    pan_fine_channel: int | ChannelWithConfig | None = Field(
        default=None, description="Pan fine channel (16-bit)"
    )
    tilt_fine_channel: int | ChannelWithConfig | None = Field(
        default=None, description="Tilt fine channel (16-bit)"
    )
    use_16bit_pan_tilt: bool = Field(default=False, description="Use 16-bit pan/tilt resolution")

    # Shutter control - optional
    shutter_channel: int | ChannelWithConfig | None = Field(
        default=None, description="Shutter/strobe channel"
    )
    shutter_default: int = Field(
        default=255, ge=0, le=255, description="Default shutter value (usually open)"
    )
    shutter_map: ShutterMap = Field(
        default_factory=ShutterMap, description="Shutter DMX value mappings"
    )

    # Color wheel - optional
    color_channel: int | ChannelWithConfig | None = Field(
        default=None, description="Color wheel channel"
    )
    color_map: dict[str, int] = Field(
        default_factory=lambda: {
            "open": 0,
            "white": 0,
            "red": 18,
            "orange": 36,
            "yellow": 54,
            "green": 72,
            "cyan": 90,
            "blue": 108,
            "magenta": 126,
        },
        description="Color name to DMX value mapping",
    )

    # Gobo wheel - optional
    gobo_channel: int | ChannelWithConfig | None = Field(
        default=None, description="Gobo wheel channel"
    )
    gobo_map: dict[str, int] = Field(
        default_factory=lambda: {
            "open": 0,
            "gobo1": 10,
            "gobo2": 20,
            "gobo3": 30,
            "gobo4": 40,
        },
        description="Gobo name to DMX value mapping",
    )

    # Private normalized storage - these are always ChannelWithConfig
    _pan_channel_obj: ChannelWithConfig | None = None
    _tilt_channel_obj: ChannelWithConfig | None = None
    _dimmer_channel_obj: ChannelWithConfig | None = None
    _pan_fine_channel_obj: ChannelWithConfig | None = None
    _tilt_fine_channel_obj: ChannelWithConfig | None = None
    _shutter_channel_obj: ChannelWithConfig | None = None
    _color_channel_obj: ChannelWithConfig | None = None
    _gobo_channel_obj: ChannelWithConfig | None = None

    @model_validator(mode="after")
    def normalize_channels(self) -> DmxMapping:
        """Convert all int channels to ChannelWithConfig for uniform internal access."""

        def _normalize(val: int | ChannelWithConfig | None) -> ChannelWithConfig | None:
            if val is None:
                return None
            if isinstance(val, int):
                return ChannelWithConfig(channel=val)
            return val

        self._pan_channel_obj = _normalize(self.pan_channel)
        self._tilt_channel_obj = _normalize(self.tilt_channel)
        self._dimmer_channel_obj = _normalize(self.dimmer_channel)
        self._pan_fine_channel_obj = _normalize(self.pan_fine_channel)
        self._tilt_fine_channel_obj = _normalize(self.tilt_fine_channel)
        self._shutter_channel_obj = _normalize(self.shutter_channel)
        self._color_channel_obj = _normalize(self.color_channel)
        self._gobo_channel_obj = _normalize(self.gobo_channel)

        return self

    # Pan properties
    @property
    def pan(self) -> int:
        """Pan channel number."""
        assert self._pan_channel_obj is not None
        return self._pan_channel_obj.channel

    @property
    def pan_config(self) -> DmxChannelConfig:
        """Pan channel configuration."""
        assert self._pan_channel_obj is not None
        return self._pan_channel_obj.config

    # Tilt properties
    @property
    def tilt(self) -> int:
        """Tilt channel number."""
        assert self._tilt_channel_obj is not None
        return self._tilt_channel_obj.channel

    @property
    def tilt_config(self) -> DmxChannelConfig:
        """Tilt channel configuration."""
        assert self._tilt_channel_obj is not None
        return self._tilt_channel_obj.config

    # Dimmer properties
    @property
    def dimmer(self) -> int:
        """Dimmer channel number."""
        assert self._dimmer_channel_obj is not None
        return self._dimmer_channel_obj.channel

    @property
    def dimmer_config(self) -> DmxChannelConfig:
        """Dimmer channel configuration."""
        assert self._dimmer_channel_obj is not None
        return self._dimmer_channel_obj.config

    # Pan fine properties
    @property
    def pan_fine(self) -> int | None:
        """Pan fine channel number."""
        return self._pan_fine_channel_obj.channel if self._pan_fine_channel_obj else None

    @property
    def pan_fine_config(self) -> DmxChannelConfig | None:
        """Pan fine channel configuration."""
        return self._pan_fine_channel_obj.config if self._pan_fine_channel_obj else None

    # Tilt fine properties
    @property
    def tilt_fine(self) -> int | None:
        """Tilt fine channel number."""
        return self._tilt_fine_channel_obj.channel if self._tilt_fine_channel_obj else None

    @property
    def tilt_fine_config(self) -> DmxChannelConfig | None:
        """Tilt fine channel configuration."""
        return self._tilt_fine_channel_obj.config if self._tilt_fine_channel_obj else None

    # Shutter properties
    @property
    def shutter(self) -> int | None:
        """Shutter channel number."""
        return self._shutter_channel_obj.channel if self._shutter_channel_obj else None

    @property
    def shutter_config(self) -> DmxChannelConfig | None:
        """Shutter channel configuration."""
        return self._shutter_channel_obj.config if self._shutter_channel_obj else None

    # Color properties
    @property
    def color(self) -> int | None:
        """Color wheel channel number."""
        return self._color_channel_obj.channel if self._color_channel_obj else None

    @property
    def color_config(self) -> DmxChannelConfig | None:
        """Color wheel channel configuration."""
        return self._color_channel_obj.config if self._color_channel_obj else None

    # Gobo properties
    @property
    def gobo(self) -> int | None:
        """Gobo wheel channel number."""
        return self._gobo_channel_obj.channel if self._gobo_channel_obj else None

    @property
    def gobo_config(self) -> DmxChannelConfig | None:
        """Gobo wheel channel configuration."""
        return self._gobo_channel_obj.config if self._gobo_channel_obj else None
