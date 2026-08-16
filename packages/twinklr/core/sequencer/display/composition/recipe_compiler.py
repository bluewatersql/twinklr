"""RecipeCompiler — TemplateCompiler implementation for EffectRecipe rendering.

Bridges the RecipeRenderer (abstract recipe → resolved layers) with the
CompositionEngine's TemplateCompiler protocol (placement → CompiledEffects).
"""

from __future__ import annotations

from difflib import get_close_matches
from typing import Any
import uuid

from twinklr.core.sequencer.display.composition.models import CompiledEffect, TemplateCompileError
from twinklr.core.sequencer.display.composition.template_compiler import (
    TemplateCompileContext,
)
from twinklr.core.sequencer.display.effects.handlers import load_builtin_handlers
from twinklr.core.sequencer.display.effects.registry import HandlerRegistry
from twinklr.core.sequencer.display.models.render_event import (
    EffectSubstitution,
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
from twinklr.core.sequencer.vocabulary import BlendMode

RECIPE_BLEND_TO_LAYER_METHOD: dict[BlendMode, str] = {
    BlendMode.NORMAL: "Normal",
    BlendMode.ADD: "Max",
    BlendMode.SCREEN: "Normal",
    BlendMode.MASK: "1 reveals 2",
}


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
        handler_registry: HandlerRegistry | None = None,
    ) -> None:
        self._catalog = catalog
        self._renderer = renderer or RecipeRenderer()
        self._handler_registry = (
            handler_registry if handler_registry is not None else load_builtin_handlers()
        )

    @property
    def handler_registry(self) -> HandlerRegistry:
        """Registry used for admission validation and eventual dispatch."""
        return self._handler_registry

    def use_handler_registry(self, registry: HandlerRegistry) -> None:
        """Bind admission validation to the renderer's runtime registry."""
        self._handler_registry = registry

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
            placement_id=placement.placement_id,
            placement_index=context.placement_index,
        )

        # Validate every resolved type before constructing any RenderEvent. This
        # keeps recipe admission atomic: one bad layer cannot yield a partial plan.
        for layer in result.layers:
            effect_type, _, _ = self._resolve_layer_effect(layer, source)
            self._validate_effect_type(effect_type, source)

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

    # Placeholder effect_type values that require fallback to resolve_effect_type
    _PLACEHOLDER_EFFECT_TYPES = frozenset(
        {"ABSTRACT", "GEOMETRIC", "IMAGERY", "TEXTURE", "HYBRID", "ORGANIC", "PLACEHOLDER"}
    )

    @staticmethod
    def _layer_to_compiled_effect(
        layer: RenderedLayer,
        context: TemplateCompileContext,
        source: RenderEventSource,
    ) -> CompiledEffect:
        """Convert a RenderedLayer into a CompiledEffect.

        Uses the layer's own effect_type when it contains a real xLights
        effect name.  Falls back to resolve_effect_type() only when the
        layer still carries a placeholder value (pre-enrichment templates).
        """
        effect_type, base_params, substitution = RecipeCompiler._resolve_layer_effect(layer, source)

        params: dict[str, Any] = {
            **base_params,
            **dict(layer.resolved_params),
            "E_SLIDER_Mix": int(layer.mix * 100),
        }
        event = RenderEvent(
            event_id=f"recipe_{source.template_id}_{layer.layer_index}_{uuid.uuid4().hex[:8]}",
            start_ms=context.start_ms,
            end_ms=context.end_ms,
            effect_type=effect_type,
            parameters=params,
            palette=context.palette,
            intensity=context.intensity,
            transition_in=context.transition_in,
            transition_out=context.transition_out,
            effect_substitution=substitution,
            source=source,
        )
        xlights_blend = RECIPE_BLEND_TO_LAYER_METHOD.get(layer.blend_mode, "Normal")
        return CompiledEffect(
            event=event,
            visual_depth=layer.layer_depth,
            layer_blend_mode=xlights_blend,
        )

    @staticmethod
    def _resolve_layer_effect(
        layer: RenderedLayer,
        source: RenderEventSource,
    ) -> tuple[str, dict[str, Any], EffectSubstitution | None]:
        """Resolve the event type and preserve any placeholder substitution."""
        layer_effect = layer.effect_type
        if not layer_effect or layer_effect in RecipeCompiler._PLACEHOLDER_EFFECT_TYPES:
            resolved = resolve_effect_type(source.template_id)
            return (
                resolved.effect_type,
                resolved.defaults,
                EffectSubstitution(
                    requested_effect_type=layer_effect or "<empty>",
                    substituted_effect_type=resolved.effect_type,
                    reason="placeholder effect type resolved from template id",
                ),
            )
        return layer_effect, {}, None

    def _validate_effect_type(self, effect_type: str, source: RenderEventSource) -> None:
        """Reject a compiled recipe effect not supported by the runtime registry."""
        registered = self._handler_registry.registered_types
        if effect_type in registered:
            return

        closest = get_close_matches(effect_type, registered, n=3, cutoff=0.3)
        closest_text = ", ".join(closest) if closest else "none"
        raise TemplateCompileError(
            template_id=source.template_id,
            section_id=source.section_id,
            placement_id=source.placement_id or "",
            reason=(
                f"unregistered effect type '{effect_type}'; "
                f"closest registered types: {closest_text}"
            ),
        )
