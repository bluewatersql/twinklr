"""Tests for RecipeCatalog."""

from __future__ import annotations

from twinklr.core.sequencer.templates.group.models.template import (
    TimingHints,
)
from twinklr.core.sequencer.templates.group.recipe import (
    ColorSource,
    EffectRecipe,
    PaletteSpec,
    RecipeLayer,
    RecipeProvenance,
    StyleMarkers,
)
from twinklr.core.sequencer.templates.group.recipe_catalog import RecipeCatalog
from twinklr.core.sequencer.vocabulary import (
    BlendMode,
    ColorMode,
    EnergyTarget,
    GroupTemplateType,
    GroupVisualIntent,
    LaneKind,
    MotionVerb,
    VisualDepth,
)


def _make_recipe(
    *,
    recipe_id: str = "test_recipe",
    template_type: GroupTemplateType = GroupTemplateType.RHYTHM,
    tags: list[str] | None = None,
    source: str = "mined",
) -> EffectRecipe:
    return EffectRecipe(
        recipe_id=recipe_id,
        name=f"Test {recipe_id}",
        description="Test recipe",
        recipe_version="1.0.0",
        template_type=template_type,
        visual_intent=GroupVisualIntent.ABSTRACT,
        tags=tags or [],
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
                params={},
                motion=[MotionVerb.FADE],
                density=0.5,
                color_source=ColorSource.PALETTE_PRIMARY,
            ),
        ),
        provenance=RecipeProvenance(source=source),
        style_markers=StyleMarkers(complexity=0.33, energy_affinity=EnergyTarget.MED),
    )


def test_recipe_catalog_has_recipe() -> None:
    r = _make_recipe(recipe_id="r1")
    catalog = RecipeCatalog(recipes=[r])
    assert catalog.has_recipe("r1")
    assert not catalog.has_recipe("nonexistent")


def test_recipe_catalog_get_recipe() -> None:
    r = _make_recipe(recipe_id="r1")
    catalog = RecipeCatalog(recipes=[r])
    assert catalog.get_recipe("r1") is not None
    assert catalog.get_recipe("r1").recipe_id == "r1"
    assert catalog.get_recipe("nonexistent") is None


def test_recipe_catalog_list_by_lane() -> None:
    base = _make_recipe(recipe_id="base1", template_type=GroupTemplateType.BASE)
    rhythm = _make_recipe(recipe_id="rhythm1", template_type=GroupTemplateType.RHYTHM)
    accent = _make_recipe(recipe_id="accent1", template_type=GroupTemplateType.ACCENT)
    catalog = RecipeCatalog(recipes=[base, rhythm, accent])

    base_recipes = catalog.list_by_lane(LaneKind.BASE)
    assert len(base_recipes) == 1
    assert base_recipes[0].recipe_id == "base1"

    rhythm_recipes = catalog.list_by_lane(LaneKind.RHYTHM)
    assert len(rhythm_recipes) == 1

    accent_recipes = catalog.list_by_lane(LaneKind.ACCENT)
    assert len(accent_recipes) == 1


def test_recipe_catalog_merge() -> None:
    r1 = _make_recipe(recipe_id="builtin1", source="builtin")
    r2 = _make_recipe(recipe_id="mined1", source="mined")
    catalog = RecipeCatalog.merge([r1], [r2])
    assert len(catalog.recipes) == 2
    assert catalog.has_recipe("builtin1")
    assert catalog.has_recipe("mined1")


def test_recipe_catalog_merge_dedup() -> None:
    """If a promoted recipe has the same ID as a builtin, promoted wins."""
    builtin = _make_recipe(recipe_id="shared_id", source="builtin")
    promoted = _make_recipe(recipe_id="shared_id", source="mined")
    catalog = RecipeCatalog.merge([builtin], [promoted])
    assert len(catalog.recipes) == 1
    assert catalog.get_recipe("shared_id").provenance.source == "mined"


def test_recipe_catalog_empty() -> None:
    catalog = RecipeCatalog(recipes=[])
    assert not catalog.has_recipe("anything")
    assert catalog.get_recipe("anything") is None
    assert catalog.list_by_lane(LaneKind.BASE) == []


def test_recipe_catalog_recipe_count() -> None:
    recipes = [_make_recipe(recipe_id=f"r{i}") for i in range(5)]
    catalog = RecipeCatalog(recipes=recipes)
    assert len(catalog.recipes) == 5


