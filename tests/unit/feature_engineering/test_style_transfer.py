"""Tests for style-weighted recipe retrieval."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from twinklr.core.sequencer.templates.group.recipe import StyleMarkers

from twinklr.core.feature_engineering.models.style import (
    ColorStyleProfile,
    LayeringStyleProfile,
    StyleFingerprint,
    TimingStyleProfile,
    TransitionStyleProfile,
)
from twinklr.core.feature_engineering.style_transfer import (
    ScoredRecipe,
    StyleWeightedRetrieval,
)
from twinklr.core.sequencer.templates.group.models.template import TimingHints
from twinklr.core.sequencer.templates.group.recipe import (
    ColorSource,
    EffectRecipe,
    PaletteSpec,
    RecipeLayer,
    RecipeProvenance,
)
from twinklr.core.sequencer.templates.group.recipe_catalog import RecipeCatalog
from twinklr.core.sequencer.vocabulary import (
    BlendMode,
    ColorMode,
    GroupTemplateType,
    GroupVisualIntent,
    MotionVerb,
    VisualDepth,
)


def _make_style(
    *,
    recipe_preferences: dict[str, float] | None = None,
    density_preference: float = 0.5,
    mean_layers: float = 2.0,
    max_layers: int = 4,
) -> StyleFingerprint:
    return StyleFingerprint(
        creator_id="test_creator",
        recipe_preferences=recipe_preferences or {},
        transition_style=TransitionStyleProfile(
            preferred_gap_ms=100, overlap_tendency=0.3, variety_score=0.5
        ),
        color_tendencies=ColorStyleProfile(
            palette_complexity=0.5, contrast_preference=0.5, temperature_preference=0.5
        ),
        timing_style=TimingStyleProfile(
            beat_alignment_strictness=0.7,
            density_preference=density_preference,
            section_change_aggression=0.5,
        ),
        layering_style=LayeringStyleProfile(
            mean_layers=mean_layers, max_layers=max_layers, blend_mode_preference="normal"
        ),
        corpus_sequence_count=10,
    )


def _make_recipe(
    *,
    recipe_id: str = "test_recipe",
    effect_type: str = "ColorWash",
    density: float = 0.5,
    num_layers: int = 1,
    style_markers: StyleMarkers | None = None,
) -> EffectRecipe:
    layers = tuple(
        RecipeLayer(
            layer_index=i,
            layer_name=f"Layer{i}",
            layer_depth=VisualDepth.BACKGROUND,
            effect_type=effect_type,
            blend_mode=BlendMode.NORMAL,
            mix=1.0,
            params={},
            motion=[MotionVerb.FADE],
            density=density,
            color_source=ColorSource.PALETTE_PRIMARY,
        )
        for i in range(num_layers)
    )
    return EffectRecipe(
        recipe_id=recipe_id,
        name=f"Test {recipe_id}",
        description="Test recipe",
        recipe_version="1.0.0",
        template_type=GroupTemplateType.RHYTHM,
        visual_intent=GroupVisualIntent.ABSTRACT,
        tags=[],
        timing=TimingHints(bars_min=2, bars_max=8),
        palette_spec=PaletteSpec(mode=ColorMode.DICHROME, palette_roles=["primary", "accent"]),
        layers=layers,
        provenance=RecipeProvenance(source="mined"),
        style_markers=style_markers,
    )


class TestStyleWeightedRetrieval:
    """Tests for StyleWeightedRetrieval."""

    def test_rank_returns_all_recipes(self) -> None:
        """All recipes in the catalog should be returned with scores."""
        recipes = [_make_recipe(recipe_id=f"r{i}") for i in range(3)]
        catalog = RecipeCatalog(recipes=recipes)
        style = _make_style()
        retrieval = StyleWeightedRetrieval()

        result = retrieval.rank(catalog, style)

        assert len(result) == 3
        assert all(isinstance(sr, ScoredRecipe) for sr in result)

    def test_rank_sorted_by_score(self) -> None:
        """Results should be sorted descending by score."""
        recipes = [_make_recipe(recipe_id=f"r{i}") for i in range(5)]
        catalog = RecipeCatalog(recipes=recipes)
        style = _make_style()
        retrieval = StyleWeightedRetrieval()

        result = retrieval.rank(catalog, style)

        scores = [sr.score for sr in result]
        assert scores == sorted(scores, reverse=True)

    def test_top_k_limits_results(self) -> None:
        """top_k should return at most k results."""
        recipes = [_make_recipe(recipe_id=f"r{i}") for i in range(5)]
        catalog = RecipeCatalog(recipes=recipes)
        style = _make_style()
        retrieval = StyleWeightedRetrieval()

        result = retrieval.top_k(catalog, style, k=2)

        assert len(result) == 2

    def test_effect_family_preference_boosts_match(self) -> None:
        """Recipe matching a preferred effect family should score higher on that dimension."""
        preferred = _make_recipe(recipe_id="preferred", effect_type="Sparkle")
        other = _make_recipe(recipe_id="other", effect_type="ColorWash")
        catalog = RecipeCatalog(recipes=[preferred, other])
        style = _make_style(recipe_preferences={"sparkle": 0.9})
        retrieval = StyleWeightedRetrieval()

        result = retrieval.rank(catalog, style)
        scored_by_id = {sr.recipe.recipe_id: sr for sr in result}

        assert (
            scored_by_id["preferred"].breakdown["effect_family"]
            > scored_by_id["other"].breakdown["effect_family"]
        )

    def test_layering_match_scoring(self) -> None:
        """Recipe with layer count matching style preference should score higher."""
        good_match = _make_recipe(recipe_id="match", num_layers=2)
        bad_match = _make_recipe(recipe_id="mismatch", num_layers=4)
        catalog = RecipeCatalog(recipes=[good_match, bad_match])
        style = _make_style(mean_layers=2.0)
        retrieval = StyleWeightedRetrieval()

        result = retrieval.rank(catalog, style)
        scored_by_id = {sr.recipe.recipe_id: sr for sr in result}

        assert (
            scored_by_id["match"].breakdown["layering"]
            > scored_by_id["mismatch"].breakdown["layering"]
        )

    def test_density_match_scoring(self) -> None:
        """Recipe density close to style preference should score higher."""
        good = _make_recipe(recipe_id="good", density=0.7)
        bad = _make_recipe(recipe_id="bad", density=0.1)
        catalog = RecipeCatalog(recipes=[good, bad])
        style = _make_style(density_preference=0.7)
        retrieval = StyleWeightedRetrieval()

        result = retrieval.rank(catalog, style)
        scored_by_id = {sr.recipe.recipe_id: sr for sr in result}

        assert scored_by_id["good"].breakdown["density"] > scored_by_id["bad"].breakdown["density"]

    def test_score_breakdown_has_all_dimensions(self) -> None:
        """Breakdown dict should have all 4 scoring dimension keys."""
        catalog = RecipeCatalog(recipes=[_make_recipe()])
        style = _make_style()
        retrieval = StyleWeightedRetrieval()

        result = retrieval.rank(catalog, style)

        assert len(result) == 1
        expected_keys = {"effect_family", "layering", "density", "complexity"}
        assert set(result[0].breakdown.keys()) == expected_keys

    def test_empty_catalog_returns_empty(self) -> None:
        """Empty catalog should return empty list."""
        catalog = RecipeCatalog(recipes=[])
        style = _make_style()
        retrieval = StyleWeightedRetrieval()

        result = retrieval.rank(catalog, style)

        assert result == []

    def test_neutral_scores_without_preferences(self) -> None:
        """No recipe_preferences should give neutral 0.5 for effect_family."""
        catalog = RecipeCatalog(recipes=[_make_recipe()])
        style = _make_style(recipe_preferences={})
        retrieval = StyleWeightedRetrieval()

        result = retrieval.rank(catalog, style)

        assert result[0].breakdown["effect_family"] == 0.5
