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
from twinklr.core.feature_engineering.promotion import (
    EXCLUDED_FAMILIES,
    PROMOTION_RUN_DEFAULT_MIN_STABILITY,
    PROMOTION_RUN_DEFAULT_MIN_SUPPORT,
)
from twinklr.core.feature_engineering.propensity import PROPENSITY_MIN_SUPPORT
from twinklr.core.feature_engineering.taxonomy.target_roles import TARGET_ROLE_SCORE_CUTOFF

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


def _review_points(
    configured: int | float, reference: Sequence[int | float]
) -> tuple[int | float, ...]:
    """Return configured plus two nearby points, preserving the accepted defaults."""
    if configured in reference and len(set(reference)) == 3:
        return tuple(sorted(set(reference)))
    if isinstance(configured, int):
        lower: int | float = max(1, configured - 1)
        upper: int | float = configured + 1
        if lower == configured:
            upper = configured + 2
    else:
        lower = max(0.0, configured * 0.5)
        upper = min(1.0, configured * 1.5)
        if lower == configured:
            upper = min(1.0, configured + 0.05)
    return tuple(sorted({lower, configured, upper}))


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


def _cluster_cap_sensitivity(
    candidates: Sequence[MinedTemplate],
    memberships: Sequence[Sequence[str]],
    caps: Sequence[int],
    *,
    multi_layer_min_per_cluster: int,
) -> list[dict[str, int]]:
    """Evaluate cluster caps from the same pre-dedup population as promotion."""
    rows: list[dict[str, int]] = []
    for cap in caps:
        kept = len(
            _apply_cluster_cap(
                candidates,
                memberships,
                cap=cap,
                multi_layer_min_per_cluster=multi_layer_min_per_cluster,
            )
        )
        rows.append({"cap": cap, "would_keep": kept, "would_cap": len(candidates) - kept})
    return rows


def _apply_cluster_cap(
    candidates: Sequence[MinedTemplate],
    memberships: Sequence[Sequence[str]],
    *,
    cap: int,
    multi_layer_min_per_cluster: int,
) -> tuple[MinedTemplate, ...]:
    """Mirror promotion's deterministic cluster selection for review evidence."""
    by_id = {candidate.template_id: candidate for candidate in candidates}
    clustered_ids: set[str] = set()
    kept_ids: set[str] = set()
    for member_ids in memberships:
        members = [by_id[member_id] for member_id in member_ids if member_id in by_id]
        if not members:
            continue
        clustered_ids.update(member.template_id for member in members)
        ranked = sorted(members, key=lambda member: -member.support_count)
        selected = list(ranked[:cap])
        selected_multi = sum(member.layer_count >= 2 for member in selected)
        if selected_multi < multi_layer_min_per_cluster:
            already_selected = {member.template_id for member in selected}
            remaining_multi = sorted(
                (
                    member
                    for member in ranked
                    if member.layer_count >= 2 and member.template_id not in already_selected
                ),
                key=lambda member: (-member.layer_count, -member.support_count),
            )
            selected.extend(remaining_multi[: multi_layer_min_per_cluster - selected_multi])
        kept_ids.update(member.template_id for member in selected)
    return tuple(
        candidate
        for candidate in candidates
        if candidate.template_id not in clustered_ids or candidate.template_id in kept_ids
    )


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
    role_scores: Sequence[float] | None = None,
    propensity_pair_supports: Sequence[int] | None = None,
    cluster_memberships: Sequence[Sequence[str]] | None = None,
    mining_run_provenance: Mapping[str, object] | None = None,
) -> dict[str, object]:
    """Build a serialisable, non-mutating quality-gate review report.

    Propensity evidence must come from uncensored effect phrases, never the
    already-gated affinity index. Cluster-cap evidence likewise requires the
    emitted cluster membership catalog. Missing evidence fails closed.
    """
    if propensity_pair_supports is None:
        raise ValueError("Raw propensity pair-support evidence is required")
    if cluster_memberships is None:
        raise ValueError("Raw cluster-membership evidence is required")
    if role_scores is None:
        raise ValueError("Raw target-role score evidence is required")
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

    propensity_sensitivity = _sensitivity(
        propensity_pair_supports, _review_points(PROPENSITY_MIN_SUPPORT, (2, 3, 5))
    )
    propensity_review: dict[str, object] = {
        "min_support": {
            "configured": PROPENSITY_MIN_SUPPORT,
            "source": "uncensored effect/model pair support from effect phrases",
            "status": "available",
            "sensitivity": propensity_sensitivity,
        },
    }
    role_review: dict[str, object] = {
        "configured": TARGET_ROLE_SCORE_CUTOFF,
        "source": "unclamped pre-assignment target-role scores",
        "status": "available" if role_scores else "requires_current_top_role_score_artifacts",
        "sensitivity": _sensitivity(role_scores, (0.25, TARGET_ROLE_SCORE_CUTOFF, 0.45)),
    }
    support_sensitivity = _combined_gate_sensitivity(
        single_layer,
        field="support_count",
        thresholds=_review_points(configured_support, (2, 3, 5)),
        held_support=effective_support,
        held_stability=effective_stability,
    )
    stability_sensitivity = _combined_gate_sensitivity(
        single_layer,
        field="cross_pack_stability",
        thresholds=_review_points(configured_stability, (0.015, 0.05, 0.3)),
        held_support=effective_support,
        held_stability=effective_stability,
    )
    cluster_sensitivity = _cluster_cap_sensitivity(
        gate_passes,
        cluster_memberships,
        tuple(
            int(value)
            for value in _review_points(options.recipe_promotion_max_per_cluster, (1, 2, 3))
        ),
        multi_layer_min_per_cluster=options.recipe_promotion_multi_layer_min_per_cluster,
    )
    post_cluster = _apply_cluster_cap(
        gate_passes,
        cluster_memberships,
        cap=options.recipe_promotion_max_per_cluster,
        multi_layer_min_per_cluster=options.recipe_promotion_multi_layer_min_per_cluster,
    )
    family_sensitivity = _family_cap_sensitivity(
        post_cluster,
        tuple(
            int(value)
            for value in _review_points(options.recipe_promotion_max_per_family, (5, 10, 15))
        ),
    )
    direct_support_sensitivity = _combined_gate_sensitivity(
        single_layer,
        field="support_count",
        thresholds=_review_points(PROMOTION_RUN_DEFAULT_MIN_SUPPORT, (2, 3, 5)),
        held_support=PROMOTION_RUN_DEFAULT_MIN_SUPPORT,
        held_stability=PROMOTION_RUN_DEFAULT_MIN_STABILITY,
    )
    direct_stability_sensitivity = _combined_gate_sensitivity(
        single_layer,
        field="cross_pack_stability",
        thresholds=_review_points(PROMOTION_RUN_DEFAULT_MIN_STABILITY, (0.015, 0.05, 0.3)),
        held_support=PROMOTION_RUN_DEFAULT_MIN_SUPPORT,
        held_stability=PROMOTION_RUN_DEFAULT_MIN_STABILITY,
    )
    numeric_values = {
        "recipe_promotion_min_support": {
            "configured": configured_support,
            "status": "available",
            "sensitivity": support_sensitivity,
        },
        "recipe_promotion_min_stability": {
            "configured": configured_stability,
            "status": "available",
            "sensitivity": stability_sensitivity,
        },
        "promotion_run_default_min_support": {
            "configured": PROMOTION_RUN_DEFAULT_MIN_SUPPORT,
            "status": "available",
            "sensitivity": direct_support_sensitivity,
        },
        "promotion_run_default_min_stability": {
            "configured": PROMOTION_RUN_DEFAULT_MIN_STABILITY,
            "status": "available",
            "sensitivity": direct_stability_sensitivity,
        },
        "propensity_min_support": {
            "configured": PROPENSITY_MIN_SUPPORT,
            "status": "available",
            "sensitivity": propensity_sensitivity,
        },
        "target_role_score_cutoff": {
            "configured": TARGET_ROLE_SCORE_CUTOFF,
            "status": "available",
            "sensitivity": role_review["sensitivity"],
        },
        "recipe_promotion_max_per_family": {
            "configured": options.recipe_promotion_max_per_family,
            "status": "available",
            "sensitivity": family_sensitivity,
        },
        "recipe_promotion_max_per_cluster": {
            "configured": options.recipe_promotion_max_per_cluster,
            "status": "available",
            "sensitivity": cluster_sensitivity,
        },
    }

    return {
        "schema_version": "quality_gate_distribution_report_v2",
        "mining_run_provenance": dict(mining_run_provenance or {}),
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
            "pipeline_run_defaults": {
                "min_support": PROMOTION_RUN_DEFAULT_MIN_SUPPORT,
                "min_stability": PROMOTION_RUN_DEFAULT_MIN_STABILITY,
            },
            "configured_pipeline_values": {
                "min_support": configured_support,
                "min_stability": configured_stability,
            },
            "owner_action_required": "Resolve whether direct PromotionPipeline.run defaults should remain intentionally different from configured pipeline values.",
        },
        "threshold_review": {
            "numeric_values": numeric_values,
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
                "max_per_family_sensitivity": family_sensitivity,
                "max_per_family_equivalence": "Exact post-cluster-dedup population at the configured cluster cap.",
                "max_per_cluster": {
                    "configured": options.recipe_promotion_max_per_cluster,
                    "status": "available",
                    "sensitivity": cluster_sensitivity,
                },
            },
        },
    }
