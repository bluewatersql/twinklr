"""Template compiler for the display rendering pipeline.

Replaces the 1:1 ``resolve_effect_type()`` keyword mapping with a
``TemplateCompiler`` protocol that reads ``GroupPlanTemplate`` layer
recipes and emits multiple ``CompiledEffect``s — one per
``LayerRecipe``.

The default implementation (``DefaultTemplateCompiler``) uses the
motif-primary ``effect_resolver`` and value curve bridge to produce
fully parameterised ``RenderEvent``s tagged with ``VisualDepth``.

**No silent fallback.**  If a template is not found, has an empty
``layer_recipe``, or contains unrecognised motifs, a
``TemplateCompileError`` is raised immediately.
"""

from __future__ import annotations

import logging
from typing import Any, Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict, Field

from twinklr.core.sequencer.display.composition.effect_resolver import (
    resolve_effect,
)
from twinklr.core.sequencer.display.composition.models import (
    CompiledEffect,
    TemplateCompileError,
)
from twinklr.core.sequencer.display.models.palette import ResolvedPalette
from twinklr.core.sequencer.display.models.render_event import (
    RenderEvent,
    RenderEventSource,
)
from twinklr.core.sequencer.display.templates.effect_map import (
    filter_valid_overrides,
)
from twinklr.core.sequencer.templates.group.library import (
    GroupTemplateRegistry,
)
from twinklr.core.sequencer.templates.group.models.coordination import (
    GroupPlacement,
)
from twinklr.core.sequencer.templates.group.models.template import (
    GroupPlanTemplate,
    LayerRecipe,
)
from twinklr.core.sequencer.templates.shared.registry import (
    TemplateNotFoundError,
)
from twinklr.core.sequencer.vocabulary import LaneKind

logger = logging.getLogger(__name__)


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

    model_config = ConfigDict(extra="forbid", frozen=True)

    section_id: str
    lane: LaneKind
    palette: ResolvedPalette
    start_ms: int = Field(ge=0)
    end_ms: int = Field(ge=0)
    intensity: float = Field(ge=0.0, le=1.0)
    placement_index: int = Field(ge=0)
    transition_in: Any = None
    transition_out: Any = None


# ------------------------------------------------------------------
# Protocol
# ------------------------------------------------------------------


@runtime_checkable
class TemplateCompiler(Protocol):
    """Protocol for template compilation.

    Implementors translate a ``GroupPlacement`` into a list of
    ``CompiledEffect``s using the ``GroupPlanTemplate`` layer recipes.
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
            List of CompiledEffect (one per LayerRecipe).

        Raises:
            TemplateCompileError: If the template cannot be compiled.
        """
        ...


# ------------------------------------------------------------------
# Default implementation
# ------------------------------------------------------------------


class DefaultTemplateCompiler:
    """Default template compiler using the group template registry.

    Loads the ``GroupPlanTemplate`` from the registry, iterates its
    ``layer_recipe`` list, and uses ``resolve_effect`` for each
    recipe to produce ``CompiledEffect``s.

    **Error handling policy:** hard fail on everything.

    - Template not found → ``TemplateCompileError``
    - Empty ``layer_recipe`` → ``TemplateCompileError``
    - No recognised motif → ``TemplateCompileError``
    """

    def __init__(self, registry: GroupTemplateRegistry) -> None:
        """Initialise with a group template registry.

        Args:
            registry: Registry to look up GroupPlanTemplates.
        """
        self._registry = registry

    def compile(
        self,
        placement: GroupPlacement,
        context: TemplateCompileContext,
    ) -> list[CompiledEffect]:
        """Compile a GroupPlacement into compiled effects.

        Args:
            placement: Group placement from the plan.
            context: Compilation context from the engine.

        Returns:
            List of CompiledEffect (one per LayerRecipe).

        Raises:
            TemplateCompileError: On any compilation failure.
        """
        template_id = placement.template_id

        # --- Load template from registry (hard error if missing) ---
        template = self._load_template(template_id, context.section_id)

        # --- Validate layer_recipe is non-empty (hard error) ---
        if not template.layer_recipe:
            raise TemplateCompileError(
                template_id=template_id,
                reason="template has empty layer_recipe — every template must define at least one layer",
                section_id=context.section_id,
                placement_id=placement.placement_id,
            )

        # --- Compile each LayerRecipe ---
        compiled: list[CompiledEffect] = []
        for recipe_idx, recipe in enumerate(template.layer_recipe):
            effect = self._compile_recipe(
                recipe=recipe,
                recipe_idx=recipe_idx,
                placement=placement,
                context=context,
                template_id=template_id,
            )
            compiled.append(effect)

        logger.debug(
            "Compiled template '%s' → %d effects (%s)",
            template_id,
            len(compiled),
            ", ".join(f"{ce.visual_depth.value}:{ce.event.effect_type}" for ce in compiled),
        )
        return compiled

    def _load_template(
        self,
        template_id: str,
        section_id: str,
    ) -> GroupPlanTemplate:
        """Load template from registry with hard error on missing.

        Args:
            template_id: Template to load.
            section_id: Section context for error messages.

        Returns:
            GroupPlanTemplate instance.

        Raises:
            TemplateCompileError: If template not found.
        """
        try:
            return self._registry.get(template_id)
        except TemplateNotFoundError as exc:
            raise TemplateCompileError(
                template_id=template_id,
                reason=f"template not found in registry (registered: {len(self._registry)} templates)",
                section_id=section_id,
            ) from exc

    def _compile_recipe(
        self,
        *,
        recipe: LayerRecipe,
        recipe_idx: int,
        placement: GroupPlacement,
        context: TemplateCompileContext,
        template_id: str,
    ) -> CompiledEffect:
        """Compile a single LayerRecipe into a CompiledEffect.

        Uses the motif-primary effect resolver to determine effect type,
        parameters, and value curves from the recipe's semantic fields.

        Args:
            recipe: Layer recipe to compile.
            recipe_idx: Index of this recipe in the template.
            placement: Parent placement.
            context: Compilation context.
            template_id: Parent template ID.

        Returns:
            CompiledEffect with resolved RenderEvent and visual depth.

        Raises:
            TemplateCompileError: If motifs are unrecognised.
        """
        # --- Resolve effect via motif-primary resolver ---
        try:
            resolved = resolve_effect(
                motifs=recipe.motifs,
                motion=recipe.motion,
                density=recipe.density,
                contrast=recipe.contrast,
                visual_depth=recipe.layer,
            )
        except ValueError as exc:
            raise TemplateCompileError(
                template_id=template_id,
                reason=f"layer[{recipe_idx}] ({recipe.layer.value}): {exc}",
                section_id=context.section_id,
                placement_id=placement.placement_id,
            ) from exc

        # --- Merge valid param_overrides from the placement ---
        params = dict(resolved.parameters)
        if placement.param_overrides:
            valid = filter_valid_overrides(resolved.effect_type, placement.param_overrides)
            params.update(valid)

        # --- Build RenderEvent ---
        event = RenderEvent(
            event_id=f"{context.section_id}_{placement.placement_id}_L{recipe_idx}",
            start_ms=context.start_ms,
            end_ms=context.end_ms,
            effect_type=resolved.effect_type,
            parameters=params,
            buffer_style=resolved.buffer_style,
            buffer_transform=resolved.buffer_transform,
            palette=context.palette,
            intensity=context.intensity,
            value_curves=resolved.value_curves,
            transition_in=context.transition_in,
            transition_out=context.transition_out,
            source=RenderEventSource(
                section_id=context.section_id,
                lane=context.lane,
                group_id=placement.target.id,
                template_id=template_id,
                placement_index=context.placement_index,
            ),
        )

        return CompiledEffect(
            event=event,
            visual_depth=recipe.layer,
        )


__all__ = [
    "DefaultTemplateCompiler",
    "TemplateCompileContext",
    "TemplateCompiler",
]
