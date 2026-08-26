"""Moving-head channel intermediate representation."""

from __future__ import annotations

from enum import Enum
import json
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

from twinklr.core.curves.models import BaseCurve, CurvePoint
from twinklr.core.sequencer.models.enum import BlendMode, ChannelName


class ChannelValue(BaseModel):
    """Single channel's value specification.

    Either static_dmx OR curve must be set (mutually exclusive).

    For offset-centered curves (movement), set offset_centered=True
    and provide base_dmx and amplitude_dmx. The final DMX value is
    computed as: base_dmx + (curve_value - 0.5) * amplitude_dmx

    For absolute curves (dimmer), leave offset_centered=False.
    The final DMX value is computed as: lerp(clamp_min, clamp_max, curve_value)
    """

    model_config = ConfigDict(extra="forbid")

    channel: ChannelName

    # Option A: static value
    static_dmx: int | None = Field(default=None, ge=0, le=255)

    # Option B: curve
    curve: BaseCurve | None = Field(default=None)
    value_points: list[CurvePoint] | None = Field(default=None)

    # Composition hints (for movement offset curves)
    base_dmx: int | None = None
    amplitude_dmx: int | None = None
    offset_centered: bool = Field(
        default=False,
        description="If true, interpret curve values as offset around 0.5",
    )

    blend_mode: BlendMode = Field(default=BlendMode.OVERRIDE)

    clamp_min: int = Field(default=0, ge=0, le=255)
    clamp_max: int = Field(default=255, ge=0, le=255)

    @model_validator(mode="after")
    def _validate_constraints(self) -> ChannelValue:
        """Validate channel value constraints."""
        # Must have exactly one of static_dmx or curve
        if self.static_dmx is None and self.curve is None:
            raise ValueError("ChannelValue must set either static_dmx or curve")
        if self.static_dmx is not None and self.curve is not None:
            raise ValueError("ChannelValue cannot set both static_dmx and curve")

        # Clamp bounds
        if self.clamp_max < self.clamp_min:
            raise ValueError("clamp_max must be >= clamp_min")

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

    # Grouping hint: if False, this segment should not be grouped with others
    # Set to False when template uses per-fixture phase offsets
    allow_grouping: bool = Field(default=True)

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

    def add_channel(
        self,
        channel: ChannelName,
        static_dmx: int | None = None,
        curve: BaseCurve | None = None,
        value_points: list[CurvePoint] | None = None,
        base_dmx: int | None = None,
        amplitude_dmx: int | None = None,
        offset_centered: bool = False,
        blend_mode: BlendMode = BlendMode.OVERRIDE,
        clamp_min: int = 0,
        clamp_max: int = 255,
    ) -> None:
        """Add or update a channel value specification.

        Args:
            channel: Channel name
            static_dmx: Static DMX value (mutually exclusive with curve)
            curve: Curve specification (mutually exclusive with static_dmx)
            value_points: Optional curve points for smooth transitions
            base_dmx: Base DMX for offset-centered curves
            amplitude_dmx: Amplitude for offset-centered curves
            offset_centered: If True, interpret curve as offset around 0.5
            blend_mode: How to blend with overlapping segments
            clamp_min: Minimum DMX value after composition
            clamp_max: Maximum DMX value after composition
        """
        self.channels[channel] = ChannelValue(
            channel=channel,
            static_dmx=static_dmx,
            curve=curve,
            value_points=value_points,
            base_dmx=base_dmx,
            amplitude_dmx=amplitude_dmx,
            offset_centered=offset_centered,
            blend_mode=blend_mode,
            clamp_min=clamp_min,
            clamp_max=clamp_max,
        )

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
