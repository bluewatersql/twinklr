"""Models for the template compilation pipeline.

Defines the intermediate representations produced by the
TemplateCompiler and consumed by the CompositionEngine
for multi-layer template rendering.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from twinklr.core.sequencer.display.models.render_event import RenderEvent
from twinklr.core.sequencer.vocabulary import VisualDepth


class CompiledEffect(BaseModel):
    """A single compiled effect from a template's LayerRecipe.

    Bundles a fully-formed ``RenderEvent`` with its intended visual
    depth so the composition engine can assign it to the correct
    xLights layer.

    Attributes:
        event: The render event (timing, effect type, parameters,
            palette, value curves, etc.).
        visual_depth: Target visual depth from the LayerRecipe
            (BACKGROUND, MIDGROUND, FOREGROUND, etc.).
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    event: RenderEvent = Field(description="Compiled render event")
    visual_depth: VisualDepth = Field(
        description="Target visual depth for layer allocation",
    )


class TemplateCompileError(Exception):
    """Raised when a template cannot be compiled to effects.

    Carries structured context for fast debugging of rendering
    failures.  Sequences are complex layered orchestrations —
    silent fallbacks would produce subtle, hard-to-debug output
    issues, so every compilation failure is loud.

    Attributes:
        template_id: Which template failed.
        section_id: Which section in the plan.
        placement_id: Which placement within the section.
        reason: What specifically went wrong.
    """

    def __init__(
        self,
        *,
        template_id: str,
        reason: str,
        section_id: str = "",
        placement_id: str = "",
    ) -> None:
        self.template_id = template_id
        self.section_id = section_id
        self.placement_id = placement_id
        self.reason = reason
        parts = [f"Template '{template_id}' compile failed: {reason}"]
        if section_id:
            parts.append(f"section={section_id}")
        if placement_id:
            parts.append(f"placement={placement_id}")
        super().__init__(" | ".join(parts))


__all__ = [
    "CompiledEffect",
    "TemplateCompileError",
]
