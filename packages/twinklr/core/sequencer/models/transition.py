"""The section transition the moving-head plan carries.

- PlanTransition: the planner's categorical transition into (ENTRY) or out of (EXIT) a
  section
- ChannelTransition: one per-channel strategy override within a transition

Every field is a category: the renderer, not the planner, turns a length, curve and split
into milliseconds and DMX values.
"""

from __future__ import annotations

from enum import StrEnum

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


class TransitionEdge(StrEnum):
    """Which edge of its section a transition shapes."""

    ENTRY = "ENTRY"
    EXIT = "EXIT"


class TransitionLength(StrEnum):
    """How long a transition lasts, on the song's beat grid."""

    BEAT = "BEAT"
    HALF_BAR = "HALF_BAR"
    BAR = "BAR"
    ONE_AND_HALF_BARS = "ONE_AND_HALF_BARS"
    TWO_BARS = "TWO_BARS"
    THREE_BARS = "THREE_BARS"
    FOUR_BARS = "FOUR_BARS"
    SIX_BARS = "SIX_BARS"
    EIGHT_BARS = "EIGHT_BARS"


class TransitionSplit(StrEnum):
    """How much of a crossfade the outgoing look takes to fade out before the incoming
    look takes over: a quarter, a third, half, two thirds or three quarters of it."""

    QUARTER = "QUARTER"
    THIRD = "THIRD"
    HALF = "HALF"
    TWO_THIRDS = "TWO_THIRDS"
    THREE_QUARTERS = "THREE_QUARTERS"


class TransitionChannel(StrEnum):
    """A channel a transition may give its own strategy."""

    PAN = "pan"
    TILT = "tilt"
    DIMMER = "dimmer"
    SHUTTER = "shutter"
    COLOR = "color"
    GOBO = "gobo"


class ChannelTransition(BaseModel):
    """One channel's own transition strategy, overriding the transition's mode."""

    channel: TransitionChannel = Field(description="The channel this strategy applies to")
    strategy: TransitionStrategy = Field(description="How this channel changes")

    model_config = ConfigDict(extra="forbid", frozen=True)


class PlanTransition(BaseModel):
    """The planner's transition into or out of a section, as categories.

    Examples:
        >>> PlanTransition(
        ...     edge=TransitionEdge.ENTRY,
        ...     mode=TransitionMode.CROSSFADE,
        ...     length=TransitionLength.BAR,
        ...     curve=CurveLibrary.EASE_IN_OUT_SINE,
        ...     split=TransitionSplit.HALF,
        ...     channels=[],
        ... ).length
        <TransitionLength.BAR: 'BAR'>
    """

    edge: TransitionEdge = Field(description="ENTRY shapes the section's start, EXIT its end")
    mode: TransitionMode = Field(description="How the look changes across the boundary")
    length: TransitionLength = Field(description="How long the change lasts")
    curve: CurveLibrary = Field(description="The easing of the change")
    split: TransitionSplit = Field(
        description="The share of the change the outgoing look takes to fade out"
    )
    channels: list[ChannelTransition] = Field(
        description="Per-channel strategies overriding the mode; empty when none",
        max_length=len(TransitionChannel),
    )

    model_config = ConfigDict(extra="forbid", frozen=True)

    @model_validator(mode="after")
    def _one_strategy_per_channel(self) -> PlanTransition:
        channels = [entry.channel for entry in self.channels]
        if len(channels) != len(set(channels)):
            raise ValueError("a transition names each channel at most once")
        return self

    def describe(self) -> str:
        """One line: mode, length, curve, split and any per-channel strategies."""
        line = (
            f"{self.mode.value} over {self.length.value}, curve {self.curve.value}, "
            f"split {self.split.value}"
        )
        if self.channels:
            line += "; " + ", ".join(
                f"{entry.channel.value} {entry.strategy.value}" for entry in self.channels
            )
        return line
