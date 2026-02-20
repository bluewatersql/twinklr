"""Tests for motif-aware recipe compatibility scoring."""

from __future__ import annotations

from pydantic import ValidationError
import pytest

from twinklr.core.sequencer.templates.group.models.template import TimingHints
from twinklr.core.sequencer.templates.group.recipe import (
    ColorSource,
    EffectRecipe,
    MotifCompatibility,
    PaletteSpec,
    RecipeLayer,
    RecipeProvenance,
)
from twinklr.core.sequencer.vocabulary import (
    BlendMode,
    ColorMode,
    GroupTemplateType,
    GroupVisualIntent,
    MotionVerb,
    VisualDepth,
)


def _make_recipe(
    *,
    recipe_id: str = "test_recipe",
    motif_compatibility: list[MotifCompatibility] | None = None,
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
                effect_type="ColorWash",
                blend_mode=BlendMode.NORMAL,
                mix=1.0,
                params={},
                motion=[MotionVerb.FADE],
                density=0.5,
                color_source=ColorSource.PALETTE_PRIMARY,
            ),
        ),
        provenance=RecipeProvenance(source="mined"),
        motif_compatibility=motif_compatibility or [],
    )


def test_motif_compatibility_model() -> None:
    """MotifCompatibility stores motif_id, score, and reason."""
    mc = MotifCompatibility(motif_id="grid", score=0.85, reason="Uses grid-like patterns")
    assert mc.motif_id == "grid"
    assert mc.score == 0.85
    assert mc.reason == "Uses grid-like patterns"


def test_recipe_with_motif_compatibility() -> None:
    """EffectRecipe can hold motif_compatibility list."""
    motifs = [
        MotifCompatibility(motif_id="grid", score=0.9),
        MotifCompatibility(motif_id="wave_cascade", score=0.6),
    ]
    recipe = _make_recipe(motif_compatibility=motifs)
    assert len(recipe.motif_compatibility) == 2
    assert recipe.motif_compatibility[0].motif_id == "grid"
    assert recipe.motif_compatibility[1].score == 0.6


def test_recipe_without_motif_compatibility() -> None:
    """EffectRecipe defaults to empty motif_compatibility."""
    recipe = _make_recipe()
    assert recipe.motif_compatibility == []


def test_motif_compatibility_frozen() -> None:
    """MotifCompatibility is frozen."""
    mc = MotifCompatibility(motif_id="grid", score=0.9)
    with pytest.raises(ValidationError):
        mc.score = 0.5  # type: ignore[misc]


def test_motif_best_match() -> None:
    """Can find best motif match from compatibility list."""
    motifs = [
        MotifCompatibility(motif_id="grid", score=0.9),
        MotifCompatibility(motif_id="sparkle", score=0.3),
        MotifCompatibility(motif_id="wave", score=0.7),
    ]
    recipe = _make_recipe(motif_compatibility=motifs)
    best = max(recipe.motif_compatibility, key=lambda m: m.score)
    assert best.motif_id == "grid"


def test_motif_filter_by_threshold() -> None:
    """Can filter motifs by score threshold."""
    motifs = [
        MotifCompatibility(motif_id="grid", score=0.9),
        MotifCompatibility(motif_id="sparkle", score=0.3),
        MotifCompatibility(motif_id="wave", score=0.7),
    ]
    recipe = _make_recipe(motif_compatibility=motifs)
    strong = [m for m in recipe.motif_compatibility if m.score >= 0.5]
    assert len(strong) == 2
