"""Builtin GroupPlanTemplate to EffectRecipe converter.

Converts existing builtin templates to the EffectRecipe format for
unified recipe-based rendering and catalog management.
"""

from __future__ import annotations

from twinklr.core.sequencer.templates.group.models.template import (
    GroupPlanTemplate,
    LayerRecipe,
)
from twinklr.core.sequencer.templates.group.recipe import (
    ColorSource,
    EffectRecipe,
    PaletteSpec,
    RecipeLayer,
    RecipeProvenance,
    StyleMarkers,
)
from twinklr.core.sequencer.vocabulary import BlendMode, ColorMode, EnergyTarget, GroupTemplateType

# Map ColorMode to a default palette_roles list
_COLOR_MODE_ROLES: dict[ColorMode, list[str]] = {
    ColorMode.MONOCHROME: ["primary"],
    ColorMode.DICHROME: ["primary", "accent"],
    ColorMode.TRIAD: ["primary", "accent", "tertiary"],
    ColorMode.ANALOGOUS: ["primary", "accent"],
    ColorMode.FULL_SPECTRUM: ["primary"],
}

# Map ColorMode to a default ColorSource
_COLOR_MODE_SOURCE: dict[ColorMode, str] = {
    ColorMode.MONOCHROME: ColorSource.PALETTE_PRIMARY,
    ColorMode.DICHROME: ColorSource.PALETTE_PRIMARY,
    ColorMode.TRIAD: ColorSource.PALETTE_PRIMARY,
    ColorMode.ANALOGOUS: ColorSource.PALETTE_PRIMARY,
    ColorMode.FULL_SPECTRUM: ColorSource.PALETTE_PRIMARY,
}


def _convert_layer(index: int, layer: LayerRecipe) -> RecipeLayer:
    """Convert a LayerRecipe to a RecipeLayer."""
    # First layer gets NORMAL blend, subsequent layers get ADD
    blend_mode = BlendMode.NORMAL if index == 0 else BlendMode.ADD

    # Map color_mode to color_source
    color_source = _COLOR_MODE_SOURCE.get(layer.color_mode, ColorSource.PALETTE_PRIMARY)

    # Use motifs as layer_name hint, or default from depth
    layer_name = layer.motifs[0].capitalize() if layer.motifs else layer.layer.value.capitalize()

    return RecipeLayer(
        layer_index=index,
        layer_name=layer_name,
        layer_depth=layer.layer,
        effect_type=layer.visual_intent.value,
        blend_mode=blend_mode,
        mix=1.0 if index == 0 else 0.7,
        params={},
        motion=list(layer.motion),
        density=layer.density,
        color_source=color_source,
    )


def _derive_palette_spec(layers: list[LayerRecipe]) -> PaletteSpec:
    """Derive a PaletteSpec from the template's layer recipes."""
    # Use the most complex color mode found across layers
    modes = [layer.color_mode for layer in layers]
    # Pick the "broadest" mode
    mode_priority = [
        ColorMode.FULL_SPECTRUM,
        ColorMode.ANALOGOUS,
        ColorMode.TRIAD,
        ColorMode.DICHROME,
        ColorMode.MONOCHROME,
    ]
    best_mode = ColorMode.MONOCHROME
    for m in mode_priority:
        if m in modes:
            best_mode = m
            break

    roles = _COLOR_MODE_ROLES.get(best_mode, ["primary"])
    return PaletteSpec(mode=best_mode, palette_roles=roles)


_TYPE_ENERGY_MAP: dict[GroupTemplateType, EnergyTarget] = {
    GroupTemplateType.BASE: EnergyTarget.LOW,
    GroupTemplateType.RHYTHM: EnergyTarget.MED,
    GroupTemplateType.ACCENT: EnergyTarget.HIGH,
    GroupTemplateType.TRANSITION: EnergyTarget.MED,
    GroupTemplateType.SPECIAL: EnergyTarget.HIGH,
}


def _compute_style_markers(template_type: GroupTemplateType, layer_count: int) -> StyleMarkers:
    """Compute style markers from template characteristics."""
    complexity = min(layer_count / 3.0, 1.0)
    energy = _TYPE_ENERGY_MAP.get(template_type, EnergyTarget.MED)
    return StyleMarkers(complexity=complexity, energy_affinity=energy)


def convert_builtin_to_recipe(template: GroupPlanTemplate) -> EffectRecipe:
    """Convert a builtin GroupPlanTemplate to an EffectRecipe.

    Args:
        template: The builtin template to convert.

    Returns:
        An EffectRecipe wrapping the template's layers and metadata.
    """
    layers = tuple(_convert_layer(i, layer) for i, layer in enumerate(template.layer_recipe))

    palette_spec = _derive_palette_spec(template.layer_recipe)
    style_markers = _compute_style_markers(template.template_type, len(layers))

    return EffectRecipe(
        recipe_id=template.template_id,
        name=template.name,
        description=template.description,
        recipe_version=template.template_version,
        template_type=template.template_type,
        visual_intent=template.visual_intent,
        tags=list(template.tags),
        timing=template.timing,
        palette_spec=palette_spec,
        layers=layers,
        provenance=RecipeProvenance(source="builtin"),
        style_markers=style_markers,
    )
