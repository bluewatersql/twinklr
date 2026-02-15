"""Render plan models for the display renderer.

RenderPlan is the intermediate representation (IR) between the
CompositionEngine and the EffectRenderer/XSQWriter.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from twinklr.core.sequencer.display.models.render_event import RenderEvent
from twinklr.core.sequencer.vocabulary import LaneKind


class RenderLayerPlan(BaseModel):
    """Plan for a single effect layer within an element.

    Attributes:
        layer_index: xLights layer index (0-based).
        layer_role: Lane role (BASE/RHYTHM/ACCENT).
        blend_mode: xLights layer blend mode string.
        events: Ordered list of non-overlapping render events.
    """

    model_config = ConfigDict(extra="forbid")

    layer_index: int = Field(ge=0, description="xLights layer index (0-based)")
    layer_role: LaneKind = Field(description="Lane role for this layer")
    blend_mode: str = Field(
        default="Normal",
        description="xLights layer blend mode",
    )
    events: list[RenderEvent] = Field(
        default_factory=list,
        description="Ordered, non-overlapping render events",
    )


class RenderGroupPlan(BaseModel):
    """Plan for a single xLights element (model/group).

    Attributes:
        element_name: Exact xLights element name.
        layers: Layers of effects for this element.
    """

    model_config = ConfigDict(extra="forbid")

    element_name: str = Field(description="xLights element name")
    layers: list[RenderLayerPlan] = Field(
        default_factory=list,
        description="Effect layers for this element",
    )


class CompositionDiagnostic(BaseModel):
    """Diagnostic message from the composition engine.

    Attributes:
        level: Severity level (info, warning, error).
        message: Human-readable diagnostic message.
        source_section: Section ID that produced this diagnostic.
        source_group: Group ID that produced this diagnostic.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    level: str = Field(description="Severity: info, warning, error")
    message: str = Field(description="Diagnostic message")
    source_section: str | None = Field(default=None)
    source_group: str | None = Field(default=None)


class RenderPlan(BaseModel):
    """Complete intermediate representation for rendering.

    Produced by the CompositionEngine, consumed by the EffectRenderer
    and XSQWriter. Contains all information needed to generate
    xLights effects without referring back to the GroupPlanSet.

    Attributes:
        render_id: Unique identifier for this render plan.
        duration_ms: Total sequence duration in milliseconds.
        groups: Per-element render plans.
        diagnostics: Warnings and errors from composition.
    """

    model_config = ConfigDict(extra="forbid")

    render_id: str = Field(description="Unique render plan identifier")
    duration_ms: int = Field(ge=0, description="Sequence duration in ms")
    groups: list[RenderGroupPlan] = Field(
        default_factory=list,
        description="Per-element render plans",
    )
    diagnostics: list[CompositionDiagnostic] = Field(
        default_factory=list,
        description="Composition diagnostics",
    )

    @property
    def total_events(self) -> int:
        """Total number of render events across all elements."""
        return sum(len(layer.events) for group in self.groups for layer in group.layers)

    @property
    def element_names(self) -> list[str]:
        """List of all element names in the plan."""
        return [g.element_name for g in self.groups]


__all__ = [
    "CompositionDiagnostic",
    "RenderGroupPlan",
    "RenderLayerPlan",
    "RenderPlan",
]
