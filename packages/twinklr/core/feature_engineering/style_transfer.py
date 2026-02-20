"""Style transfer — style-weighted recipe retrieval.

Re-ranks recipe catalogs using StyleFingerprint to surface recipes
that best match a creator's aesthetic preferences.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from twinklr.core.feature_engineering.models.style import StyleFingerprint
from twinklr.core.sequencer.templates.group.recipe import EffectRecipe
from twinklr.core.sequencer.templates.group.recipe_catalog import RecipeCatalog


@dataclass(frozen=True)
class ScoredRecipe:
    """A recipe with its style match score."""

    recipe: EffectRecipe
    score: float  # 0.0-1.0
    breakdown: dict[str, float] = field(default_factory=dict)


class StyleWeightedRetrieval:
    """Re-ranks recipe catalog using style fingerprint matching.

    Scoring dimensions (each 0-1, weighted equally by default):
    1. Effect family preference: Does the recipe's effect types match preferred families?
    2. Layering match: Does layer count match the style's layering preference?
    3. Density match: Does recipe density match timing_style.density_preference?
    4. Complexity match: Does recipe complexity match the style (via StyleMarkers)?

    All dimensions contribute equally to the final score (average).
    """

    def rank(
        self,
        catalog: RecipeCatalog,
        style: StyleFingerprint,
    ) -> list[ScoredRecipe]:
        """Rank all recipes in catalog by style match.

        Returns:
            List of ScoredRecipe sorted by score descending.
        """
        scored = []
        for recipe in catalog.recipes:
            total, breakdown = self._score_recipe(recipe, style)
            scored.append(ScoredRecipe(recipe=recipe, score=total, breakdown=breakdown))
        scored.sort(key=lambda s: s.score, reverse=True)
        return scored

    def top_k(
        self,
        catalog: RecipeCatalog,
        style: StyleFingerprint,
        k: int = 5,
    ) -> list[ScoredRecipe]:
        """Get top-k recipes by style match."""
        return self.rank(catalog, style)[:k]

    def _score_recipe(
        self,
        recipe: EffectRecipe,
        style: StyleFingerprint,
    ) -> tuple[float, dict[str, float]]:
        """Score a single recipe against a style fingerprint."""
        scores: dict[str, float] = {}

        scores["effect_family"] = self._score_effect_family(recipe, style)
        scores["layering"] = self._score_layering(recipe, style)
        scores["density"] = self._score_density(recipe, style)
        scores["complexity"] = self._score_complexity(recipe, style)

        total = sum(scores.values()) / len(scores) if scores else 0.0
        return total, scores

    def _score_effect_family(
        self, recipe: EffectRecipe, style: StyleFingerprint
    ) -> float:
        """Score based on effect family preference match."""
        if not style.recipe_preferences:
            return 0.5  # Neutral if no preferences

        matches: list[float] = []
        for layer in recipe.layers:
            effect_key = layer.effect_type.lower()
            best_match = 0.0
            for pref_key, pref_weight in style.recipe_preferences.items():
                if pref_key.lower() in effect_key or effect_key in pref_key.lower():
                    best_match = max(best_match, pref_weight)
            matches.append(best_match)
        return sum(matches) / len(matches) if matches else 0.5

    def _score_layering(self, recipe: EffectRecipe, style: StyleFingerprint) -> float:
        """Score based on layer count vs style preference."""
        recipe_layers = len(recipe.layers)
        preferred = style.layering_style.mean_layers
        if preferred <= 0:
            return 0.5
        diff = abs(recipe_layers - preferred)
        return max(0.0, 1.0 - (diff / max(preferred, 1.0)))

    def _score_density(self, recipe: EffectRecipe, style: StyleFingerprint) -> float:
        """Score based on average layer density vs style density preference."""
        if not recipe.layers:
            return 0.5
        avg_density = sum(layer.density for layer in recipe.layers) / len(recipe.layers)
        preferred = style.timing_style.density_preference
        diff = abs(avg_density - preferred)
        return max(0.0, 1.0 - diff)

    def _score_complexity(
        self, recipe: EffectRecipe, style: StyleFingerprint
    ) -> float:
        """Score based on recipe complexity vs style complexity."""
        if recipe.style_markers is None:
            return 0.5  # Neutral if no markers
        style_complexity = (
            style.layering_style.mean_layers / max(style.layering_style.max_layers, 1)
            + style.timing_style.density_preference
        ) / 2.0
        diff = abs(recipe.style_markers.complexity - style_complexity)
        return max(0.0, 1.0 - diff)
