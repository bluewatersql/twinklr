"""DMX channel assignments for moving head fixtures."""

from __future__ import annotations

import logging

from pydantic import BaseModel, ConfigDict, Field, model_validator

from twinklr.core.config.fixtures.physical import (
    REMOVED_DMX_MAPPING_FIELDS,
    reject_removed_fields,
)

logger = logging.getLogger(__name__)


class ChannelWithConfig(BaseModel):
    """A DMX channel number accepted by the fixture-file schema."""

    model_config = ConfigDict(frozen=True)

    channel: int = Field(..., ge=1, le=512, description="DMX channel number")

    @model_validator(mode="before")
    @classmethod
    def drop_removed_channel_config(cls, value: object) -> object:
        if isinstance(value, dict) and "config" in value:
            logger.warning("Ignoring retired fixture channel 'config': it does not affect output")
            return {key: item for key, item in value.items() if key != "config"}
        return value


class DmxMapping(BaseModel):
    """DMX channel assignments.

    The renderer does not read these: each fixture's physical_profile states its
    channels. The pan, tilt, dimmer, shutter, color and gobo channel numbers are listed
    to the moving-head planner.
    """

    model_config = ConfigDict(frozen=False)

    # Primary channels (required) - accept int or ChannelWithConfig
    pan_channel: int | ChannelWithConfig = Field(..., description="Pan coarse channel")
    tilt_channel: int | ChannelWithConfig = Field(..., description="Tilt coarse channel")
    dimmer_channel: int | ChannelWithConfig = Field(..., description="Dimmer/intensity channel")

    shutter_channel: int | ChannelWithConfig | None = Field(
        default=None, description="Shutter/strobe channel"
    )
    color_channel: int | ChannelWithConfig | None = Field(
        default=None, description="Color wheel channel"
    )
    gobo_channel: int | ChannelWithConfig | None = Field(
        default=None, description="Gobo wheel channel"
    )

    # Private normalized storage - these are always ChannelWithConfig
    _pan_channel_obj: ChannelWithConfig | None = None
    _tilt_channel_obj: ChannelWithConfig | None = None
    _dimmer_channel_obj: ChannelWithConfig | None = None
    _shutter_channel_obj: ChannelWithConfig | None = None
    _color_channel_obj: ChannelWithConfig | None = None
    _gobo_channel_obj: ChannelWithConfig | None = None

    @model_validator(mode="before")
    @classmethod
    def reject_removed_fields(cls, value: object) -> object:
        return reject_removed_fields(value, REMOVED_DMX_MAPPING_FIELDS, "dmx_mapping")

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

    # Tilt properties
    @property
    def tilt(self) -> int:
        """Tilt channel number."""
        assert self._tilt_channel_obj is not None
        return self._tilt_channel_obj.channel

    # Dimmer properties
    @property
    def dimmer(self) -> int:
        """Dimmer channel number."""
        assert self._dimmer_channel_obj is not None
        return self._dimmer_channel_obj.channel

    # Shutter properties
    @property
    def shutter(self) -> int | None:
        """Shutter channel number."""
        return self._shutter_channel_obj.channel if self._shutter_channel_obj else None

    # Color properties
    @property
    def color(self) -> int | None:
        """Color wheel channel number."""
        return self._color_channel_obj.channel if self._color_channel_obj else None

    # Gobo properties
    @property
    def gobo(self) -> int | None:
        """Gobo wheel channel number."""
        return self._gobo_channel_obj.channel if self._gobo_channel_obj else None
