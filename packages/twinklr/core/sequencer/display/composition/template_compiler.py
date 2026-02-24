"""Template compiler protocol for the display rendering pipeline.

Defines the ``TemplateCompiler`` protocol that compilers (e.g.
``RecipeCompiler``) implement to translate ``GroupPlacement``
instances into ``CompiledEffect`` lists for the composition engine.
"""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict, Field

from twinklr.core.sequencer.display.composition.models import (
    CompiledEffect,
)
from twinklr.core.sequencer.display.models.palette import ResolvedPalette
from twinklr.core.sequencer.templates.group.models.coordination import (
    GroupPlacement,
)
from twinklr.core.sequencer.vocabulary import LaneKind

# ------------------------------------------------------------------
# Compile context — all context the compiler needs from the engine
# ------------------------------------------------------------------


class TemplateCompileContext(BaseModel):
    """Context provided by the CompositionEngine for compilation.

    Carries timing, palette, and traceability information that the
    compiler needs but doesn't own.

    Attributes:
        section_id: ID of the containing section.
        lane: Lane kind (BASE, RHYTHM, ACCENT).
        palette: Resolved palette for color information.
        start_ms: Effect start time in milliseconds.
        end_ms: Effect end time in milliseconds.
        intensity: Normalised intensity (0.0-1.0).
        placement_index: Index of this placement in the plan.
        transition_in: Optional incoming transition spec.
        transition_out: Optional outgoing transition spec.
    """

    model_config = ConfigDict(extra="forbid", arbitrary_types_allowed=True)

    section_id: str
    lane: LaneKind
    palette: ResolvedPalette = Field(
        default_factory=lambda: ResolvedPalette(colors=[], active_slots=[])
    )
    start_ms: int = 0
    end_ms: int = 0
    intensity: float = 1.0
    placement_index: int = 0
    transition_in: Any = None
    transition_out: Any = None


# ------------------------------------------------------------------
# Protocol
# ------------------------------------------------------------------


@runtime_checkable
class TemplateCompiler(Protocol):
    """Protocol for template compilation.

    Implementors translate a ``GroupPlacement`` into a list of
    ``CompiledEffect``s using template layer definitions.
    """

    def compile(
        self,
        placement: GroupPlacement,
        context: TemplateCompileContext,
    ) -> list[CompiledEffect]:
        """Compile a placement into compiled effects.

        Args:
            placement: Group placement from the plan.
            context: Compilation context from the engine.

        Returns:
            List of CompiledEffect (one per layer).

        Raises:
            TemplateCompileError: If the template cannot be compiled.
        """
        ...


__all__ = [
    "TemplateCompileContext",
    "TemplateCompiler",
]
