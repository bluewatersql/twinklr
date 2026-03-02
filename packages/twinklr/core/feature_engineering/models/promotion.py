"""Promotion pipeline report model.

``PromotionReport`` captures the full funnel metrics from recipe promotion,
persisted as ``promotion_report.json`` alongside the recipe catalog.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class PromotionReport(BaseModel):
    """Structured report of the recipe promotion pipeline run.

    Captures funnel counts at each stage, effective thresholds,
    and distribution breakdowns for downstream analysis.

    Args:
        schema_version: Report schema version identifier.
        total_candidates: Templates entering the pipeline.
        filtered_families: Templates rejected by family filter.
        eligible_count: Templates after family filter.
        passed_quality_gate: Templates passing support + stability gates.
        rejected_count: Templates failing quality gate.
        after_cluster_dedup: Templates remaining after cluster dedup.
        promoted_count: Final promoted recipe count.
        capped_count: Recipes removed by per-family cap.
        stack_promoted_count: Recipes synthesized from multi-layer stacks.
        effective_min_stability: Stability threshold actually applied.
        effective_min_support: Support threshold actually applied.
        adaptive_stability_used: Whether adaptive stability was active.
        family_distribution: Recipe count per effect family.
        lane_distribution: Recipe count per sequencer lane.
        avg_layers_per_recipe: Mean layer count across promoted recipes.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_version: str = "v1.0.0"
    total_candidates: int
    filtered_families: int
    eligible_count: int
    passed_quality_gate: int
    rejected_count: int
    after_cluster_dedup: int
    promoted_count: int
    capped_count: int = 0
    stack_promoted_count: int = 0
    effective_min_stability: float
    effective_min_support: int
    adaptive_stability_used: bool
    family_distribution: dict[str, int]
    lane_distribution: dict[str, int]
    avg_layers_per_recipe: float
