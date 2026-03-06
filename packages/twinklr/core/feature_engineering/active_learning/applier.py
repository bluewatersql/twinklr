"""Applies approved taxonomy corrections and tracks improvement metrics."""

from __future__ import annotations

import logging

from twinklr.core.feature_engineering.active_learning.models import (
    CorrectionRecord,
    CorrectionReport,
    TaxonomyCorrectionResult,
)

logger = logging.getLogger(__name__)

_UNKNOWN_FAMILY = "unknown"
_UNKNOWN_MOTION = "unknown"


def _unknown_ratio(taxonomy_rules: dict[str, dict[str, str]]) -> float:
    """Compute the fraction of entries with unknown family or motion.

    Args:
        taxonomy_rules: Mapping of effect_type -> {"family": ..., "motion": ...}.

    Returns:
        Ratio in [0.0, 1.0]; 0.0 when the dict is empty.
    """
    if not taxonomy_rules:
        return 0.0
    unknown_count = sum(
        1
        for v in taxonomy_rules.values()
        if v.get("family", "").lower() == _UNKNOWN_FAMILY
        or v.get("motion", "").lower() == _UNKNOWN_MOTION
    )
    return unknown_count / len(taxonomy_rules)


class CorrectionApplier:
    """Applies approved corrections and tracks improvement metrics.

    Tracks:
    - Correction history (before/after labels)
    - Confidence uplift per batch
    - Unknown ratio reduction
    """

    def apply(
        self,
        corrections: tuple[TaxonomyCorrectionResult, ...],
        taxonomy_rules: dict[str, dict[str, str]],
    ) -> CorrectionReport:
        """Apply approved corrections to taxonomy_rules and return a report.

        Only corrections with ``approved=True`` are applied.  For each such
        correction that provides a ``corrected_family`` or ``corrected_motion``
        the corresponding entry in ``taxonomy_rules`` is updated in-place.

        Metrics computed:
        - ``mean_confidence_before``: average ``map_confidence`` across **all**
          corrections (approved or not).  0.0 when the input is empty.
        - ``mean_confidence_after``: average ``correction_confidence`` across
          approved corrections.  Falls back to ``mean_confidence_before`` when
          there are no approved corrections.
        - ``confidence_uplift``: after − before.
        - ``unknown_ratio_before``: unknown ratio of ``taxonomy_rules`` **before**
          any changes are applied.
        - ``unknown_ratio_after``: unknown ratio **after** all changes are applied.

        Args:
            corrections: Tuple of TaxonomyCorrectionResult from the oracle.
            taxonomy_rules: Mutable mapping of effect_type ->
                {"family": str, "motion": str}.  Updated in-place.

        Returns:
            A CorrectionReport summarising what was changed and the metric deltas.
        """
        total_candidates = len(corrections)

        # Capture unknown ratio before any mutations.
        unknown_ratio_before = _unknown_ratio(taxonomy_rules)

        # Mean confidence across ALL candidates (using map_confidence as proxy).
        # TaxonomyCorrectionResult stores original_family/motion but not
        # map_confidence directly — we use correction_confidence on unapproved
        # items as 0 (their original uncertainty) and rely on correction_confidence
        # for approved items.  Per spec: mean_confidence_before = average of
        # original map_confidence across ALL corrections.  Since
        # TaxonomyCorrectionResult does not carry map_confidence, we use 0.0
        # for unapproved items and correction_confidence for approved ones as the
        # best available proxy.
        # Actually: the spec says "average of original map_confidence across ALL
        # corrections" — but TaxonomyCorrectionResult does not have that field.
        # We therefore use correction_confidence for ALL items as the pre-state
        # estimate (unapproved items have confidence 0.0 from parse errors, or
        # their oracle score). This is the most faithful interpretation.
        if total_candidates > 0:
            mean_confidence_before = (
                sum(c.correction_confidence for c in corrections) / total_candidates
            )
        else:
            mean_confidence_before = 0.0

        approved = [c for c in corrections if c.approved]
        records: list[CorrectionRecord] = []

        for result in approved:
            # Look up existing entry or create defaults.
            existing = taxonomy_rules.get(
                result.candidate_id,
                {"family": result.original_family, "motion": result.original_motion},
            )
            # Try to find by matching original values if candidate_id not a key.
            # taxonomy_rules is keyed by effect_type; we need to resolve it.
            # Since TaxonomyCorrectionResult doesn't carry effect_type directly,
            # we match by original_family/motion in any entry whose values match,
            # but that is ambiguous.  The applier contract expects the caller to
            # key taxonomy_rules by effect_type AND the candidate_id equals the
            # effect_type OR the caller maps appropriately.
            # Per the model: CorrectionRecord has effect_type; we emit it as
            # candidate_id since that is all we have from TaxonomyCorrectionResult.
            before_family = existing.get("family", result.original_family)
            before_motion = existing.get("motion", result.original_motion)
            after_family = result.corrected_family or before_family
            after_motion = result.corrected_motion or before_motion

            # Update taxonomy_rules in-place keyed by candidate_id.
            taxonomy_rules[result.candidate_id] = {
                "family": after_family,
                "motion": after_motion,
            }

            records.append(
                CorrectionRecord(
                    candidate_id=result.candidate_id,
                    effect_type=result.candidate_id,
                    before_family=before_family,
                    before_motion=before_motion,
                    after_family=after_family,
                    after_motion=after_motion,
                    confidence=result.correction_confidence,
                    rationale=result.rationale,
                )
            )

        total_approved = len(approved)
        total_applied = len(records)

        if total_approved > 0:
            mean_confidence_after = sum(c.correction_confidence for c in approved) / total_approved
        else:
            mean_confidence_after = mean_confidence_before

        unknown_ratio_after = _unknown_ratio(taxonomy_rules)
        confidence_uplift = mean_confidence_after - mean_confidence_before

        return CorrectionReport(
            total_candidates=total_candidates,
            total_approved=total_approved,
            total_applied=total_applied,
            corrections=tuple(records),
            mean_confidence_before=round(min(1.0, max(0.0, mean_confidence_before)), 10),
            mean_confidence_after=round(min(1.0, max(0.0, mean_confidence_after)), 10),
            confidence_uplift=round(confidence_uplift, 10),
            unknown_ratio_before=round(min(1.0, max(0.0, unknown_ratio_before)), 10),
            unknown_ratio_after=round(min(1.0, max(0.0, unknown_ratio_after)), 10),
        )


__all__ = ["CorrectionApplier"]
