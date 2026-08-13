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


def _unknown_ratio(taxonomy_overrides: dict[str, dict[str, str]]) -> float:
    """Compute the fraction of entries with unknown family or motion.

    Args:
        taxonomy_overrides: Mapping of candidate_id -> {"family": ..., "motion": ...}.

    Returns:
        Ratio in [0.0, 1.0]; 0.0 when the dict is empty.
    """
    if not taxonomy_overrides:
        return 0.0
    unknown_count = sum(
        1
        for v in taxonomy_overrides.values()
        if v.get("family", "").lower() == _UNKNOWN_FAMILY
        or v.get("motion", "").lower() == _UNKNOWN_MOTION
    )
    return unknown_count / len(taxonomy_overrides)


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
        taxonomy_overrides: dict[str, dict[str, str]],
    ) -> CorrectionReport:
        """Apply approved corrections to taxonomy_overrides and return a report.

        Contract: ``taxonomy_overrides`` is keyed by
        :attr:`TaxonomyCorrectionResult.candidate_id` — the sha1 identity of an
        ``(effect_type, param_signature)`` pair produced by
        :class:`UncertaintySampler`.  It is *not* keyed by ``effect_type``: one
        effect type can have several param signatures whose correct labels
        differ, so the candidate id is the granularity a correction targets.
        The real effect type of each correction travels on
        :attr:`TaxonomyCorrectionResult.effect_type` and is copied verbatim
        onto :attr:`CorrectionRecord.effect_type`.

        Only corrections with ``approved=True`` are applied.  For each such
        correction that provides a ``corrected_family`` or ``corrected_motion``
        the corresponding entry in ``taxonomy_overrides`` is updated in-place.

        Metrics computed:
        - ``mean_confidence_before``: average ``map_confidence`` across **all**
          corrections (approved or not).  0.0 when the input is empty.
        - ``mean_confidence_after``: average ``correction_confidence`` across
          approved corrections.  Falls back to ``mean_confidence_before`` when
          there are no approved corrections.
        - ``confidence_uplift``: after - before.
        - ``unknown_ratio_before``: unknown ratio of ``taxonomy_overrides``
          **before** any changes are applied.
        - ``unknown_ratio_after``: unknown ratio **after** all changes are applied.

        Args:
            corrections: Tuple of TaxonomyCorrectionResult from the review
                (human-edited corrections file or LLM oracle).
            taxonomy_overrides: Mutable mapping of candidate_id ->
                {"family": str, "motion": str}.  Updated in-place.

        Returns:
            A CorrectionReport summarising what was changed and the metric deltas.
        """
        total_candidates = len(corrections)

        # Capture unknown ratio before any mutations.
        unknown_ratio_before = _unknown_ratio(taxonomy_overrides)

        # TaxonomyCorrectionResult does not carry the original map_confidence, so
        # correction_confidence across all items (0.0 for unreviewed/failed ones)
        # stands in for the pre-correction confidence level.
        if total_candidates > 0:
            mean_confidence_before = (
                sum(c.correction_confidence for c in corrections) / total_candidates
            )
        else:
            mean_confidence_before = 0.0

        approved = [c for c in corrections if c.approved]
        records: list[CorrectionRecord] = []

        for result in approved:
            existing = taxonomy_overrides.get(
                result.candidate_id,
                {"family": result.original_family, "motion": result.original_motion},
            )
            before_family = existing.get("family", result.original_family)
            before_motion = existing.get("motion", result.original_motion)
            after_family = result.corrected_family or before_family
            after_motion = result.corrected_motion or before_motion

            taxonomy_overrides[result.candidate_id] = {
                "family": after_family,
                "motion": after_motion,
            }

            records.append(
                CorrectionRecord(
                    candidate_id=result.candidate_id,
                    effect_type=result.effect_type,
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

        unknown_ratio_after = _unknown_ratio(taxonomy_overrides)
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
