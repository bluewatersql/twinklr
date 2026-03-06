from __future__ import annotations

import json
import logging
from typing import Any

from twinklr.core.feature_engineering.normalization.models import (
    AliasClusterGroup,
    AliasReviewResult,
)

logger = logging.getLogger(__name__)

_REVIEW_SYSTEM_PROMPT = """You are an expert in lighting effect taxonomy classification.
Given a cluster of effect type names that may be aliases of each other, determine:
1. Whether these names genuinely refer to the same effect (approved: true/false)
2. A canonical label for the group
3. The most likely effect_family (e.g. MOTION, COLOR, BEAM, STATIC, STROBE, DIMMER)
4. The most likely motion_class (e.g. sweep, chase, rotate, pulse, static, unknown)

Respond in JSON with keys: approved, canonical_label, confidence, rationale, suggested_effect_family, suggested_motion_class"""


class LLMReviewPass:
    """Use LLM to review alias candidates and propose canonical labels.

    Args:
        llm_client: OpenAI client adapter from twinklr.core.api.llm.
        model: Model name to use for review.
    """

    def __init__(self, llm_client: Any, model: str = "gpt-4o-mini") -> None:
        self._client = llm_client
        self._model = model

    def review(
        self,
        clusters: tuple[AliasClusterGroup, ...],
    ) -> tuple[AliasReviewResult, ...]:
        """Review each cluster and propose canonical label.

        For each cluster:
        1. Build a user prompt describing the cluster members and counts
        2. Call LLM with JSON response format
        3. Parse response into AliasReviewResult
        4. On parse failure, create a fallback result (approved=False, confidence=0.0)

        Args:
            clusters: Tuple of alias cluster groups to review.

        Returns:
            Tuple of review results, one per cluster.
        """
        results: list[AliasReviewResult] = []
        for cluster in clusters:
            result = self._review_single(cluster)
            results.append(result)
        return tuple(results)

    def _review_single(self, cluster: AliasClusterGroup) -> AliasReviewResult:
        """Review a single cluster.

        Args:
            cluster: The alias cluster group to review.

        Returns:
            Review result with LLM verdict or fallback on failure.
        """
        user_prompt = self._build_user_prompt(cluster)
        try:
            response = self._client.client.chat.completions.create(
                model=self._model,
                messages=[
                    {"role": "system", "content": _REVIEW_SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt},
                ],
                response_format={"type": "json_object"},
            )
            content = response.choices[0].message.content or "{}"
            data = json.loads(content)
            return AliasReviewResult(
                cluster_id=cluster.cluster_id,
                approved=bool(data.get("approved", False)),
                canonical_label=str(data.get("canonical_label", cluster.suggested_canonical)),
                confidence=float(data.get("confidence", 0.5)),
                rationale=str(data.get("rationale", "")),
                members=cluster.members,
                suggested_effect_family=data.get("suggested_effect_family"),
                suggested_motion_class=data.get("suggested_motion_class"),
            )
        except Exception:
            logger.warning("LLM review failed for cluster %s, using fallback", cluster.cluster_id)
            return AliasReviewResult(
                cluster_id=cluster.cluster_id,
                approved=False,
                canonical_label=cluster.suggested_canonical,
                confidence=0.0,
                rationale="LLM review failed",
                members=cluster.members,
            )

    @staticmethod
    def _build_user_prompt(cluster: AliasClusterGroup) -> str:
        """Build the user prompt for reviewing a cluster.

        Args:
            cluster: The alias cluster group to describe.

        Returns:
            Formatted prompt string for the LLM.
        """
        member_lines = "\n".join(
            f"  - {name} (count: {count})"
            for name, count in zip(cluster.members, cluster.member_counts, strict=True)
        )
        return (
            f"Cluster ID: {cluster.cluster_id}\n"
            f"Suggested canonical: {cluster.suggested_canonical}\n"
            f"Centroid similarity: {cluster.centroid_similarity:.3f}\n"
            f"Members:\n{member_lines}\n\n"
            "Are these the same effect? Provide your analysis in JSON."
        )
