"""Promotion Pipeline — MinedTemplate to curated EffectRecipe.

Orchestrates: family filter → quality gate → cluster dedup → recipe synthesis.
Converts high-quality mined templates into renderable EffectRecipes
with provenance tracking and quality reporting.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from twinklr.core.feature_engineering.models.motifs import MotifCatalog
from twinklr.core.feature_engineering.models.templates import MinedTemplate
from twinklr.core.feature_engineering.motif_annotator import MotifAnnotator
from twinklr.core.feature_engineering.recipe_synthesizer import RecipeSynthesizer
from twinklr.core.sequencer.templates.group.recipe import EffectRecipe

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
    ) -> None:
        self._synthesizer = RecipeSynthesizer()
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
    ) -> PromotionResult:
        """Run the promotion pipeline.

        Args:
            candidates: MinedTemplates to evaluate for promotion.
            min_support: Minimum support count to pass quality gate.
            min_stability: Minimum cross-pack stability to pass quality gate.
            clusters: Optional cluster dedup specs, each with
                cluster_id, member_ids, and keep_id.
            motif_catalog: Optional motif catalog for compatibility annotation.

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

        # Stage 1: Quality gate
        passed: list[MinedTemplate] = []
        rejected_count = 0
        for t in eligible:
            if t.support_count >= min_support and t.cross_pack_stability >= min_stability:
                passed.append(t)
            else:
                rejected_count += 1

        # Stage 2: Cluster dedup
        if clusters:
            passed = self._apply_cluster_dedup(passed, clusters)

        # Stage 3: Recipe synthesis + build source template map for motif annotation
        promoted: list[EffectRecipe] = []
        source_template_map: dict[str, list[str]] = {}
        for t in passed:
            recipe_id = f"synth_{t.effect_family}_{t.motion_class}_{t.template_id}"
            recipe = self._synthesizer.synthesize(t, recipe_id=recipe_id)
            promoted.append(recipe)
            source_ids = [t.template_id] + self._get_cluster_member_ids(t.template_id, clusters)
            source_template_map[recipe_id] = source_ids

        # Stage 4: Motif annotation
        motifs_annotated = 0
        if motif_catalog is not None:
            promoted = self._annotator.annotate(
                promoted, motif_catalog, source_template_map=source_template_map
            )
            motifs_annotated = sum(1 for r in promoted if r.motif_compatibility)

        report = {
            "total_candidates": len(candidates),
            "filtered_families": filtered_count,
            "passed_quality_gate": len(passed),
            "rejected_count": rejected_count,
            "promoted_count": len(promoted),
            "motifs_annotated": motifs_annotated,
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
