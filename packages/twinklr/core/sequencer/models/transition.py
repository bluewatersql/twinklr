"""The transition hint the moving-head plan schema carries.

- TransitionHint: the planner's transition preference for a section
- TransitionStrategy: per-channel transition strategies it may name
"""

from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

from twinklr.core.curves.library import CurveLibrary
from twinklr.core.sequencer.models.enum import TransitionMode


class TransitionStrategy(StrEnum):
    """Strategy for transitioning a specific channel.

    Different channels may require different transition strategies:
    - Movement channels (pan/tilt): smooth interpolation
    - Intensity channels (dimmer): crossfade
    - Discrete channels (shutter/gobo): snap or sequenced changes

    Attributes:
        SNAP: Instant change at boundary (no blend).
        SMOOTH_INTERPOLATION: Linear or curved interpolation (pan/tilt).
        CROSSFADE: Overlapping fade out/in (dimmer).
        FADE_VIA_BLACK: Fade to zero, change, fade up (color/gobo).
        SEQUENCE: Sequenced change (e.g., close shutter, change, open).
    """

    SNAP = "snap"
    SMOOTH_INTERPOLATION = "smooth"
    CROSSFADE = "crossfade"
    FADE_VIA_BLACK = "fade_via_black"
    SEQUENCE = "sequence"


class ChannelTransitionOverrides(BaseModel):
    """Strict, closed set of optional per-channel transition strategies."""

    pan: TransitionStrategy | None = Field(description="Pan override, or null")
    tilt: TransitionStrategy | None = Field(description="Tilt override, or null")
    dimmer: TransitionStrategy | None = Field(description="Dimmer override, or null")
    shutter: TransitionStrategy | None = Field(description="Shutter override, or null")
    color: TransitionStrategy | None = Field(description="Color override, or null")
    gobo: TransitionStrategy | None = Field(description="Gobo override, or null")

    model_config = ConfigDict(extra="forbid", frozen=True)

    @model_validator(mode="before")
    @classmethod
    def _normalize_legacy_mapping(cls, value: Any) -> Any:
        if isinstance(value, dict):
            return {
                "pan": None,
                "tilt": None,
                "dimmer": None,
                "shutter": None,
                "color": None,
                "gobo": None,
                **value,
            }
        return value


class TransitionHint(BaseModel):
    """Hint for how to transition into a section or step.

    This is the agent's or template's way of specifying transition preferences.
    The rendering pipeline will honor these hints when generating transitions.

    Attributes:
        mode: Transition mode (SNAP, CROSSFADE, MORPH).
        duration_bars: Transition duration in bars.
        curve: Curve to use for interpolation (LINEAR, EASE_IN_OUT, etc.).
        fade_out_ratio: For crossfades, ratio of fade-out to total duration (0.0-1.0).
        per_channel_overrides: Optional per-channel strategy overrides.

    Examples:
        >>> # Quick snap transition
        >>> TransitionHint(mode=TransitionMode.SNAP, duration_bars=0.0)

        >>> # Smooth crossfade
        >>> TransitionHint(
        ...     mode=TransitionMode.CROSSFADE,
        ...     duration_bars=1.0,
        ...     curve=CurveLibrary.EASE_IN_OUT,
        ...     fade_out_ratio=0.5
        ... )

        >>> # Custom per-channel strategies
        >>> TransitionHint(
        ...     mode=TransitionMode.CROSSFADE,
        ...     duration_bars=1.5,
        ...     per_channel_overrides={
        ...         "dimmer": TransitionStrategy.FADE_VIA_BLACK,
        ...         "color": TransitionStrategy.SNAP
        ...     }
        ... )
    """

    model_config = ConfigDict(extra="forbid")

    mode: TransitionMode = Field(description="Transition mode")

    duration_bars: float = Field(
        ge=0.0,
        le=8.0,
        description="Transition duration in bars (0.0 = instant/SNAP)",
    )

    curve: CurveLibrary = Field(
        description="Interpolation curve for smooth transitions",
    )

    fade_out_ratio: float = Field(
        ge=0.0,
        le=1.0,
        description="For crossfades, ratio of fade-out to total duration",
    )

    per_channel_overrides: ChannelTransitionOverrides | None = Field(
        description="Optional per-channel strategy overrides, or null"
    )

    @model_validator(mode="before")
    @classmethod
    def _normalize_legacy_defaults(cls, value: Any) -> Any:
        if isinstance(value, dict):
            return {
                "mode": TransitionMode.CROSSFADE,
                "duration_bars": 0.5,
                "curve": CurveLibrary.EASE_IN_OUT_SINE,
                "fade_out_ratio": 0.5,
                "per_channel_overrides": None,
                **value,
            }
        return value
