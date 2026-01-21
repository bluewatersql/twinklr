"""Pydantic models for channel specification system.

NOTE: ChannelDefaults has been moved to blinkb0t.core.config.models
to avoid circular imports. Import it from there instead:

    from blinkb0t.core.config.models import ChannelDefaults
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel, ConfigDict, Field

from blinkb0t.core.domains.sequencing.models.curves import ValueCurveSpec

if TYPE_CHECKING:
    from blinkb0t.core.domains.sequencing.channels.state import ChannelState


class ChannelSpecification(BaseModel):
    """Section-level channel specification.

    Overrides job-level defaults for a specific section.
    None/null values inherit from job defaults.

    Example:
        >>> spec = ChannelSpecification(shutter="strobe_fast", gobo="stars")
        >>> spec.has_override("shutter")  # True
        >>> spec.has_override("color")    # False
        >>> spec.get_overrides()  # {"shutter": "strobe_fast", "gobo": "stars"}
    """

    shutter: str | None = Field(
        default=None, description="Shutter override (None = inherit from job defaults)"
    )

    color: str | None = Field(
        default=None, description="Color override (None = inherit from job defaults)"
    )

    gobo: str | None = Field(
        default=None, description="Gobo override (None = inherit from job defaults)"
    )

    model_config = ConfigDict(
        extra="forbid",  # Reject unknown fields
    )

    def has_override(self, channel: str) -> bool:
        """Check if this spec overrides a specific channel.

        Args:
            channel: Channel name ("shutter", "color", or "gobo")

        Returns:
            True if channel is overridden (not None)
        """
        value = getattr(self, channel, None)
        return value is not None

    def get_overrides(self) -> dict[str, str]:
        """Get all non-None channel overrides.

        Returns:
            Dictionary of channel name -> override value
        """
        return {
            channel: value
            for channel in ["shutter", "color", "gobo"]
            if (value := getattr(self, channel, None)) is not None
        }


@dataclass(frozen=True)
class ResolvedChannels:
    """Resolved channel values for a section.

    Result of applying section overrides on top of job defaults.
    Immutable once resolved to prevent accidental modification.

    All channel values must be non-empty strings.

    Example:
        >>> resolved = ResolvedChannels(
        ...     shutter="strobe_fast",
        ...     color="white",
        ...     gobo="stars"
        ... )
        >>> resolved.shutter  # "strobe_fast"
    """

    shutter: str
    color: str
    gobo: str

    def __post_init__(self) -> None:
        """Validate resolved values are non-empty strings."""
        for channel in ["shutter", "color", "gobo"]:
            value = getattr(self, channel)
            if not value or not isinstance(value, str):
                raise ValueError(f"Resolved channel '{channel}' must be non-empty string")


class ChannelEffect(BaseModel):
    """DMX effect for a single channel.

    Represents the output of a channel handler - a time-resolved DMX effect
    for a specific channel on a specific fixture.

    Uses existing value curve system:
    - If value_curve is None: Constant/fixed DMX value (use dmx_values[0])
    - If value_curve is specified: Use curve for interpolation

    This aligns with the existing curve system used throughout the codebase.

    Example (Constant):
        >>> effect = ChannelEffect(
        ...     fixture_id="MH1",
        ...     channel_name="shutter",
        ...     start_time_ms=0,
        ...     end_time_ms=8000,
        ...     dmx_values=[255],
        ...     value_curve=None  # Constant value
        ... )

    Example (Dynamic with curve):
        >>> from blinkb0t.core.domains.sequencing.models.curves import ValueCurveSpec
        >>> from blinkb0t.core.domains.sequencing.infrastructure.curves.enums import NativeCurveType
        >>> curve = ValueCurveSpec(type=NativeCurveType.RAMP, p2=150.0)
        >>> effect = ChannelEffect(
        ...     fixture_id="MH1",
        ...     channel_name="shutter",
        ...     start_time_ms=0,
        ...     end_time_ms=8000,
        ...     dmx_values=[0, 150],
        ...     value_curve=curve
        ... )
    """

    fixture_id: str = Field(description="Fixture this effect applies to")

    channel_name: str = Field(description="DMX channel name (shutter, color, gobo, etc.)")

    start_time_ms: int = Field(ge=0, description="Effect start time in milliseconds")

    end_time_ms: int = Field(ge=0, description="Effect end time in milliseconds")

    dmx_values: list[int] = Field(description="DMX values (0-255) over time")

    value_curve: ValueCurveSpec | None = Field(
        default=None,
        description="Optional value curve for interpolation. If None, dmx_values[0] is constant.",
    )

    model_config = ConfigDict(extra="forbid")

    def model_post_init(self, __context: object) -> None:
        """Validate effect after initialization."""
        if self.end_time_ms <= self.start_time_ms:
            raise ValueError("end_time_ms must be > start_time_ms")

        if not self.dmx_values:
            raise ValueError("dmx_values cannot be empty")

        if not all(0 <= v <= 255 for v in self.dmx_values):
            raise ValueError("All DMX values must be 0-255")


@dataclass(frozen=True)
class SequencedEffect:
    """Effect targeting semantic group with channel state.

    Represents handler output before fixture resolution.
    Handlers return these, pipeline converts to DmxEffect.

    Attributes:
        targets: Semantic group IDs (e.g., "stage_left", "ALL", "MH1")
        channels: Channel states by channel name (pan, tilt, shutter, etc.)
        start_ms: Effect start time
        end_ms: Effect end time
        metadata: Optional metadata (pattern, intensity, etc.)

    Example:
        >>> from blinkb0t.core.domains.sequencing.channels.state import ChannelState
        >>> channel_state = ChannelState(fixture="stage_left", values={"pan": 128})
        >>> effect = SequencedEffect(
        ...     targets=["stage_left"],
        ...     channels={"pan": channel_state, "tilt": channel_state},
        ...     start_ms=100,
        ...     end_ms=500,
        ...     metadata={"pattern": "circle"}
        ... )
        >>> effect.targets  # ["stage_left"]
        >>> len(effect.channels)  # 2
    """

    targets: list[str]
    channels: dict[str, ChannelState]
    start_ms: int
    end_ms: int
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """Validate effect after initialization."""
        if self.end_ms <= self.start_ms:
            raise ValueError(f"end_ms ({self.end_ms}) must be > start_ms ({self.start_ms})")
        if not self.targets:
            raise ValueError("targets cannot be empty")
        if not self.channels:
            raise ValueError("channels cannot be empty")
        # Validate all targets are strings
        if not all(isinstance(t, str) for t in self.targets):
            raise ValueError("All targets must be strings")


@dataclass(frozen=True)
class DmxEffect:
    """Discrete DMX effect for a single fixture.

    Represents a complete channel state for one fixture over a time range.
    All active channels must be explicitly set (no implicit DMX 0).

    Attributes:
        fixture_id: Resolved fixture ID (e.g., "MH1")
        start_ms: Effect start time
        end_ms: Effect end time
        channels: Complete channel state (all active channels)
        metadata: Optional metadata (type, source, etc.)

    Example:
        >>> from blinkb0t.core.domains.sequencing.channels.state import ChannelState
        >>> channel_state = ChannelState(fixture="MH1", values={"pan": 128})
        >>> effect = DmxEffect(
        ...     fixture_id="MH1",
        ...     start_ms=100,
        ...     end_ms=200,
        ...     channels={
        ...         "pan": channel_state,
        ...         "tilt": channel_state,
        ...         "shutter": channel_state,
        ...         "color": channel_state,
        ...         "gobo": channel_state
        ...     },
        ...     metadata={"type": "movement", "source": "handler"}
        ... )
        >>> effect.fixture_id  # "MH1"
        >>> len(effect.channels)  # 5
    """

    fixture_id: str
    start_ms: int
    end_ms: int
    channels: dict[str, ChannelState]
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """Validate effect after initialization."""
        if self.end_ms <= self.start_ms:
            raise ValueError(f"end_ms ({self.end_ms}) must be > start_ms ({self.start_ms})")
        if not self.fixture_id:
            raise ValueError("fixture_id cannot be empty")
        if not self.channels:
            raise ValueError("channels cannot be empty")
