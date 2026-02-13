"""Render event models for the display renderer.

RenderEvent is the atomic unit of the RenderPlan — a single effect
placement with all information needed by an EffectHandler.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from twinklr.core.sequencer.display.models.palette import (
    ResolvedPalette,
    TransitionSpec,
)
from twinklr.core.sequencer.vocabulary import LaneKind


class RenderEventSource(BaseModel):
    """Traceability link from a RenderEvent back to its planning origin.

    Attributes:
        section_id: Source section ID.
        lane: Source lane (BASE/RHYTHM/ACCENT).
        group_id: Source group ID.
        template_id: Source template ID from the plan.
        placement_index: Index of the placement within the coordination plan.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    section_id: str
    lane: LaneKind
    group_id: str
    template_id: str
    placement_index: int = 0


class RenderEvent(BaseModel):
    """A single effect placement in the render plan.

    Contains all information an EffectHandler needs to produce an
    xLights EffectDB settings string and ColorPalette string.

    Attributes:
        event_id: Unique identifier for this event.
        start_ms: Start time in milliseconds.
        end_ms: End time in milliseconds.
        effect_type: xLights effect type name (e.g., 'Color Wash').
        parameters: Effect-specific parameters (xLights-native keys).
        buffer_style: xLights buffer style.
        buffer_transform: Optional buffer transform (e.g., 'Rotate CC 90').
        palette: Resolved color palette for this event.
        intensity: Normalized intensity (0.0-1.0).
        transition_in: Optional incoming transition.
        transition_out: Optional outgoing transition.
        source: Traceability back to the planning origin.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    event_id: str = Field(description="Unique event identifier")
    start_ms: int = Field(ge=0, description="Start time in milliseconds")
    end_ms: int = Field(ge=0, description="End time in milliseconds")
    effect_type: str = Field(description="xLights effect type name")
    parameters: dict[str, Any] = Field(
        default_factory=dict,
        description="Effect-specific parameters",
    )
    buffer_style: str = Field(
        default="Per Model Default",
        description="xLights buffer style",
    )
    buffer_transform: str | None = Field(
        default=None,
        description="Optional buffer transform",
    )
    palette: ResolvedPalette = Field(description="Resolved color palette")
    intensity: float = Field(
        default=1.0,
        ge=0.0,
        le=1.0,
        description="Normalized intensity (0.0-1.0)",
    )
    transition_in: TransitionSpec | None = Field(
        default=None,
        description="Optional incoming transition",
    )
    transition_out: TransitionSpec | None = Field(
        default=None,
        description="Optional outgoing transition",
    )
    source: RenderEventSource = Field(
        description="Traceability to planning origin",
    )

    @property
    def duration_ms(self) -> int:
        """Effect duration in milliseconds."""
        return self.end_ms - self.start_ms


__all__ = [
    "RenderEvent",
    "RenderEventSource",
]
