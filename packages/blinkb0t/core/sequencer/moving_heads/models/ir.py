"""IR Segment Model for the moving head sequencer.

This module defines the Intermediate Representation (IR) for compiled
channel segments. IR segments represent the output of template compilation
and are the input to the export pipeline.

Each segment describes a single fixture + channel over a time range,
expressed as either a static DMX value or a normalized curve.
"""

from pydantic import BaseModel, ConfigDict, Field, model_validator

from blinkb0t.core.curves.models import BaseCurve
from blinkb0t.core.sequencer.moving_heads.models.channel import BlendMode, ChannelName


class ChannelSegment(BaseModel):
    """IR segment for a single fixture + channel over a time range.

    Either `static_dmx` is set OR `curve` is set (mutually exclusive).

    For offset-centered curves (movement), set offset_centered=True
    and provide base_dmx and amplitude_dmx. The final DMX value is
    computed as: base_dmx + (curve_value - 0.5) * amplitude_dmx

    For absolute curves (dimmer), leave offset_centered=False.
    The final DMX value is computed as: lerp(clamp_min, clamp_max, curve_value)

    Attributes:
        fixture_id: Unique identifier for the fixture.
        channel: The DMX channel type (PAN, TILT, DIMMER).
        t0_ms: Start time in milliseconds (inclusive).
        t1_ms: End time in milliseconds (inclusive).
        static_dmx: Static DMX value (0-255), mutually exclusive with curve.
        curve: Normalized curve specification, mutually exclusive with static_dmx.
        base_dmx: Base DMX value for offset-centered curves.
        amplitude_dmx: Amplitude for offset-centered curves.
        offset_centered: If True, interpret curve values as offset around 0.5.
        blend_mode: How to blend with overlapping segments.
        clamp_min: Minimum DMX value after composition.
        clamp_max: Maximum DMX value after composition.

    Example:
        >>> # Static segment
        >>> static_seg = ChannelSegment(
        ...     fixture_id="fix1",
        ...     channel=ChannelName.DIMMER,
        ...     t0_ms=0, t1_ms=1000,
        ...     static_dmx=255
        ... )

        >>> # Curve segment
        >>> from blinkb0t.core.curves.models import NativeCurve
        >>> curve_seg = ChannelSegment(
        ...     fixture_id="fix1",
        ...     channel=ChannelName.PAN,
        ...     t0_ms=0, t1_ms=2000,
        ...     curve=NativeCurve(curve_id="LINEAR"),
        ...     offset_centered=True,
        ...     base_dmx=128,
        ...     amplitude_dmx=64
        ... )
    """

    model_config = ConfigDict(extra="forbid")

    fixture_id: str = Field(..., min_length=1)
    channel: ChannelName

    t0_ms: int = Field(..., ge=0)
    t1_ms: int = Field(..., ge=0)

    # Option A: static value
    static_dmx: int | None = Field(default=None, ge=0, le=255)

    # Option B: curve
    curve: BaseCurve | None = Field(default=None)

    # Composition hints (for movement offset curves)
    base_dmx: int | None = Field(default=None, ge=0, le=255)
    amplitude_dmx: int | None = Field(default=None, ge=0, le=255)
    offset_centered: bool = Field(
        default=False,
        description="If true, interpret curve values as offset around 0.5",
    )

    blend_mode: BlendMode = Field(default=BlendMode.OVERRIDE)

    clamp_min: int = Field(default=0, ge=0, le=255)
    clamp_max: int = Field(default=255, ge=0, le=255)

    @model_validator(mode="after")
    def _validate_constraints(self) -> "ChannelSegment":
        """Validate segment constraints.

        - t1_ms must be >= t0_ms
        - Must have exactly one of static_dmx or curve
        - clamp_max must be >= clamp_min
        - offset_centered curves require base_dmx and amplitude_dmx
        """
        # Time ordering
        if self.t1_ms < self.t0_ms:
            raise ValueError("t1_ms must be >= t0_ms")

        # Must have exactly one of static_dmx or curve
        if self.static_dmx is None and self.curve is None:
            raise ValueError("ChannelSegment must set either static_dmx or curve")
        if self.static_dmx is not None and self.curve is not None:
            raise ValueError("ChannelSegment cannot set both static_dmx and curve")

        # Clamp bounds
        if self.clamp_max < self.clamp_min:
            raise ValueError("clamp_max must be >= clamp_min")

        # Offset-centered validation
        if self.curve is not None and self.offset_centered:
            if self.base_dmx is None or self.amplitude_dmx is None:
                raise ValueError("offset_centered curves require base_dmx and amplitude_dmx")

        return self
