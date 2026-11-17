"""Moving-head channel intermediate representation."""

from __future__ import annotations

from enum import Enum
import json
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

from twinklr.core.sequencer.models.enum import ChannelName
from twinklr.core.sequencer.models.moving_heads.physical import (
    CONTINUOUS_UNITS,
    ContinuousTrajectory,
    PhysicalValue,
)


class ChannelValue(BaseModel):
    """One channel's value: a typed physical trajectory in degrees or normalized units,
    or named states."""

    model_config = ConfigDict(extra="forbid")

    channel: ChannelName
    physical: PhysicalValue

    @model_validator(mode="after")
    def _validate_unit(self) -> ChannelValue:
        """The trajectory's unit is the channel's: continuous for pan, tilt, dimmer and
        zoom, discrete states for the rest."""
        unit = CONTINUOUS_UNITS.get(self.channel)
        if isinstance(self.physical, ContinuousTrajectory):
            if self.physical.unit != unit:
                raise ValueError(
                    f"{self.channel.value} takes "
                    f"{'discrete states' if unit is None else unit + ' values'}, "
                    f"not {self.physical.unit} values"
                )
        elif unit is not None:
            raise ValueError(f"{self.channel.value} takes {unit} values, not discrete states")
        return self


class FixtureSegment(BaseModel):
    """Unified segment for a fixture over a time range with multiple channel values.

    This combines fixture identity, timing, and per-channel configuration into
    a single cohesive unit.

    Attributes:
        fixture_id: Unique identifier for the fixture
        t0_ms: Start time in milliseconds (inclusive)
        t1_ms: End time in milliseconds (inclusive)
        channels: Dict mapping channel names to their value specifications
    """

    model_config = ConfigDict(extra="forbid")

    section_id: str
    segment_id: str
    step_id: str
    template_id: str
    preset_id: str | None = None

    fixture_id: str = Field(..., min_length=1)
    t0_ms: int = Field(..., ge=0)
    t1_ms: int = Field(..., ge=0)

    channels: dict[ChannelName, ChannelValue] = Field(default_factory=dict)
    metadata: dict[str, str] = Field(default_factory=dict)

    @property
    def metatag(self) -> str:
        if self.preset_id:
            return f"{self.section_id}_{self.step_id}_{self.template_id}_{self.preset_id}"
        else:
            return f"{self.section_id}_{self.step_id}_{self.template_id}"

    @model_validator(mode="after")
    def _validate_constraints(self) -> FixtureSegment:
        """Validate segment constraints."""
        # Time ordering
        if self.t1_ms < self.t0_ms:
            raise ValueError("t1_ms must be >= t0_ms")

        # Validate channel consistency
        for channel_name, channel_value in self.channels.items():
            if channel_value.channel != channel_name:
                raise ValueError(
                    f"Channel mismatch: key is {channel_name} but "
                    f"ChannelValue.channel is {channel_value.channel}"
                )

        return self

    def get_channel(self, channel: ChannelName) -> ChannelValue | None:
        """Get channel value specification.

        Args:
            channel: Channel name

        Returns:
            ChannelValue if set, None otherwise
        """
        return self.channels.get(channel)

    def has_channel(self, channel: ChannelName) -> bool:
        """Check if channel is configured.

        Args:
            channel: Channel name

        Returns:
            True if channel is configured
        """
        return channel in self.channels

    def metadata_json_encoder(self, obj: Any) -> str:
        """Custom JSON encoder for metadata values."""
        if isinstance(obj, BaseModel):
            return str(obj.model_dump(exclude_none=True, exclude_defaults=True, exclude_unset=True))

        if isinstance(obj, Enum):
            return str(obj.value)

        if isinstance(obj, list):
            return ",".join([self.metadata_json_encoder(item) for item in obj])

        return str(obj)

    def add_metadata(self, key: str, value: Any) -> None:
        """Add metadata to the segment."""
        if value is None:
            return
        if isinstance(value, dict):
            value = json.dumps(value, default=self.metadata_json_encoder)
        elif not isinstance(value, str):
            value = str(value)

        self.metadata[key] = value
