"""Timeline models for the rendering pipeline.

These models represent the exploded timeline - a flat list of all segments
(template steps and gaps) that will be rendered to effects.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field, field_validator

# TransitionSpec is defined in the agents module, import from there
from blinkb0t.core.agents.moving_heads.models_agent_plan import TransitionSpec


class TemplateStepSegment(BaseModel):
    """A template execution segment on the timeline.

    Represents a single template step that will be rendered to per-fixture effects.
    Contains all information needed for rendering (timing, targets, parameters).

    Attributes:
        step_id: Unique identifier for this step
        section_id: Which section this belongs to
        start_ms: Start time in milliseconds
        end_ms: End time in milliseconds
        template_id: Which template to use
        movement_id: Movement pattern ID
        movement_params: Parameters for movement pattern
        geometry_id: Optional geometry transformation ID
        geometry_params: Optional geometry parameters
        dimmer_id: Dimmer pattern ID
        dimmer_params: Parameters for dimmer pattern
        base_pose: Base pose ID (e.g., 'AUDIENCE_CENTER')
        target: Target group ('ALL', 'LEFT', 'RIGHT', 'ODD', 'EVEN', or fixture_id)
        entry_transition: Optional entry transition specification
        exit_transition: Optional exit transition specification
    """

    # Identity
    step_id: str = Field(description="Unique identifier for this step")
    section_id: str = Field(description="Which section this belongs to")

    # Timing
    start_ms: float = Field(description="Start time in milliseconds", ge=0)
    end_ms: float = Field(description="End time in milliseconds", ge=0)

    # Template specification
    template_id: str = Field(description="Template ID from library")
    movement_id: str = Field(description="Movement pattern ID")
    movement_params: dict[str, Any] = Field(
        default_factory=dict, description="Parameters for movement pattern"
    )

    # Geometry config
    geometry_id: str | None = Field(default=None, description="Optional geometry transformation ID")
    geometry_params: dict[str, Any] | None = Field(
        default=None, description="Optional geometry parameters"
    )

    # Dimmer
    dimmer_id: str = Field(description="Dimmer pattern ID")
    dimmer_params: dict[str, Any] = Field(
        default_factory=dict, description="Parameters for dimmer pattern"
    )

    # Pose & targeting
    base_pose: str = Field(description="Base pose ID (e.g., 'AUDIENCE_CENTER')")
    target: str = Field(
        description="Target group ('ALL', 'LEFT', 'RIGHT', 'ODD', 'EVEN', or fixture_id)"
    )

    # Transitions
    entry_transition: TransitionSpec | None = Field(
        default=None, description="Optional entry transition"
    )
    exit_transition: TransitionSpec | None = Field(
        default=None, description="Optional exit transition"
    )

    @field_validator("end_ms")
    @classmethod
    def validate_timing(cls, v: float, info: Any) -> float:  # type: ignore[misc]
        """Validate that end_ms > start_ms."""
        if "start_ms" in info.data and v <= info.data["start_ms"]:
            raise ValueError(
                f"end_ms ({v}) must be greater than start_ms ({info.data['start_ms']})"
            )
        return v


class GapSegment(BaseModel):
    """A gap in the timeline (no template execution).

    Represents time where fixtures should hold at SOFT_HOME position.
    Used for inter-section gaps, intra-section gaps, and end-of-song holds.

    Attributes:
        start_ms: Start time in milliseconds
        end_ms: End time in milliseconds
        section_id: Optional section ID this gap is associated with
        gap_type: Type of gap ('intra_section', 'inter_section', 'end_of_song')
    """

    # Timing
    start_ms: float = Field(description="Start time in milliseconds", ge=0)
    end_ms: float = Field(description="End time in milliseconds", ge=0)

    # Context
    section_id: str | None = Field(
        default=None, description="Optional section ID this gap is associated with"
    )
    gap_type: str = Field(
        description="Type of gap ('intra_section', 'inter_section', 'end_of_song')"
    )

    @field_validator("end_ms")
    @classmethod
    def validate_timing(cls, v: float, info: Any) -> float:  # type: ignore[misc]
        """Validate that end_ms > start_ms."""
        if "start_ms" in info.data and v <= info.data["start_ms"]:
            raise ValueError(
                f"end_ms ({v}) must be greater than start_ms ({info.data['start_ms']})"
            )
        return v


class ExplodedTimeline(BaseModel):
    """Complete timeline with all segments ordered chronologically.

    Represents the full timeline as a flat list of segments (template steps + gaps).
    This is the output of TemplateTimelinePlanner and input to the rendering pipeline.

    Attributes:
        segments: List of all segments (TemplateStepSegment or GapSegment) in order
        total_duration_ms: Total duration of the timeline in milliseconds
    """

    segments: list[TemplateStepSegment | GapSegment] = Field(
        description="All segments (template steps and gaps) in chronological order"
    )
    total_duration_ms: float = Field(description="Total timeline duration in milliseconds", ge=0)
