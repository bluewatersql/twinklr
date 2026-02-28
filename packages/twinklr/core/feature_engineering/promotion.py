"""Promotion Pipeline — MinedTemplate to curated EffectRecipe.

Orchestrates: family filter → quality gate → cluster dedup → recipe synthesis
→ model affinity enrichment → motif annotation.

Converts high-quality mined templates into renderable EffectRecipes
with provenance tracking and quality reporting.
"""

from __future__ import annotations

import math
import statistics
from collections import defaultdict
from dataclasses import dataclass
from typing import Any

from twinklr.core.feature_engineering.models.motifs import MotifCatalog
from twinklr.core.feature_engineering.models.propensity import PropensityIndex
from twinklr.core.feature_engineering.models.templates import MinedTemplate
from twinklr.core.feature_engineering.motif_annotator import MotifAnnotator
from twinklr.core.feature_engineering.recipe_synthesizer import RecipeSynthesizer
from twinklr.core.sequencer.templates.group.recipe import EffectRecipe, ModelAffinity

# Families handled by dedicated pipelines or not renderable as group effects.
# MH/DMX → MovingHeadManager; servo/glediator → device-specific;
# state/duplicate → xLights utility effects with no visual output.
EXCLUDED_FAMILIES: frozenset[str] = frozenset(
    {
        "dmx",
        "moving_head",
        "servo",
        "glediator",
        "state",
        "duplicate",
    }
)


def _adaptive_stability(
    median_distinct_pack_count: float,
    *,
    lower_bound: float = 0.3,
    upper_bound: float = 0.9,
) -> float:
    """Compute effective min_stability threshold from corpus diversity.

    Uses a logarithmic scaling of the median distinct_pack_count to produce
    a threshold that is lower for sparse corpora and higher for diverse ones.

    The result is deterministic and clamped between ``lower_bound`` and
    ``upper_bound``.

    Args:
        median_distinct_pack_count: Median distinct_pack_count across candidates.
        lower_bound: Hard minimum for the returned threshold.
        upper_bound: Hard maximum for the returned threshold.

    Returns:
        Effective min_stability threshold.
    """
    # Scale: log2(1 + x) / log2(1 + 20) maps [0, 20+] → roughly [0, 1]
    # At pack_count=0 → 0, pack_count=4 → ~0.48, pack_count=10 → ~0.77, 20 → 1.0
    denominator = math.log2(1.0 + 20.0)
    raw = math.log2(1.0 + max(0.0, median_distinct_pack_count)) / denominator
    scaled = lower_bound + raw * (upper_bound - lower_bound)
    return max(lower_bound, min(upper_bound, scaled))


@dataclass(frozen=True)
class PromotionResult:
    """Result of running the promotion pipeline."""

    promoted_recipes: list[EffectRecipe]
    report: dict[str, Any]


class PromotionPipeline:
    """Promotes MinedTemplates to EffectRecipes through quality gates.

    Pipeline stages:
    1. Family filter: reject device/utility effect families
    2. Quality gate: filter by min_support and min_stability
    3. Cluster dedup: merge similar templates using provided clusters
    4. Recipe synthesis: convert surviving templates to EffectRecipes
    5. Motif annotation: cross-reference recipes with motif catalog (optional)
    """

    def __init__(
        self,
        *,
        excluded_families: frozenset[str] = EXCLUDED_FAMILIES,
        param_profiles: dict[str, dict[str, object]] | None = None,
    ) -> None:
        self._synthesizer = RecipeSynthesizer(param_profiles=param_profiles)
        self._annotator = MotifAnnotator()
        self._excluded_families = excluded_families

    def run(
        self,
        candidates: list[MinedTemplate],
        *,
        min_support: int = 5,
        min_stability: float = 0.3,
        clusters: list[dict[str, Any]] | None = None,
        motif_catalog: MotifCatalog | None = None,
        propensity_index: PropensityIndex | None = None,
        use_stack_synthesis: bool = False,
        adaptive_stability: bool = False,
    ) -> PromotionResult:
        """Run the promotion pipeline.

        Args:
            candidates: MinedTemplates to evaluate for promotion.
            min_support: Minimum support count to pass quality gate.
            min_stability: Minimum cross-pack stability to pass quality gate.
            clusters: Optional cluster dedup specs, each with
                cluster_id, member_ids, and keep_id.
            motif_catalog: Optional motif catalog for compatibility annotation.
            propensity_index: Optional propensity index for model affinity enrichment.
            use_stack_synthesis: Use stack-aware synthesis path (V2).
            adaptive_stability: When True, compute effective min_stability from
                corpus diversity rather than using the static value.

        Returns:
            PromotionResult with promoted recipes and a quality report.
        """
        # Stage 0: Family filter
        filtered_count = 0
        eligible: list[MinedTemplate] = []
        for t in candidates:
            if t.effect_family in self._excluded_families:
                filtered_count += 1
            else:
                eligible.append(t)

        # Stage 1: Quality gate (with optional adaptive stability)
        effective_stability = min_stability
        if adaptive_stability and eligible:
            pack_counts = [t.distinct_pack_count for t in eligible]
            median_pack = float(statistics.median(pack_counts))
            effective_stability = _adaptive_stability(median_pack)

        passed: list[MinedTemplate] = []
        rejected_count = 0
        for t in eligible:
            if t.support_count >= min_support and t.cross_pack_stability >= effective_stability:
                passed.append(t)
            else:
                rejected_count += 1

        # Stage 2: Cluster dedup
        if clusters:
            passed = self._apply_cluster_dedup(passed, clusters)

        # Stage 3: Recipe synthesis + build source template map for motif annotation
        promoted: list[EffectRecipe] = []
        source_template_map: dict[str, list[str]] = {}
        stack_promoted_count = 0
        for t in passed:
            recipe_id = f"synth_{t.effect_family}_{t.motion_class}_{t.template_id}"
            if use_stack_synthesis and t.stack_composition:
                recipe = self._synthesizer.synthesize_from_stack(t, recipe_id=recipe_id)
                stack_promoted_count += 1
            else:
                recipe = self._synthesizer.synthesize(t, recipe_id=recipe_id)
            promoted.append(recipe)
            source_ids = [t.template_id] + self._get_cluster_member_ids(t.template_id, clusters)
            source_template_map[recipe_id] = source_ids

        # Stage 4: Model affinity enrichment
        affinities_enriched = 0
        if propensity_index is not None:
            promoted, affinities_enriched = self._enrich_model_affinities(
                promoted, propensity_index
            )

        # Stage 5: Motif annotation
        motifs_annotated = 0
        if motif_catalog is not None:
            promoted = self._annotator.annotate(
                promoted, motif_catalog, source_template_map=source_template_map
            )
            motifs_annotated = sum(1 for r in promoted if r.motif_compatibility)

        report: dict[str, Any] = {
            "total_candidates": len(candidates),
            "filtered_families": filtered_count,
            "passed_quality_gate": len(passed),
            "rejected_count": rejected_count,
            "promoted_count": len(promoted),
            "affinities_enriched": affinities_enriched,
            "motifs_annotated": motifs_annotated,
            "stack_promoted_count": stack_promoted_count,
            "effective_min_stability": effective_stability,
        }

        return PromotionResult(promoted_recipes=promoted, report=report)

    def _get_cluster_member_ids(
        self,
        template_id: str,
        clusters: list[dict[str, Any]] | None,
    ) -> list[str]:
        """Get other member IDs from the cluster this template belongs to."""
        if not clusters:
            return []
        for cluster in clusters:
            keep_id = cluster.get("keep_id")
            member_ids = cluster.get("member_ids", [])
            if keep_id == template_id and len(member_ids) > 1:
                return [mid for mid in member_ids if mid != template_id]
        return []

    @staticmethod
    def _enrich_model_affinities(
        recipes: list[EffectRecipe],
        propensity: PropensityIndex,
    ) -> tuple[list[EffectRecipe], int]:
        """Enrich recipes with model affinity scores from PropensityIndex.

        For each recipe, look up its layers' effect families in the
        propensity index and aggregate affinities.

        Returns:
            Tuple of (enriched recipes, count of recipes that received affinities).
        """
        family_affinity: dict[str, list[tuple[str, float]]] = defaultdict(list)
        for aff in propensity.affinities:
            family_affinity[aff.effect_family].append((aff.model_type, aff.frequency))

        enriched: list[EffectRecipe] = []
        count = 0

        for recipe in recipes:
            model_scores: dict[str, list[float]] = defaultdict(list)
            for layer in recipe.layers:
                family = layer.effect_type.lower()
                family_normalized = family.replace(" ", "_")
                for lookup in (family, family_normalized):
                    if lookup in family_affinity:
                        for model_type, score in family_affinity[lookup]:
                            model_scores[model_type].append(score)
                        break

            if model_scores:
                affinities = [
                    ModelAffinity(
                        model_type=mt,
                        score=round(sum(scores) / len(scores), 4),
                    )
                    for mt, scores in sorted(model_scores.items())
                ]
                recipe = recipe.model_copy(update={"model_affinities": affinities})
                count += 1

            enriched.append(recipe)

        return enriched, count

    def _apply_cluster_dedup(
        self,
        templates: list[MinedTemplate],
        clusters: list[dict[str, Any]],
    ) -> list[MinedTemplate]:
        """Remove cluster duplicates, keeping only the designated template."""
        # Build set of template IDs to remove (cluster members that aren't the keeper)
        remove_ids: set[str] = set()
        for cluster in clusters:
            member_ids = cluster.get("member_ids", [])
            keep_id = cluster.get("keep_id")
            for mid in member_ids:
                if mid != keep_id:
                    remove_ids.add(mid)

        return [t for t in templates if t.template_id not in remove_ids]
