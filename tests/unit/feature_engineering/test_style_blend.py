"""Tests for StyleBlend evaluation and StyleEvolution application."""

from __future__ import annotations

import pytest

from twinklr.core.feature_engineering.models.style import (
    ColorStyleProfile,
    LayeringStyleProfile,
    StyleBlend,
    StyleEvolution,
    StyleFingerprint,
    TimingStyleProfile,
    TransitionStyleProfile,
)
from twinklr.core.feature_engineering.style_transfer import (
    StyleBlendEvaluator,
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
    temperature_preference: float = 0.5,
    palette_complexity: float = 0.5,
) -> StyleFingerprint:
    return StyleFingerprint(
        creator_id="test_creator",
        recipe_preferences=recipe_preferences or {},
        transition_style=TransitionStyleProfile(
            preferred_gap_ms=100, overlap_tendency=0.3, variety_score=0.5
        ),
        color_tendencies=ColorStyleProfile(
            palette_complexity=palette_complexity,
            contrast_preference=0.5,
            temperature_preference=temperature_preference,
        ),
        timing_style=TimingStyleProfile(
            beat_alignment_strictness=0.7,
            density_preference=density_preference,
            section_change_aggression=0.5,
        ),
        layering_style=LayeringStyleProfile(
            mean_layers=mean_layers,
            max_layers=max_layers,
            blend_mode_preference="normal",
        ),
        corpus_sequence_count=10,
    )


def _make_recipe(
    *,
    recipe_id: str = "test_recipe",
    effect_type: str = "ColorWash",
    density: float = 0.5,
) -> EffectRecipe:
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
        layers=(
            RecipeLayer(
                layer_index=0,
                layer_name="Base",
                layer_depth=VisualDepth.BACKGROUND,
                effect_type=effect_type,
                blend_mode=BlendMode.NORMAL,
                mix=1.0,
                params={},
                motion=[MotionVerb.FADE],
                density=density,
                color_source=ColorSource.PALETTE_PRIMARY,
            ),
        ),
        provenance=RecipeProvenance(source="mined"),
    )


# ============================================================================
# StyleBlendEvaluator — blend two styles
# ============================================================================


def test_blend_pure_base() -> None:
    """blend_ratio=0.0 returns pure base style fingerprint."""
    base = _make_style(density_preference=0.3, mean_layers=1.0)
    accent = _make_style(density_preference=0.9, mean_layers=4.0)
    blend = StyleBlend(base_style=base, accent_style=accent, blend_ratio=0.0)
    evaluator = StyleBlendEvaluator()
    result = evaluator.evaluate(blend)
    assert result.timing_style.density_preference == pytest.approx(0.3)
    assert result.layering_style.mean_layers == pytest.approx(1.0)


def test_blend_pure_accent() -> None:
    """blend_ratio=1.0 returns pure accent style fingerprint."""
    base = _make_style(density_preference=0.3, mean_layers=1.0)
    accent = _make_style(density_preference=0.9, mean_layers=4.0)
    blend = StyleBlend(base_style=base, accent_style=accent, blend_ratio=1.0)
    evaluator = StyleBlendEvaluator()
    result = evaluator.evaluate(blend)
    assert result.timing_style.density_preference == pytest.approx(0.9)
    assert result.layering_style.mean_layers == pytest.approx(4.0)


def test_blend_50_50() -> None:
    """blend_ratio=0.5 averages base and accent."""
    base = _make_style(density_preference=0.2, mean_layers=1.0)
    accent = _make_style(density_preference=0.8, mean_layers=3.0)
    blend = StyleBlend(base_style=base, accent_style=accent, blend_ratio=0.5)
    evaluator = StyleBlendEvaluator()
    result = evaluator.evaluate(blend)
    assert result.timing_style.density_preference == pytest.approx(0.5)
    assert result.layering_style.mean_layers == pytest.approx(2.0)


def test_blend_no_accent_returns_base() -> None:
    """No accent style returns base unchanged."""
    base = _make_style(density_preference=0.4)
    blend = StyleBlend(base_style=base, accent_style=None, blend_ratio=0.5)
    evaluator = StyleBlendEvaluator()
    result = evaluator.evaluate(blend)
    assert result.timing_style.density_preference == pytest.approx(0.4)


# ============================================================================
# StyleEvolution — directional style adjustment
# ============================================================================


def test_evolution_more_complex() -> None:
    """more_complex increases density and mean_layers."""
    base = _make_style(density_preference=0.3, mean_layers=1.5)
    blend = StyleBlend(
        base_style=base,
        accent_style=None,
        blend_ratio=0.0,
        evolution_params=StyleEvolution(direction="more_complex", intensity=1.0),
    )
    evaluator = StyleBlendEvaluator()
    result = evaluator.evaluate(blend)
    assert result.timing_style.density_preference > 0.3
    assert result.layering_style.mean_layers > 1.5


def test_evolution_simpler() -> None:
    """simpler decreases density and mean_layers."""
    base = _make_style(density_preference=0.7, mean_layers=3.0)
    blend = StyleBlend(
        base_style=base,
        accent_style=None,
        blend_ratio=0.0,
        evolution_params=StyleEvolution(direction="simpler", intensity=1.0),
    )
    evaluator = StyleBlendEvaluator()
    result = evaluator.evaluate(blend)
    assert result.timing_style.density_preference < 0.7
    assert result.layering_style.mean_layers < 3.0


def test_evolution_warmer() -> None:
    """warmer increases temperature_preference."""
    base = _make_style(temperature_preference=0.3)
    blend = StyleBlend(
        base_style=base,
        accent_style=None,
        blend_ratio=0.0,
        evolution_params=StyleEvolution(direction="warmer", intensity=1.0),
    )
    evaluator = StyleBlendEvaluator()
    result = evaluator.evaluate(blend)
    assert result.color_tendencies.temperature_preference > 0.3


def test_evolution_cooler() -> None:
    """cooler decreases temperature_preference."""
    base = _make_style(temperature_preference=0.7)
    blend = StyleBlend(
        base_style=base,
        accent_style=None,
        blend_ratio=0.0,
        evolution_params=StyleEvolution(direction="cooler", intensity=1.0),
    )
    evaluator = StyleBlendEvaluator()
    result = evaluator.evaluate(blend)
    assert result.color_tendencies.temperature_preference < 0.7


def test_evolution_clamps_to_bounds() -> None:
    """Evolution values are clamped to 0.0-1.0."""
    base = _make_style(density_preference=0.95)
    blend = StyleBlend(
        base_style=base,
        accent_style=None,
        blend_ratio=0.0,
        evolution_params=StyleEvolution(direction="more_complex", intensity=1.0),
    )
    evaluator = StyleBlendEvaluator()
    result = evaluator.evaluate(blend)
    assert result.timing_style.density_preference <= 1.0


# ============================================================================
# Integration: StyleBlend + StyleWeightedRetrieval
# ============================================================================


def test_blend_used_for_retrieval() -> None:
    """StyleBlendEvaluator output can be used with StyleWeightedRetrieval."""
    base = _make_style(recipe_preferences={"colorwash": 0.9}, density_preference=0.5)
    accent = _make_style(recipe_preferences={"sparkles": 0.9}, density_preference=0.8)
    blend = StyleBlend(base_style=base, accent_style=accent, blend_ratio=0.5)
    evaluator = StyleBlendEvaluator()
    blended = evaluator.evaluate(blend)

    catalog = RecipeCatalog(recipes=[
        _make_recipe(recipe_id="r1", effect_type="ColorWash", density=0.5),
        _make_recipe(recipe_id="r2", effect_type="Sparkles", density=0.8),
    ])
    retrieval = StyleWeightedRetrieval()
    results = retrieval.rank(catalog, blended)
    assert len(results) == 2
    assert all(0.0 <= r.score <= 1.0 for r in results)
