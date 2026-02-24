"""Tests for EffectRecipe model."""

from __future__ import annotations

from pydantic import ValidationError
import pytest

from twinklr.core.sequencer.templates.group.models import TimingHints
from twinklr.core.sequencer.templates.group.recipe import (
    ColorSource,
    EffectRecipe,
    PaletteSpec,
    ParamValue,
    RecipeLayer,
    RecipeProvenance,
    StyleMarkers,
)
from twinklr.core.sequencer.vocabulary import (
    BlendMode,
    ColorMode,
    EnergyTarget,
    GroupTemplateType,
    GroupVisualIntent,
    MotionVerb,
    VisualDepth,
)


def test_single_layer_recipe() -> None:
    recipe = EffectRecipe(
        recipe_id="candy_cane_stack_v1",
        name="Candy Cane Stack",
        description="Red/white bars with sparkle overlay",
        recipe_version="1.0.0",
        template_type=GroupTemplateType.BASE,
        visual_intent=GroupVisualIntent.ABSTRACT,
        tags=["candy_cane", "christmas", "classic"],
        timing=TimingHints(bars_min=4, bars_max=64),
        palette_spec=PaletteSpec(mode=ColorMode.DICHROME, palette_roles=["primary", "accent"]),
        layers=(
            RecipeLayer(
                layer_index=0,
                layer_name="Base",
                layer_depth=VisualDepth.BACKGROUND,
                effect_type="ColorWash",
                blend_mode=BlendMode.NORMAL,
                mix=1.0,
                params={"Direction": ParamValue(value="Vertical"), "Speed": ParamValue(value=0)},
                motion=[MotionVerb.FADE],
                density=0.8,
                color_source=ColorSource.PALETTE_PRIMARY,
            ),
        ),
        provenance=RecipeProvenance(source="builtin"),
        style_markers=StyleMarkers(complexity=0.33, energy_affinity=EnergyTarget.LOW),
    )
    assert recipe.recipe_id == "candy_cane_stack_v1"
    assert len(recipe.layers) == 1


def test_multi_layer_recipe_candy_cane() -> None:
    recipe = EffectRecipe(
        recipe_id="candy_cane_stack_v1",
        name="Candy Cane Stack",
        description="Multi-layer candy cane with sparkle",
        recipe_version="1.0.0",
        template_type=GroupTemplateType.BASE,
        visual_intent=GroupVisualIntent.ABSTRACT,
        tags=["candy_cane"],
        timing=TimingHints(bars_min=4, bars_max=64),
        palette_spec=PaletteSpec(mode=ColorMode.DICHROME, palette_roles=["primary", "accent"]),
        layers=(
            RecipeLayer(
                layer_index=0,
                layer_name="Base",
                layer_depth=VisualDepth.BACKGROUND,
                effect_type="ColorWash",
                blend_mode=BlendMode.NORMAL,
                mix=1.0,
                params={},
                motion=[MotionVerb.FADE],
                density=0.8,
                color_source=ColorSource.PALETTE_PRIMARY,
            ),
            RecipeLayer(
                layer_index=1,
                layer_name="Pattern",
                layer_depth=VisualDepth.MIDGROUND,
                effect_type="Bars",
                blend_mode=BlendMode.ADD,
                mix=0.7,
                params={"BarCount": ParamValue(value=8), "Direction": ParamValue(value="Diagonal")},
                motion=[MotionVerb.SWEEP],
                density=0.6,
                color_source=ColorSource.PALETTE_PRIMARY,
            ),
            RecipeLayer(
                layer_index=2,
                layer_name="Accents",
                layer_depth=VisualDepth.FOREGROUND,
                effect_type="Sparkle",
                blend_mode=BlendMode.SCREEN,
                mix=0.45,
                params={"Density": ParamValue(value=30), "Size": ParamValue(value=2)},
                motion=[MotionVerb.SPARKLE],
                density=0.3,
                color_source=ColorSource.WHITE_ONLY,
            ),
        ),
        provenance=RecipeProvenance(source="builtin"),
        style_markers=StyleMarkers(complexity=1.0, energy_affinity=EnergyTarget.LOW),
    )
    assert len(recipe.layers) == 3
    assert recipe.layers[1].blend_mode == BlendMode.ADD
    assert recipe.layers[2].color_source == ColorSource.WHITE_ONLY


def test_dynamic_param_value() -> None:
    p = ParamValue(expr="energy * 0.8", min_val=10, max_val=90)
    assert p.expr is not None
    assert p.value is None


def test_recipe_provenance_mined() -> None:
    p = RecipeProvenance(
        source="mined",
        curator_notes="Merged from two similar patterns",
    )
    assert p.source == "mined"
    assert p.curator_notes == "Merged from two similar patterns"


def test_style_markers() -> None:
    m = StyleMarkers(
        complexity=0.6,
        energy_affinity=EnergyTarget.HIGH,
    )
    assert m.complexity == 0.6
    assert m.energy_affinity == EnergyTarget.HIGH


def test_recipe_is_frozen() -> None:
    recipe = EffectRecipe(
        recipe_id="test",
        name="Test",
        description="Test recipe",
        recipe_version="1.0.0",
        template_type=GroupTemplateType.BASE,
        visual_intent=GroupVisualIntent.ABSTRACT,
        tags=[],
        timing=TimingHints(),
        palette_spec=PaletteSpec(mode=ColorMode.MONOCHROME, palette_roles=["primary"]),
        layers=(
            RecipeLayer(
                layer_index=0,
                layer_name="Base",
                layer_depth=VisualDepth.BACKGROUND,
                effect_type="On",
                blend_mode=BlendMode.NORMAL,
                mix=1.0,
                params={},
                motion=[],
                density=0.5,
                color_source=ColorSource.PALETTE_PRIMARY,
            ),
        ),
        provenance=RecipeProvenance(source="builtin"),
        style_markers=StyleMarkers(complexity=0.33, energy_affinity=EnergyTarget.LOW),
    )
    with pytest.raises(ValidationError):
        recipe.name = "Changed"  # type: ignore[misc]


def test_recipe_serialization_roundtrip() -> None:
    recipe = EffectRecipe(
        recipe_id="test_rt",
        name="Roundtrip Test",
        description="Roundtrip test recipe",
        recipe_version="1.0.0",
        template_type=GroupTemplateType.RHYTHM,
        visual_intent=GroupVisualIntent.ABSTRACT,
        tags=["test"],
        timing=TimingHints(bars_min=2, bars_max=8),
        palette_spec=PaletteSpec(mode=ColorMode.DICHROME, palette_roles=["primary", "accent"]),
        layers=(
            RecipeLayer(
                layer_index=0,
                layer_name="Base",
                layer_depth=VisualDepth.BACKGROUND,
                effect_type="ColorWash",
                blend_mode=BlendMode.NORMAL,
                mix=1.0,
                params={"Speed": ParamValue(value=5)},
                motion=[MotionVerb.FADE],
                density=0.7,
                color_source=ColorSource.PALETTE_PRIMARY,
            ),
        ),
        provenance=RecipeProvenance(source="builtin"),
        style_markers=StyleMarkers(complexity=0.3, energy_affinity=EnergyTarget.MED),
    )
    data = recipe.model_dump()
    restored = EffectRecipe.model_validate(data)
    assert restored == recipe
