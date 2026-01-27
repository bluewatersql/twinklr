"""Transition models for the moving head sequencer.

This module defines all transition-related models:
- TransitionHint: Agent/template specification for transitions
- Boundary: Transition boundary between segments
- TransitionPlan: Complete plan for a single transition
- TransitionRegistry: Registry of all transitions in a plan
- TransitionStrategy: Per-channel transition strategies
"""

from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from blinkb0t.core.curves.library import CurveLibrary
from blinkb0t.core.sequencer.models.enum import ChannelName, TransitionMode


class TransitionStrategy(str, Enum):
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

    mode: TransitionMode = Field(default=TransitionMode.CROSSFADE, description="Transition mode")

    duration_bars: float = Field(
        default=0.5,
        ge=0.0,
        le=8.0,
        description="Transition duration in bars (0.0 = instant/SNAP)",
    )

    curve: CurveLibrary = Field(
        default=CurveLibrary.EASE_IN_OUT_SINE,
        description="Interpolation curve for smooth transitions",
    )

    fade_out_ratio: float = Field(
        default=0.5,
        ge=0.0,
        le=1.0,
        description="For crossfades, ratio of fade-out to total duration",
    )

    per_channel_overrides: dict[str, TransitionStrategy] | None = Field(
        default=None, description="Optional per-channel strategy overrides"
    )

    @property
    def is_snap(self) -> bool:
        """Check if this is a snap transition (instant)."""
        return self.mode == TransitionMode.SNAP or self.duration_bars == 0.0


class BoundaryType(str, Enum):
    """Type of transition boundary."""

    SECTION_BOUNDARY = "section"  # Between plan sections
    STEP_BOUNDARY = "step"  # Between template steps
    CYCLE_BOUNDARY = "cycle"  # Between repeat cycles


class Boundary(BaseModel):
    """A transition boundary between two segments.

    Represents a point in time where a transition may occur.

    Attributes:
        type: Type of boundary (section, step, cycle).
        source_id: Identifier of segment ending at boundary.
        target_id: Identifier of segment starting at boundary.
        time_ms: Boundary time in milliseconds.
        bar_position: Boundary position in bars (musical time).
    """

    model_config = ConfigDict(extra="forbid")

    type: BoundaryType
    source_id: str
    target_id: str
    time_ms: int = Field(ge=0)
    bar_position: float = Field(ge=0.0)


class TransitionPlan(BaseModel):
    """Complete plan for a single transition.

    Contains all information needed to generate transition segments:
    - Timing (when and how long)
    - Source and target states (what we're transitioning from/to)
    - Blend strategy (how to interpolate channels)

    Attributes:
        transition_id: Unique identifier for this transition.
        boundary: The boundary this transition spans.
        hint: The transition hint (from agent or template).
        overlap_start_ms: When transition region starts.
        overlap_end_ms: When transition region ends.
        overlap_duration_ms: Duration of transition region.
        channel_strategies: Per-channel transition strategies.
        fixtures: List of fixture IDs involved in transition.
        metadata: Additional transition metadata.
    """

    model_config = ConfigDict(extra="forbid")

    transition_id: str = Field(description="Unique transition identifier")
    boundary: Boundary
    hint: TransitionHint

    # Timing
    overlap_start_ms: int = Field(ge=0, description="Transition start time")
    overlap_end_ms: int = Field(ge=0, description="Transition end time")
    overlap_duration_ms: int = Field(ge=0, description="Transition duration")

    # Blending strategy
    channel_strategies: dict[ChannelName, TransitionStrategy] = Field(
        default_factory=dict, description="Per-channel transition strategies"
    )

    # Fixtures involved
    fixtures: list[str] = Field(
        default_factory=list, description="Fixture IDs involved in this transition"
    )

    # Metadata
    metadata: dict[str, Any] = Field(
        default_factory=dict, description="Additional transition metadata"
    )

    @property
    def duration_bars(self) -> float:
        """Get transition duration in bars (from hint)."""
        return self.hint.duration_bars


class TransitionRegistry(BaseModel):
    """Registry of all transitions in a choreography plan.

    Provides lookup and management of transition plans.

    Attributes:
        transitions: List of all transition plans.
    """

    model_config = ConfigDict(extra="forbid")

    transitions: list[TransitionPlan] = Field(
        default_factory=list, description="All transition plans"
    )

    def add_transition(self, plan: TransitionPlan) -> None:
        """Add a transition plan to registry.

        Args:
            plan: Transition plan to add.
        """
        self.transitions.append(plan)

    def get_by_boundary(self, boundary: Boundary) -> TransitionPlan | None:
        """Get transition plan for a specific boundary.

        Args:
            boundary: Boundary to look up.

        Returns:
            TransitionPlan if found, None otherwise.
        """
        for transition in self.transitions:
            if (
                transition.boundary.source_id == boundary.source_id
                and transition.boundary.target_id == boundary.target_id
            ):
                return transition
        return None

    def get_incoming(self, section_name: str) -> TransitionPlan | None:
        """Get transition INTO a section.

        Args:
            section_name: Name of target section.

        Returns:
            TransitionPlan if found, None otherwise.
        """
        for transition in self.transitions:
            if transition.boundary.target_id == section_name:
                return transition
        return None

    def get_outgoing(self, section_name: str) -> TransitionPlan | None:
        """Get transition OUT OF a section.

        Args:
            section_name: Name of source section.

        Returns:
            TransitionPlan if found, None otherwise.
        """
        for transition in self.transitions:
            if transition.boundary.source_id == section_name:
                return transition
        return None

    def get_all_for_section(self, section_name: str) -> list[TransitionPlan]:
        """Get all transitions involving a section.

        Args:
            section_name: Section name to look up.

        Returns:
            List of all transitions involving this section.
        """
        result = []
        for transition in self.transitions:
            if (
                transition.boundary.source_id == section_name
                or transition.boundary.target_id == section_name
            ):
                result.append(transition)
        return result
