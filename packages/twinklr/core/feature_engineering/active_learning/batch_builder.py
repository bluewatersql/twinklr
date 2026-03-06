"""Review batch builder for active learning taxonomy review pipeline."""

from __future__ import annotations

import uuid

from twinklr.core.feature_engineering.active_learning.models import (
    ReviewBatch,
    ReviewItem,
    UncertaintyCandidate,
)
from twinklr.core.feature_engineering.models.phrases import EffectPhrase
from twinklr.core.feature_engineering.normalization.resolver import EffectAliasResolver


class ReviewBatchBuilder:
    """Constructs contextual review batches from uncertainty candidates.

    Each candidate is wrapped in a ReviewItem enriched with:

    - ``context_phrases``: deduplicated param_signatures from phrases sharing
      the same effect_type.
    - ``suggested_family`` / ``suggested_motion``: alias resolver suggestions
      when a resolver is provided and the effect_type is known to it.
    """

    def build(
        self,
        candidates: tuple[UncertaintyCandidate, ...],
        phrases: tuple[EffectPhrase, ...],
        resolver: EffectAliasResolver | None = None,
    ) -> ReviewBatch:
        """Construct a ReviewBatch from candidates and supporting phrases.

        Args:
            candidates: Uncertainty candidates to wrap into review items.
            phrases: All available EffectPhrase records used for context.
            resolver: Optional alias resolver for suggesting family/motion
                corrections.  Pass ``None`` to skip suggestion enrichment.

        Returns:
            A ReviewBatch with a fresh uuid4 batch_id.
        """
        # Index phrases by effect_type for fast lookup.
        phrases_by_type: dict[str, list[EffectPhrase]] = {}
        for phrase in phrases:
            phrases_by_type.setdefault(phrase.effect_type, []).append(phrase)

        items: list[ReviewItem] = []

        for candidate in candidates:
            matching = phrases_by_type.get(candidate.effect_type, [])

            # Deduplicated param_signatures preserving first-seen order.
            seen: set[str] = set()
            context_phrases: list[str] = []
            for phrase in matching:
                sig = phrase.param_signature
                if sig not in seen:
                    seen.add(sig)
                    context_phrases.append(sig)

            suggested_family: str | None = None
            suggested_motion: str | None = None
            suggestion_source: str | None = None

            if resolver is not None:
                resolved = resolver.resolve(candidate.effect_type)
                if resolved is not None:
                    suggested_family = resolved.effect_family
                    suggested_motion = resolved.motion_class
                    suggestion_source = "alias_resolver"

            items.append(
                ReviewItem(
                    candidate=candidate,
                    context_phrases=tuple(context_phrases),
                    suggested_family=suggested_family,
                    suggested_motion=suggested_motion,
                    suggestion_source=suggestion_source,
                )
            )

        return ReviewBatch(
            batch_id=str(uuid.uuid4()),
            items=tuple(items),
            total_candidates=len(items),
        )


__all__ = ["ReviewBatchBuilder"]
