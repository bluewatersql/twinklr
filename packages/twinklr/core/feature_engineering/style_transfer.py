"""Style transfer — style-weighted recipe retrieval.

Re-ranks recipe catalogs using StyleFingerprint to surface recipes
that best match a creator's aesthetic preferences.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from twinklr.core.feature_engineering.models.style import (
    ColorStyleProfile,
    LayeringStyleProfile,
    StyleBlend,
    StyleEvolution,
    StyleFingerprint,
    TimingStyleProfile,
    TransitionStyleProfile,
)
from twinklr.core.sequencer.templates.group.recipe import EffectRecipe
from twinklr.core.sequencer.templates.group.recipe_catalog import RecipeCatalog

_PASCAL_RE = re.compile(r"(?<=[a-z0-9])(?=[A-Z])")


def _to_snake(name: str) -> str:
    """Normalise PascalCase or camelCase to snake_case, idempotent on snake_case."""
    return _PASCAL_RE.sub("_", name).lower()


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

    def _score_effect_family(self, recipe: EffectRecipe, style: StyleFingerprint) -> float:
        """Score based on effect family preference match.

        Both PascalCase effect_type values (e.g. ``SingleStrand``) and
        snake_case recipe_preferences keys (e.g. ``single_strand``) are
        normalised to snake_case before an **exact** comparison.
        """
        if not style.recipe_preferences:
            return 0.5  # Neutral if no preferences

        norm_prefs = {_to_snake(k): v for k, v in style.recipe_preferences.items()}

        matches: list[float] = []
        for layer in recipe.layers:
            effect_key = _to_snake(layer.effect_type)
            matches.append(norm_prefs.get(effect_key, 0.0))
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

    def _score_complexity(self, recipe: EffectRecipe, style: StyleFingerprint) -> float:
        """Score based on recipe complexity vs style complexity."""
        if recipe.style_markers is None:
            return 0.5  # Neutral if no markers
        style_complexity = (
            style.layering_style.mean_layers / max(style.layering_style.max_layers, 1)
            + style.timing_style.density_preference
        ) / 2.0
        diff = abs(recipe.style_markers.complexity - style_complexity)
        return max(0.0, 1.0 - diff)


class StyleBlendEvaluator:
    """Evaluates a StyleBlend into a single blended StyleFingerprint.

    Supports:
    - Base + accent style mixing (linear interpolation by blend_ratio)
    - Directional evolution (more_complex, simpler, warmer, cooler, etc.)

    The resulting StyleFingerprint can be fed to StyleWeightedRetrieval
    for recipe ranking.
    """

    # Evolution adjustment magnitude (applied at intensity=1.0)
    _EVOLUTION_DELTA = 0.3

    def evaluate(self, blend: StyleBlend) -> StyleFingerprint:
        """Evaluate a StyleBlend into a single StyleFingerprint.

        Args:
            blend: StyleBlend with base, optional accent, and optional evolution.

        Returns:
            Blended and optionally evolved StyleFingerprint.
        """
        base = blend.base_style

        if blend.accent_style is not None:
            blended = self._interpolate(base, blend.accent_style, blend.blend_ratio)
        else:
            blended = base

        if blend.evolution_params is not None:
            blended = self._apply_evolution(blended, blend.evolution_params)

        return blended

    def _interpolate(
        self,
        a: StyleFingerprint,
        b: StyleFingerprint,
        ratio: float,
    ) -> StyleFingerprint:
        """Linear interpolation between two fingerprints."""
        t = ratio  # 0 = pure a, 1 = pure b

        def lerp(va: float, vb: float) -> float:
            return va + t * (vb - va)

        # Merge recipe_preferences (union of keys)
        all_keys = set(a.recipe_preferences) | set(b.recipe_preferences)
        merged_prefs = {
            k: lerp(a.recipe_preferences.get(k, 0.0), b.recipe_preferences.get(k, 0.0))
            for k in all_keys
        }

        return StyleFingerprint(
            creator_id=f"{a.creator_id}+{b.creator_id}",
            recipe_preferences=merged_prefs,
            transition_style=TransitionStyleProfile(
                preferred_gap_ms=lerp(
                    a.transition_style.preferred_gap_ms,
                    b.transition_style.preferred_gap_ms,
                ),
                overlap_tendency=lerp(
                    a.transition_style.overlap_tendency,
                    b.transition_style.overlap_tendency,
                ),
                variety_score=lerp(
                    a.transition_style.variety_score,
                    b.transition_style.variety_score,
                ),
            ),
            color_tendencies=ColorStyleProfile(
                palette_complexity=lerp(
                    a.color_tendencies.palette_complexity,
                    b.color_tendencies.palette_complexity,
                ),
                contrast_preference=lerp(
                    a.color_tendencies.contrast_preference,
                    b.color_tendencies.contrast_preference,
                ),
                temperature_preference=lerp(
                    a.color_tendencies.temperature_preference,
                    b.color_tendencies.temperature_preference,
                ),
            ),
            timing_style=TimingStyleProfile(
                beat_alignment_strictness=lerp(
                    a.timing_style.beat_alignment_strictness,
                    b.timing_style.beat_alignment_strictness,
                ),
                density_preference=lerp(
                    a.timing_style.density_preference,
                    b.timing_style.density_preference,
                ),
                section_change_aggression=lerp(
                    a.timing_style.section_change_aggression,
                    b.timing_style.section_change_aggression,
                ),
            ),
            layering_style=LayeringStyleProfile(
                mean_layers=lerp(
                    a.layering_style.mean_layers,
                    b.layering_style.mean_layers,
                ),
                max_layers=max(a.layering_style.max_layers, b.layering_style.max_layers),
                blend_mode_preference=(
                    a.layering_style.blend_mode_preference
                    if t < 0.5
                    else b.layering_style.blend_mode_preference
                ),
            ),
            corpus_sequence_count=a.corpus_sequence_count + b.corpus_sequence_count,
        )

    def _apply_evolution(
        self,
        style: StyleFingerprint,
        evolution: StyleEvolution | None,
    ) -> StyleFingerprint:
        """Apply directional evolution to a fingerprint."""
        if not isinstance(evolution, StyleEvolution):
            return style

        delta = self._EVOLUTION_DELTA * evolution.intensity
        direction = evolution.direction

        # Start with current values
        density = style.timing_style.density_preference
        mean_layers = style.layering_style.mean_layers
        temperature = style.color_tendencies.temperature_preference
        palette_complexity = style.color_tendencies.palette_complexity
        aggression = style.timing_style.section_change_aggression

        if direction == "more_complex":
            density = min(1.0, density + delta)
            mean_layers = mean_layers + delta * 2
            palette_complexity = min(1.0, palette_complexity + delta * 0.5)
        elif direction == "simpler":
            density = max(0.0, density - delta)
            mean_layers = max(0.5, mean_layers - delta * 2)
            palette_complexity = max(0.0, palette_complexity - delta * 0.5)
        elif direction == "warmer":
            temperature = min(1.0, temperature + delta)
        elif direction == "cooler":
            temperature = max(0.0, temperature - delta)
        elif direction == "higher_energy":
            density = min(1.0, density + delta)
            aggression = min(1.0, aggression + delta)
        elif direction == "calmer":
            density = max(0.0, density - delta)
            aggression = max(0.0, aggression - delta)

        return StyleFingerprint(
            creator_id=style.creator_id,
            recipe_preferences=dict(style.recipe_preferences),
            transition_style=style.transition_style,
            color_tendencies=ColorStyleProfile(
                palette_complexity=palette_complexity,
                contrast_preference=style.color_tendencies.contrast_preference,
                temperature_preference=temperature,
            ),
            timing_style=TimingStyleProfile(
                beat_alignment_strictness=style.timing_style.beat_alignment_strictness,
                density_preference=density,
                section_change_aggression=aggression,
            ),
            layering_style=LayeringStyleProfile(
                mean_layers=mean_layers,
                max_layers=style.layering_style.max_layers,
                blend_mode_preference=style.layering_style.blend_mode_preference,
            ),
            corpus_sequence_count=style.corpus_sequence_count,
        )
