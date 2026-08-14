"""Owner-facing evidence for feature-engineering quality-gate review.

The feature-engineering pipeline decides which candidates pass promotion.  This
module deliberately does not participate in that decision: it reads the full
candidate set after a run and renders the distributions needed for an owner to
make a threshold decision with evidence rather than hand-tuned intuition.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterable, Mapping, Sequence

from twinklr.core.feature_engineering.config import FeatureEngineeringPipelineOptions
from twinklr.core.feature_engineering.models.templates import MinedTemplate
from twinklr.core.feature_engineering.promotion import EXCLUDED_FAMILIES

_SUPPORT_BUCKETS: tuple[tuple[str, int, int | None], ...] = (
    ("1", 1, 1),
    ("2", 2, 2),
    ("3-4", 3, 4),
    ("5-9", 5, 9),
    ("10+", 10, None),
)
_STABILITY_BUCKETS: tuple[tuple[str, float, float | None], ...] = (
    ("0", 0.0, 0.0),
    ("0-0.014", 0.0, 0.014999),
    ("0.015-0.049", 0.015, 0.049999),
    ("0.05-0.299", 0.05, 0.299999),
    ("0.3-0.599", 0.3, 0.599999),
    ("0.6-1.0", 0.6, 1.0),
)


def _bucket_counts(
    values: Iterable[int | float], buckets: Sequence[tuple[str, int | float, int | float | None]]
) -> dict[str, int]:
    """Count values into ordered, inclusive display buckets."""
    counts = {label: 0 for label, _, _ in buckets}
    for value in values:
        for label, lower, upper in buckets:
            if value >= lower and (upper is None or value <= upper):
                counts[label] += 1
                break
    return counts


def _sensitivity(
    values: Iterable[int | float], thresholds: Sequence[int | float]
) -> list[dict[str, int | float]]:
    """Return pass/fail counts for each prospective inclusive threshold."""
    materialized = tuple(values)
    return [
        {
            "threshold": threshold,
            "pass_count": sum(value >= threshold for value in materialized),
            "fail_count": sum(value < threshold for value in materialized),
        }
        for threshold in thresholds
    ]


def _combined_gate_sensitivity(
    candidates: Sequence[MinedTemplate],
    *,
    field: str,
    thresholds: Sequence[int | float],
    held_support: int,
    held_stability: float,
) -> list[dict[str, int | float]]:
    """Vary one gate while holding the other fixed on eligible single-layer rows."""
    rows: list[dict[str, int | float]] = []
    for threshold in thresholds:
        support = int(threshold) if field == "support_count" else held_support
        stability = float(threshold) if field == "cross_pack_stability" else held_stability
        passed = sum(
            candidate.support_count >= support and candidate.cross_pack_stability >= stability
            for candidate in candidates
        )
        rows.append(
            {
                "threshold": threshold,
                "pass_count": passed,
                "fail_count": len(candidates) - passed,
            }
        )
    return rows


def _family_cap_sensitivity(
    candidates: Sequence[MinedTemplate], caps: Sequence[int]
) -> list[dict[str, int]]:
    """Show the cap effect after the configured support/stability gate."""
    by_family = Counter(candidate.effect_family for candidate in candidates)
    return [
        {
            "cap": cap,
            "would_keep": sum(min(count, cap) for count in by_family.values()),
            "would_cap": sum(max(0, count - cap) for count in by_family.values()),
        }
        for cap in caps
    ]


def _effective_value(
    report: Mapping[str, object] | None, key: str, fallback: int | float
) -> int | float:
    """Read an applied value from a promotion report without trusting its shape."""
    if report is not None:
        value = report.get(key)
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            return value
    return fallback


def build_quality_gate_distribution_report(
    candidates: Sequence[MinedTemplate],
    *,
    options: FeatureEngineeringPipelineOptions,
    promotion_report: Mapping[str, object] | None,
    role_scores: Sequence[float] = (),
) -> dict[str, object]:
    """Build a serialisable, non-mutating quality-gate review report.

    ``MinedTemplate`` contains the inputs for promotion thresholds but not raw
    propensity pair observations. Propensity sensitivity is therefore marked
    unavailable rather than inferred from the censored emitted index. Current
    target-role artifacts retain the separate unclamped pre-assignment score.
    """
    support_counts = tuple(candidate.support_count for candidate in candidates)
    stability_scores = tuple(candidate.cross_pack_stability for candidate in candidates)
    pack_counts = tuple(candidate.distinct_pack_count for candidate in candidates)
    configured_support = options.recipe_promotion_min_support
    configured_stability = options.recipe_promotion_min_stability
    effective_support = int(
        _effective_value(promotion_report, "effective_min_support", configured_support)
    )
    effective_stability = float(
        _effective_value(promotion_report, "effective_min_stability", configured_stability)
    )
    effective_source = "promotion_report" if promotion_report is not None else "static_fallback"
    excluded = tuple(
        candidate for candidate in candidates if candidate.effect_family in EXCLUDED_FAMILIES
    )
    eligible = tuple(
        candidate for candidate in candidates if candidate.effect_family not in EXCLUDED_FAMILIES
    )
    single_layer = tuple(candidate for candidate in eligible if candidate.layer_count < 2)
    multi_layer = tuple(candidate for candidate in eligible if candidate.layer_count >= 2)
    single_layer_passes = tuple(
        candidate
        for candidate in single_layer
        if candidate.support_count >= effective_support
        and candidate.cross_pack_stability >= effective_stability
    )
    multi_layer_passes = tuple(
        candidate
        for candidate in multi_layer
        if candidate.support_count >= options.recipe_promotion_multi_layer_min_support
        and candidate.cross_pack_stability >= options.recipe_promotion_multi_layer_min_stability
    )
    gate_passes = (*single_layer_passes, *multi_layer_passes)

    propensity_review: dict[str, object] = {
        "min_support": {
            "configured": 3,
            "status": "unavailable_from_emitted_index",
            "sensitivity": [],
            "limitation": "The emitted affinity index is censored at the current support gate. Its affinity corpus_support values include only passing pairs, while anti-affinity corpus_support is family_total + model_total rather than pair support; neither is a valid raw 2/3/5 population.",
        },
        "anti_affinity_threshold": {
            "configured": 0.05,
            "status": "unwired_constant",
            "current_behavior": "PropensityMiner.mine emits anti-affinities only for zero co-occurrence and does not consult this constant.",
            "owner_action_required": "Resolve whether the constant should be removed as dead configuration or wired in through a separately approved behavior change.",
        },
    }
    role_review: dict[str, object] = {
        "configured": 0.35,
        "source": "unclamped pre-assignment target-role scores",
        "status": "available" if role_scores else "requires_current_top_role_score_artifacts",
        "sensitivity": _sensitivity(role_scores, (0.25, 0.35, 0.45)),
    }
    support_sensitivity = _combined_gate_sensitivity(
        single_layer,
        field="support_count",
        thresholds=(2, 3, 5),
        held_support=effective_support,
        held_stability=effective_stability,
    )
    stability_sensitivity = _combined_gate_sensitivity(
        single_layer,
        field="cross_pack_stability",
        thresholds=(0.015, 0.05, 0.3),
        held_support=effective_support,
        held_stability=effective_stability,
    )

    return {
        "schema_version": "quality_gate_distribution_report_v1",
        "candidate_count": len(candidates),
        "histograms": {
            "support_count": _bucket_counts(support_counts, _SUPPORT_BUCKETS),
            "cross_pack_stability": _bucket_counts(stability_scores, _STABILITY_BUCKETS),
            "distinct_pack_count": _bucket_counts(pack_counts, _SUPPORT_BUCKETS),
        },
        "candidate_population": {
            "all": len(candidates),
            "excluded_family": len(excluded),
            "eligible_single_layer": len(single_layer),
            "eligible_multi_layer": len(multi_layer),
            "exact_quality_gate_pass": len(gate_passes),
            "exact_quality_gate_fail_or_excluded": len(candidates) - len(gate_passes),
        },
        "recipe_promotion": {
            "static_configured": {
                "min_support": configured_support,
                "min_stability": configured_stability,
                "adaptive_stability": options.recipe_promotion_adaptive_stability,
                "multi_layer_min_support": options.recipe_promotion_multi_layer_min_support,
                "multi_layer_min_stability": options.recipe_promotion_multi_layer_min_stability,
            },
            "effective_applied": {
                "min_support": effective_support,
                "min_stability": effective_stability,
                "source": effective_source,
            },
            "exact_gate_breakdown": {
                "excluded_family_count": len(excluded),
                "single_layer_pass_count": len(single_layer_passes),
                "single_layer_fail_count": len(single_layer) - len(single_layer_passes),
                "multi_layer_pass_count": len(multi_layer_passes),
                "multi_layer_fail_count": len(multi_layer) - len(multi_layer_passes),
                "equivalence": "Matches PromotionPipeline stage 0 and stage 1; cluster dedup and caps occur later.",
            },
            "support_sensitivity": support_sensitivity,
            "stability_sensitivity": stability_sensitivity,
            "sensitivity_population": "eligible single-layer candidates; the other gate is held at its effective applied value",
        },
        "low_pack_ratio_risk": {
            "exact_gate_pass_count": len(gate_passes),
            "exact_gate_passes_with_one_pack": sum(
                candidate.distinct_pack_count == 1 for candidate in gate_passes
            ),
            "exact_gate_passes_with_two_or_fewer_packs": sum(
                candidate.distinct_pack_count <= 2 for candidate in gate_passes
            ),
        },
        "promotion_default_discrepancy": {
            "pipeline_run_defaults": {"min_support": 5, "min_stability": 0.3},
            "configured_pipeline_values": {
                "min_support": configured_support,
                "min_stability": configured_stability,
            },
            "owner_action_required": "Resolve whether direct PromotionPipeline.run defaults should remain intentionally different from configured pipeline values.",
        },
        "threshold_review": {
            "recipe_promotion": {
                "static_configured": {
                    "min_support": configured_support,
                    "min_stability": configured_stability,
                },
                "effective_applied": {
                    "min_support": effective_support,
                    "min_stability": effective_stability,
                    "source": effective_source,
                },
                "support_sensitivity": support_sensitivity,
                "stability_sensitivity": stability_sensitivity,
                "sensitivity_population": "eligible single-layer candidates with the other effective gate held constant",
            },
            "propensity": propensity_review,
            "target_role_score_cutoff": role_review,
            "recipe_promotion_caps": {
                "max_per_family": {"configured": options.recipe_promotion_max_per_family},
                "max_per_family_sensitivity": _family_cap_sensitivity(
                    gate_passes, (5, options.recipe_promotion_max_per_family, 15)
                ),
                "max_per_family_equivalence": "Upper bound before cluster dedup; exact family-cap impact requires the run's cluster catalog and dedup result.",
                "max_per_cluster": {
                    "configured": options.recipe_promotion_max_per_cluster,
                    "status": "unavailable_without_cluster_catalog",
                    "sensitivity": [],
                    "limitation": "Nearby cap values cannot be evaluated from templates alone because cluster membership and multi-layer minimum retention affect survivors.",
                },
            },
        },
    }
