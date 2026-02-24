"""RecipeCompiler — TemplateCompiler implementation for EffectRecipe rendering.

Bridges the RecipeRenderer (abstract recipe → resolved layers) with the
CompositionEngine's TemplateCompiler protocol (placement → CompiledEffects).
"""

from __future__ import annotations

import uuid
from typing import Any

from twinklr.core.sequencer.display.composition.models import CompiledEffect, TemplateCompileError
from twinklr.core.sequencer.display.composition.template_compiler import (
    TemplateCompileContext,
)
from twinklr.core.sequencer.display.models.render_event import (
    RenderEvent,
    RenderEventSource,
)
from twinklr.core.sequencer.display.recipe_renderer import (
    RecipeRenderer,
    RenderedLayer,
    RenderEnvironment,
)
from twinklr.core.sequencer.display.templates.effect_map import resolve_effect_type
from twinklr.core.sequencer.templates.group.models import GroupPlacement
from twinklr.core.sequencer.templates.group.recipe_catalog import RecipeCatalog


class RecipeCompiler:
    """Compile EffectRecipe placements into CompiledEffects.

    Implements the TemplateCompiler protocol. Looks up recipes from
    a RecipeCatalog, renders them via RecipeRenderer, then converts
    each RenderedLayer into a CompiledEffect with proper timing and
    traceability.
    """

    def __init__(
        self,
        catalog: RecipeCatalog,
        renderer: RecipeRenderer | None = None,
    ) -> None:
        self._catalog = catalog
        self._renderer = renderer or RecipeRenderer()

    def can_compile(self, template_id: str) -> bool:
        """Check whether this compiler can handle the given template_id."""
        return self._catalog.has_recipe(template_id)

    def compile(
        self,
        placement: GroupPlacement,
        context: TemplateCompileContext,
    ) -> list[CompiledEffect]:
        """Compile a recipe-based placement into CompiledEffects.

        Args:
            placement: Group placement referencing a recipe_id.
            context: Compile context with timing, palette, intensity.

        Returns:
            List of CompiledEffect (one per recipe layer).

        Raises:
            TemplateCompileError: If recipe not found or has no layers.
        """
        recipe = self._catalog.get_recipe(placement.template_id)
        if recipe is None:
            raise TemplateCompileError(
                template_id=placement.template_id,
                reason="not found in RecipeCatalog",
            )
        if not recipe.layers:
            raise TemplateCompileError(
                template_id=placement.template_id,
                reason="recipe has no layers",
            )

        env = self._build_environment(context)
        result = self._renderer.render(recipe, env)

        source = RenderEventSource(
            section_id=context.section_id,
            lane=context.lane,
            group_id=placement.target.id,
            template_id=placement.template_id,
            placement_index=context.placement_index,
        )

        return [self._layer_to_compiled_effect(layer, context, source) for layer in result.layers]

    def _build_environment(self, context: TemplateCompileContext) -> RenderEnvironment:
        """Build RenderEnvironment from compile context."""
        palette_colors: dict[str, str] = {}
        if context.palette and context.palette.colors:
            colors = context.palette.colors
            if len(colors) > 0:
                palette_colors["primary"] = colors[0]
            if len(colors) > 1:
                palette_colors["accent"] = colors[1]

        return RenderEnvironment(
            energy=context.intensity,
            density=context.intensity,
            palette_colors=palette_colors,
        )

    @staticmethod
    def _layer_to_compiled_effect(
        layer: RenderedLayer,
        context: TemplateCompileContext,
        source: RenderEventSource,
    ) -> CompiledEffect:
        """Convert a RenderedLayer into a CompiledEffect."""
        resolved = resolve_effect_type(source.template_id)
        params: dict[str, Any] = {
            **resolved.defaults,
            **dict(layer.resolved_params),
            "blend_mode": layer.blend_mode.value,
            "mix": layer.mix,
        }
        event = RenderEvent(
            event_id=f"recipe_{source.template_id}_{layer.layer_index}_{uuid.uuid4().hex[:8]}",
            start_ms=context.start_ms,
            end_ms=context.end_ms,
            effect_type=resolved.effect_type,
            parameters=params,
            palette=context.palette,
            intensity=context.intensity,
            transition_in=context.transition_in,
            transition_out=context.transition_out,
            source=source,
        )

        return CompiledEffect(
            event=event,
            visual_depth=layer.layer_depth,
        )
