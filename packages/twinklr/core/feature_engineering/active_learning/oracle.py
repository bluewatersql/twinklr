"""LLM-based oracle for adjudicating uncertain taxonomy classifications."""

from __future__ import annotations

import json
import logging
from typing import Any, Protocol

from twinklr.core.feature_engineering.active_learning.models import (
    ReviewBatch,
    ReviewItem,
    TaxonomyCorrectionResult,
)

logger = logging.getLogger(__name__)

_KNOWN_FAMILIES: frozenset[str] = frozenset(
    {
        "CHASE",
        "STROBE",
        "STATIC",
        "COLOR",
        "BARS",
        "WAVE",
        "MORPH",
        "BUTTERFLY",
        "SPARKLE",
        "FIREWORKS",
        "LIGHTNING",
        "SHIMMER",
        "WARP",
        "CIRCLES",
        "CUSTOM",
    }
)

_KNOWN_MOTIONS: frozenset[str] = frozenset(
    {"static", "sweep", "pulse", "sparkle", "dmx_program", "unknown"}
)

_SYSTEM_PROMPT = """\
You are a lighting-effect taxonomy expert. Your task is to classify a lighting effect \
into the correct effect_family and motion_class.

Known effect families: CHASE, STROBE, STATIC, COLOR, BARS, WAVE, MORPH, BUTTERFLY, \
SPARKLE, FIREWORKS, LIGHTNING, SHIMMER, WARP, CIRCLES, CUSTOM

Known motion classes: static, sweep, pulse, sparkle, dmx_program, unknown

Given an effect_type, context phrases, and optional suggestions, respond with a JSON \
object (no markdown) containing exactly these keys:
  corrected_family  - string from the known families list
  corrected_motion  - string from the known motion classes list
  confidence        - float between 0.0 and 1.0
  rationale         - brief explanation (max 200 chars)
  approved          - boolean, true if you are confident in the correction

Respond with raw JSON only. No code fences, no extra text."""


def _build_user_prompt(item: ReviewItem) -> str:
    """Build the per-item user prompt.

    Args:
        item: The review item containing candidate data and context.

    Returns:
        A formatted string suitable for the user turn of the LLM conversation.
    """
    c = item.candidate
    lines: list[str] = [
        f"effect_type: {c.effect_type}",
        f"current_family: {c.current_family}",
        f"current_motion: {c.current_motion}",
        f"map_confidence: {c.map_confidence:.3f}",
        f"uncertainty_reasons: {', '.join(c.uncertainty_reasons)}",
    ]
    if item.context_phrases:
        lines.append(f"context_phrases: {'; '.join(item.context_phrases)}")
    if item.suggested_family:
        lines.append(f"suggested_family: {item.suggested_family}")
    if item.suggested_motion:
        lines.append(f"suggested_motion: {item.suggested_motion}")
    if item.suggestion_source:
        lines.append(f"suggestion_source: {item.suggestion_source}")
    return "\n".join(lines)


def _parse_llm_response(
    raw: str,
    item: ReviewItem,
) -> TaxonomyCorrectionResult:
    """Parse the LLM response JSON into a TaxonomyCorrectionResult.

    Args:
        raw: Raw string returned by the LLM.
        item: The original review item (used for original family/motion).

    Returns:
        A TaxonomyCorrectionResult populated from the parsed data, or a
        fallback with approved=False on any parse failure.
    """
    c = item.candidate
    try:
        data = json.loads(raw.strip())
        corrected_family: str | None = data.get("corrected_family")
        corrected_motion: str | None = data.get("corrected_motion")
        confidence_raw = data.get("confidence", 0.0)
        rationale: str = str(data.get("rationale", ""))[:500]
        approved: bool = bool(data.get("approved", False))

        # Clamp confidence to [0, 1].
        confidence = float(max(0.0, min(1.0, float(confidence_raw))))

        # Null out values that are not in known sets.
        if corrected_family is not None and corrected_family not in _KNOWN_FAMILIES:
            logger.warning(
                "Oracle returned unknown family %r for %s; discarding",
                corrected_family,
                c.effect_type,
            )
            corrected_family = None
        if corrected_motion is not None and corrected_motion not in _KNOWN_MOTIONS:
            logger.warning(
                "Oracle returned unknown motion %r for %s; discarding",
                corrected_motion,
                c.effect_type,
            )
            corrected_motion = None

    except (json.JSONDecodeError, TypeError, ValueError) as exc:
        logger.warning("Failed to parse LLM response for %s: %s", c.effect_type, exc)
        return TaxonomyCorrectionResult(
            candidate_id=c.candidate_id,
            original_family=c.current_family,
            original_motion=c.current_motion,
            corrected_family=None,
            corrected_motion=None,
            correction_confidence=0.0,
            rationale="LLM response parse error",
            approved=False,
        )

    return TaxonomyCorrectionResult(
        candidate_id=c.candidate_id,
        original_family=c.current_family,
        original_motion=c.current_motion,
        corrected_family=corrected_family,
        corrected_motion=corrected_motion,
        correction_confidence=confidence,
        rationale=rationale,
        approved=approved,
    )


class LLMClientProtocol(Protocol):
    """Minimal interface expected of the LLM client."""

    def complete(self, messages: list[dict[str, str]]) -> str:
        """Send a list of chat messages and return the assistant reply.

        Args:
            messages: List of role/content dicts (e.g. system, user).

        Returns:
            The assistant's raw text response.
        """
        ...


class TaxonomyReviewOracle:
    """LLM-based adjudicator for uncertain taxonomy classifications.

    Uses structured prompts to:
    1. Review current classification with context
    2. Propose corrected effect_family and motion_class
    3. Provide confidence and rationale

    Args:
        llm_client: Any object implementing LLMClientProtocol.
    """

    def __init__(self, llm_client: Any) -> None:
        """Initialise the oracle with an LLM client.

        Args:
            llm_client: Client with a ``complete(messages)`` method.
        """
        self._client: LLMClientProtocol = llm_client

    def review(self, batch: ReviewBatch) -> tuple[TaxonomyCorrectionResult, ...]:
        """Review all items in the batch and return correction results.

        For each ReviewItem the oracle:
        - Builds a system prompt explaining the classification task.
        - Builds a user prompt with candidate data, context phrases, and suggestions.
        - Calls ``llm_client.complete()``.
        - Parses the JSON response into a TaxonomyCorrectionResult.

        On any parse failure the result will have ``approved=False`` and
        ``rationale="LLM response parse error"``.

        Args:
            batch: The batch of review items to adjudicate.

        Returns:
            A tuple of TaxonomyCorrectionResult, one per item in the batch,
            in the same order as ``batch.items``.
        """
        results: list[TaxonomyCorrectionResult] = []
        for item in batch.items:
            messages: list[dict[str, str]] = [
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": _build_user_prompt(item)},
            ]
            try:
                raw = self._client.complete(messages)
            except Exception as exc:  # noqa: BLE001
                logger.error(
                    "LLM client raised an exception for %s: %s",
                    item.candidate.effect_type,
                    exc,
                )
                raw = ""
            results.append(_parse_llm_response(raw, item))
        return tuple(results)


__all__ = ["LLMClientProtocol", "TaxonomyReviewOracle"]
