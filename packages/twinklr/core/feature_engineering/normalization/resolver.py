"""Runtime resolver for unknown effect types — Phase B of Profiling V2."""

from __future__ import annotations

import json
import re
from pathlib import Path

from twinklr.core.feature_engineering.normalization.models import (
    AliasReviewResult,
    ResolvedEffect,
    TaxonomyRulePatch,
)


def _normalize_key(effect_type: str) -> str:
    """Normalize an effect type string to a lookup key.

    Args:
        effect_type: Raw effect type string.

    Returns:
        Lowercased, non-alphanumeric-stripped key.
    """
    return re.sub(r"[^a-z0-9]+", "", effect_type.strip().lower())


class EffectAliasResolver:
    """Runtime resolver: maps unknown effect types to canonical names.

    Maintains four parallel dicts keyed by *normalized* effect type (so
    lookups are case-insensitive and punctuation-tolerant):

    - ``alias_map``: normalized_key -> canonical_name
    - ``family_map``: normalized_key -> effect_family or None
    - ``motion_map``: normalized_key -> motion_class or None
    - ``confidence_map``: normalized_key -> confidence float

    Example::

        resolver = EffectAliasResolver.from_json(Path("effect_alias_candidates.json"))
        resolved = resolver.resolve("Chase")
    """

    def __init__(
        self,
        alias_map: dict[str, str],
        family_map: dict[str, str | None],
        motion_map: dict[str, str | None],
        confidence_map: dict[str, float],
    ) -> None:
        """Initialise with pre-built lookup maps (all keyed by normalized key).

        Args:
            alias_map: normalized_key -> canonical_name.
            family_map: normalized_key -> effect_family (or None).
            motion_map: normalized_key -> motion_class (or None).
            confidence_map: normalized_key -> confidence score.
        """
        self._alias_map = alias_map
        self._family_map = family_map
        self._motion_map = motion_map
        self._confidence_map = confidence_map

    # ------------------------------------------------------------------
    # Factories
    # ------------------------------------------------------------------

    @classmethod
    def from_review_results(cls, results: tuple[AliasReviewResult, ...]) -> EffectAliasResolver:
        """Build resolver from approved LLM review results only.

        Rejected results are silently ignored. Each *member* of an approved
        cluster is mapped to the cluster's ``canonical_label``.

        Args:
            results: All review results, including rejected ones.

        Returns:
            A new ``EffectAliasResolver`` covering only approved clusters.
        """
        alias_map: dict[str, str] = {}
        family_map: dict[str, str | None] = {}
        motion_map: dict[str, str | None] = {}
        confidence_map: dict[str, float] = {}

        for result in results:
            if not result.approved:
                continue
            for member in result.members:
                key = _normalize_key(member)
                alias_map[key] = result.canonical_label
                family_map[key] = result.suggested_effect_family
                motion_map[key] = result.suggested_motion_class
                confidence_map[key] = result.confidence

        return cls(alias_map, family_map, motion_map, confidence_map)

    @classmethod
    def from_json(cls, path: Path) -> EffectAliasResolver:
        """Load resolver from an ``effect_alias_candidates.json`` file.

        The JSON file is expected to have been written by ``to_json``.

        Args:
            path: Path to the JSON artifact.

        Returns:
            A reconstructed ``EffectAliasResolver``.

        Raises:
            FileNotFoundError: If the file does not exist.
            ValueError: If the file cannot be parsed.
        """
        raw = json.loads(path.read_text(encoding="utf-8"))
        alias_raw: dict[str, str] = raw.get("alias_map", {})
        family_raw: dict[str, str | None] = raw.get("family_map", {})
        motion_raw: dict[str, str | None] = raw.get("motion_map", {})
        conf_raw: dict[str, object] = raw.get("confidence_map", {})
        return cls(
            alias_map=dict(alias_raw),
            family_map=dict(family_raw),
            motion_map=dict(motion_raw),
            confidence_map={k: float(v) for k, v in conf_raw.items()},  # type: ignore[arg-type]
        )

    # ------------------------------------------------------------------
    # Runtime resolution
    # ------------------------------------------------------------------

    def resolve(self, effect_type: str) -> ResolvedEffect | None:
        """Resolve an unknown effect type to its canonical name.

        Lookup is case-insensitive (via normalized key). Returns ``None``
        if the effect type is not in the resolver.

        Args:
            effect_type: Raw effect type string from the sequence data.

        Returns:
            A ``ResolvedEffect`` if a mapping exists, otherwise ``None``.
        """
        key = _normalize_key(effect_type)
        if key not in self._alias_map:
            return None
        return ResolvedEffect(
            original_effect_type=effect_type,
            canonical_name=self._alias_map[key],
            effect_family=self._family_map.get(key),
            motion_class=self._motion_map.get(key),
            confidence=self._confidence_map.get(key, 0.0),
        )

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def to_json(self, path: Path) -> None:
        """Persist resolver state to a JSON file.

        Args:
            path: Destination path. Parent directories must exist.
        """
        payload = {
            "alias_map": self._alias_map,
            "family_map": self._family_map,
            "motion_map": self._motion_map,
            "confidence_map": self._confidence_map,
        }
        path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")

    # ------------------------------------------------------------------
    # Taxonomy patch generation
    # ------------------------------------------------------------------

    @staticmethod
    def generate_taxonomy_patches(
        results: tuple[AliasReviewResult, ...],
    ) -> tuple[TaxonomyRulePatch, ...]:
        """Generate taxonomy rule patches from approved review results.

        One patch is emitted per *member* of each approved cluster. Rejected
        results produce no patches.

        Args:
            results: All review results, including rejected ones.

        Returns:
            A tuple of ``TaxonomyRulePatch`` objects for approved members.
        """
        patches: list[TaxonomyRulePatch] = []
        for result in results:
            if not result.approved:
                continue
            for member in result.members:
                patches.append(
                    TaxonomyRulePatch(
                        effect_type=member,
                        canonical_name=result.canonical_label,
                        effect_family=result.suggested_effect_family,
                        motion_class=result.suggested_motion_class,
                        source_cluster_id=result.cluster_id,
                        confidence=result.confidence,
                    )
                )
        return tuple(patches)


__all__ = ["EffectAliasResolver"]
