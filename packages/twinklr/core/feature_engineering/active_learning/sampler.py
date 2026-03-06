"""Uncertainty sampler for active learning taxonomy review pipeline."""

from __future__ import annotations

import hashlib
from collections import Counter, defaultdict

from twinklr.core.feature_engineering.active_learning.models import (
    UncertaintyCandidate,
    UncertaintySamplerOptions,
)
from twinklr.core.feature_engineering.models.phrases import EffectPhrase
from twinklr.core.feature_engineering.models.taxonomy import PhraseTaxonomyRecord


class UncertaintySampler:
    """Selects high-uncertainty taxonomy rows for review.

    Sampling strategy:

    1. All phrases with map_confidence < threshold.
    2. All phrases with effect_family == "unknown" (case-insensitive) and
       occurrence_count >= min_frequency_threshold.
    3. All phrases with motion_class == "unknown" and
       occurrence_count >= min_frequency_threshold.
    4. Deduplicated by (effect_type, param_signature) →
       normalized_key = f"{effect_type}::{param_signature}".
    5. Sorted by uncertainty score descending (lower confidence = higher priority).

    Args:
        options: Sampling configuration.
    """

    def __init__(self, options: UncertaintySamplerOptions) -> None:
        """Initialise the sampler.

        Args:
            options: Configuration controlling thresholds and limits.
        """
        self._opts = options

    def sample(
        self,
        phrases: tuple[EffectPhrase, ...],
        taxonomy: tuple[PhraseTaxonomyRecord, ...],  # noqa: ARG002 — reserved for future use
    ) -> tuple[UncertaintyCandidate, ...]:
        """Select uncertain phrases and return deduplicated candidates.

        Args:
            phrases: All EffectPhrase records to evaluate.
            taxonomy: Corresponding PhraseTaxonomyRecord records (reserved for
                future label-based signals; not currently consumed).

        Returns:
            Tuple of UncertaintyCandidate sorted by uncertainty_score descending,
            capped at max_batch_size.
        """
        opts = self._opts

        # Group phrases by normalized_key = effect_type::param_signature.
        groups: dict[str, list[EffectPhrase]] = defaultdict(list)
        for phrase in phrases:
            key = f"{phrase.effect_type}::{phrase.param_signature}"
            groups[key].append(phrase)

        candidates: list[UncertaintyCandidate] = []

        for normalized_key, group_phrases in groups.items():
            effect_type = group_phrases[0].effect_type
            occurrence_count = len(group_phrases)
            min_confidence = min(p.map_confidence for p in group_phrases)

            # Determine reasons this group qualifies.
            reasons: list[str] = []

            is_low_confidence = min_confidence < opts.max_confidence_threshold
            if is_low_confidence:
                reasons.append("low_confidence")

            family_counter: Counter[str] = Counter(p.effect_family for p in group_phrases)
            most_common_family: str = family_counter.most_common(1)[0][0]
            has_unknown_family = (
                opts.include_unknown_families
                and most_common_family.lower() == "unknown"
                and occurrence_count >= opts.min_frequency_threshold
            )
            if has_unknown_family:
                reasons.append("unknown_family")

            motion_counter: Counter[str] = Counter(p.motion_class.value for p in group_phrases)
            most_common_motion: str = motion_counter.most_common(1)[0][0]
            has_unknown_motion = (
                opts.include_unknown_motions
                and most_common_motion.lower() == "unknown"
                and occurrence_count >= opts.min_frequency_threshold
            )
            if has_unknown_motion:
                reasons.append("unknown_motion")

            if not reasons:
                continue

            candidate_id = hashlib.sha1(normalized_key.encode()).hexdigest()[:16]  # noqa: S324
            uncertainty_score = round(1.0 - min_confidence, 10)
            sample_ids = tuple(p.phrase_id for p in group_phrases[:5])

            candidates.append(
                UncertaintyCandidate(
                    candidate_id=candidate_id,
                    effect_type=effect_type,
                    normalized_key=normalized_key,
                    current_family=most_common_family,
                    current_motion=most_common_motion,
                    map_confidence=min_confidence,
                    occurrence_count=occurrence_count,
                    uncertainty_score=uncertainty_score,
                    uncertainty_reasons=tuple(reasons),
                    sample_phrase_ids=sample_ids,
                )
            )

        candidates.sort(key=lambda c: c.uncertainty_score, reverse=True)
        return tuple(candidates[: opts.max_batch_size])


__all__ = ["UncertaintySampler"]
