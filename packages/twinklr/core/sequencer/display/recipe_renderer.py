"""RecipeRenderer — renders EffectRecipe layers into concrete effect specs.

Takes an EffectRecipe and a RenderEnvironment and produces a list of
RenderedLayers with all dynamic parameters evaluated and color sources
resolved to concrete hex values.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from twinklr.core.sequencer.templates.group.recipe import (
    ColorSource,
    EffectRecipe,
    ParamValue,
    RecipeLayer,
)
from twinklr.core.sequencer.vocabulary import BlendMode, VisualDepth


@dataclass(frozen=True)
class RenderedLayer:
    """A single rendered layer with all values resolved."""

    layer_index: int
    layer_name: str
    layer_depth: VisualDepth
    effect_type: str
    blend_mode: BlendMode
    mix: float
    resolved_params: dict[str, Any]
    resolved_color: str
    density: float
    timing_offset_beats: float


@dataclass(frozen=True)
class RecipeRenderResult:
    """Result of rendering an EffectRecipe."""

    recipe_id: str
    layers: list[RenderedLayer]
    warnings: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class RenderEnvironment:
    """Runtime values for dynamic parameter evaluation."""

    energy: float = 0.5
    density: float = 0.5
    palette_colors: dict[str, str] = field(default_factory=dict)


class RecipeRenderer:
    """Renders EffectRecipe layers into concrete effect specifications."""

    def render(self, recipe: EffectRecipe, env: RenderEnvironment) -> RecipeRenderResult:
        """Render all layers of an EffectRecipe.

        Args:
            recipe: The EffectRecipe to render.
            env: Runtime environment with energy, density, and palette colors.

        Returns:
            RecipeRenderResult with resolved layers and any warnings.
        """
        rendered_layers: list[RenderedLayer] = []
        warnings: list[str] = []
        for layer in recipe.layers:
            try:
                rendered = self._render_layer(layer, env)
                rendered_layers.append(rendered)
            except Exception as e:
                warnings.append(f"Layer {layer.layer_index} ({layer.layer_name}): {e}")
        return RecipeRenderResult(
            recipe_id=recipe.recipe_id,
            layers=rendered_layers,
            warnings=warnings,
        )

    def _render_layer(self, layer: RecipeLayer, env: RenderEnvironment) -> RenderedLayer:
        """Render a single RecipeLayer into a RenderedLayer."""
        resolved_params: dict[str, Any] = {}
        for key, pv in layer.params.items():
            resolved_params[key] = self._evaluate_param(pv, env)

        resolved_color = self._resolve_color(layer.color_source, env)

        return RenderedLayer(
            layer_index=layer.layer_index,
            layer_name=layer.layer_name,
            layer_depth=layer.layer_depth,
            effect_type=layer.effect_type,
            blend_mode=layer.blend_mode,
            mix=layer.mix,
            resolved_params=resolved_params,
            resolved_color=resolved_color,
            density=layer.density,
            timing_offset_beats=layer.timing_offset_beats or 0.0,
        )

    def _evaluate_param(self, pv: ParamValue, env: RenderEnvironment) -> Any:
        """Evaluate a ParamValue — static passthrough or dynamic expression."""
        if pv.value is not None:
            return pv.value
        if pv.expr is not None:
            allowed_vars = {"energy": env.energy, "density": env.density}
            try:
                result = float(eval(pv.expr, {"__builtins__": {}}, allowed_vars))  # noqa: S307
            except Exception:
                return pv.min_val or 0.0
            if pv.min_val is not None:
                result = max(result, pv.min_val)
            if pv.max_val is not None:
                result = min(result, pv.max_val)
            return result
        return None

    def _resolve_color(self, color_source: str, env: RenderEnvironment) -> str:
        """Resolve a color source to a concrete hex color."""
        if color_source == ColorSource.PALETTE_PRIMARY:
            return env.palette_colors.get("primary", "#FFFFFF")
        if color_source == ColorSource.PALETTE_ACCENT:
            return env.palette_colors.get("accent", "#FFFFFF")
        if color_source == ColorSource.WHITE_ONLY:
            return "#FFFFFF"
        if color_source == ColorSource.EXPLICIT:
            return env.palette_colors.get("explicit", "#FFFFFF")
        return "#FFFFFF"
