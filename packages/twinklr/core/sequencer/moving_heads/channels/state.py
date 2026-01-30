from __future__ import annotations

import json
import logging
from enum import Enum
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel, ConfigDict, Field, model_validator
from twinklr.core.curves.models import BaseCurve, CurvePoint
from twinklr.core.sequencer.models.enum import BlendMode, ChannelName
from twinklr.core.utils.math import clamp

if TYPE_CHECKING:
    from twinklr.core.config.fixtures import FixtureInstance

logger = logging.getLogger(__name__)


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


class ChannelState:
    """Runtime state manager for fixture DMX channels.

    This class handles the runtime application of FixtureSegment channel values
    to actual DMX channels, including:
    - DMX channel mapping via fixture configuration
    - Channel inversion
    - Value clamping
    - Curve point tracking
    """

    _CHANNEL_ATTR = {
        ChannelName.PAN: "pan_channel",
        ChannelName.TILT: "tilt_channel",
        ChannelName.DIMMER: "dimmer_channel",
        ChannelName.SHUTTER: "shutter",
        ChannelName.COLOR: "color",
        ChannelName.GOBO: "gobo",
    }

    def __init__(self, fixture: FixtureInstance):
        """Initialize channel state.

        Args:
            fixture: Fixture instance for DMX channel mapping
        """
        self.fixture = fixture
        self.values: dict[int, int] = {}  # DMX channel -> value
        self.value_points: dict[int, list[CurvePoint]] = {}  # DMX channel -> curve

    def _get_dmx_channel(self, channel_name: ChannelName) -> int | None:
        """Get DMX channel number for logical channel name."""
        mapping = self.fixture.config.dmx_mapping

        attr = self._CHANNEL_ATTR.get(channel_name)
        if not attr:
            return None

        ch = getattr(mapping, attr, None)

        try:
            if ch is None:
                return None
            # supports ChannelWithConfig(channel=<int-like>) and mocks
            return int(getattr(ch, "channel", ch))
        except (TypeError, ValueError):
            return None

    def _is_inverted(self, channel_name: ChannelName) -> bool:
        """Check if a channel is inverted."""
        inversions = self.fixture.config.inversions
        inversion_map = {
            ChannelName.PAN: inversions.pan,
            ChannelName.TILT: inversions.tilt,
            ChannelName.DIMMER: inversions.dimmer,
        }
        return inversion_map.get(channel_name, False)

    def apply_channel_value(self, channel_value: ChannelValue) -> bool:
        """Apply a ChannelValue to the state.

        Args:
            channel_value: Channel value specification to apply

        Returns:
            True if channel was applied, False if channel doesn't exist
        """
        dmx_channel = self._get_dmx_channel(channel_value.channel)
        if dmx_channel is None or dmx_channel == 0:
            logger.debug(f"Channel '{channel_value.channel}' not available on this fixture")
            return False

        # Get the DMX value (static or from curve evaluation)
        if channel_value.static_dmx is not None:
            dmx_value = channel_value.static_dmx
        else:
            # For now, just use base_dmx if available, or 0
            # Full curve evaluation would happen elsewhere
            dmx_value = channel_value.base_dmx or 0

        # Clamp to configured range
        dmx_value = clamp(dmx_value, channel_value.clamp_min, channel_value.clamp_max)

        # Apply inversion if configured
        if self._is_inverted(channel_value.channel):
            dmx_value = 255 - dmx_value

        # Set value curve if provided
        if channel_value.value_points:
            self.value_points[dmx_channel] = channel_value.value_points
        else:
            self.values[dmx_channel] = dmx_value

        logger.debug(f"Applied {channel_value.channel} (DMX{dmx_channel}) = {dmx_value}")
        return True

    def set_channel(
        self,
        channel_name: ChannelName,
        value: int | str,
        value_points: list[CurvePoint] | None = None,
    ) -> bool:
        """Set a channel value by logical name (legacy interface).

        Args:
            channel_name: Logical channel name
            value: DMX integer value (0-255)
            value_points: Optional list of CurvePoint for smooth transitions

        Returns:
            True if channel was set, False if channel doesn't exist
        """
        # For now, only support integer values
        if isinstance(value, str):
            logger.warning(f"String value '{value}' not supported yet, skipping")
            return False

        channel_value = ChannelValue(
            channel=channel_name,
            static_dmx=int(value),
            value_points=value_points,
        )
        return self.apply_channel_value(channel_value)

    def get_channel(self, channel_name: ChannelName) -> int | None:
        """Get current DMX value for a channel."""
        dmx_channel = self._get_dmx_channel(channel_name)
        if dmx_channel is None:
            return None
        return self.values.get(dmx_channel)

    def to_dmx_dict(self) -> dict[int, int]:
        """Get final DMX channel values."""
        return self.values.copy()

    def to_value_curves_dict(self) -> dict[int, list[CurvePoint]]:
        """Get value curves for channels."""
        return self.value_points.copy()

    def merge(self, other: ChannelState) -> None:
        """Merge another channel state into this one."""
        self.values.update(other.values)
        self.value_points.update(other.value_points)
