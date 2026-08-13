"""Deterministic effect-function taxonomy classifier (V1.3)."""

from __future__ import annotations

import copy
from dataclasses import dataclass
import json
import logging
from pathlib import Path
from typing import Any

from twinklr.core.feature_engineering.models import EffectPhrase
from twinklr.core.feature_engineering.models.taxonomy import (
    PhraseTaxonomyRecord,
    TaxonomyLabel,
    TaxonomyLabelScore,
)

logger = logging.getLogger(__name__)

_DEFAULT_CONFIG = Path(__file__).resolve().parent / "config" / "effect_function_v2.json"

DEFAULT_CORRECTIONS_PATH = Path(__file__).resolve().parent / "config" / "corrections.json"
"""Git-tracked layer of human-reviewed taxonomy corrections merged over the base rules."""


@dataclass(frozen=True)
class TaxonomyClassifierOptions:
    """Runtime options for deterministic taxonomy classification.

    Attributes:
        rules_path: Base weighted-rules config; defaults to ``effect_function_v2.json``.
        corrections_path: Optional additive corrections layer written by the
            active-learning loop.  Its ``labels[*].rules`` are appended to the
            base config's matching labels; nothing in the base config is
            rewritten or removed.
    """

    rules_path: Path | None = None
    corrections_path: Path | None = None


class TaxonomyClassifier:
    """Classify phrase function with deterministic weighted rules."""

    def __init__(self, options: TaxonomyClassifierOptions | None = None) -> None:
        self._options = options or TaxonomyClassifierOptions()
        self._config = self._load_config(self._options.rules_path or _DEFAULT_CONFIG)
        corrections_path = self._options.corrections_path
        if corrections_path is not None and corrections_path.exists():
            self._config = self._merge_corrections(
                self._config, self._load_config(corrections_path)
            )
        self._schema_version = str(self._config["schema_version"])
        self._classifier_version = str(self._config["classifier_version"])
        labels = self._config.get("labels")
        if not isinstance(labels, dict):
            raise ValueError("Taxonomy config missing labels map")
        self._labels = labels

    @staticmethod
    def _load_config(path: Path) -> dict[str, Any]:
        payload = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise ValueError(f"Invalid taxonomy config at {path}")
        return payload

    @staticmethod
    def _merge_corrections(
        base: dict[str, Any],
        corrections: dict[str, Any],
    ) -> dict[str, Any]:
        """Append correction rules onto the base config's labels.

        The merge is additive: existing rules are never rewritten or dropped,
        and a rule whose ``id`` is already present is ignored so re-loading the
        same corrections file is idempotent.  Labels that are not valid
        :class:`TaxonomyLabel` members are skipped — the scoring loop cannot
        construct them.

        Args:
            base: Parsed base rules config.
            corrections: Parsed corrections config (same ``labels`` schema).

        Returns:
            A new config dict with correction rules merged in.
        """
        merged = copy.deepcopy(base)
        extra = corrections.get("labels")
        if not isinstance(extra, dict):
            return merged
        labels = merged.setdefault("labels", {})
        if not isinstance(labels, dict):
            return merged
        valid_labels = {label.value for label in TaxonomyLabel}

        for name, spec in sorted(extra.items()):
            if name not in valid_labels:
                logger.warning("Ignoring correction for unknown taxonomy label %r", name)
                continue
            if not isinstance(spec, dict):
                continue
            new_rules = spec.get("rules", [])
            if not isinstance(new_rules, list):
                continue
            entry = labels.get(name)
            if not isinstance(entry, dict):
                labels[name] = {
                    "base": float(spec.get("base", 0.0)),
                    "min_confidence": float(spec.get("min_confidence", 0.0)),
                    "rules": list(new_rules),
                }
                continue
            existing = entry.setdefault("rules", [])
            if not isinstance(existing, list):
                continue
            known_ids = {rule.get("id") for rule in existing if isinstance(rule, dict)}
            for rule in new_rules:
                if isinstance(rule, dict) and rule.get("id") not in known_ids:
                    existing.append(rule)
        return merged

    def classify(
        self,
        *,
        phrases: tuple[EffectPhrase, ...],
        package_id: str,
        sequence_file_id: str,
    ) -> tuple[PhraseTaxonomyRecord, ...]:
        rows: list[PhraseTaxonomyRecord] = []
        for phrase in phrases:
            rows.append(
                self._classify_phrase(
                    phrase=phrase,
                    package_id=package_id,
                    sequence_file_id=sequence_file_id,
                )
            )
        return tuple(rows)

    def _classify_phrase(
        self,
        *,
        phrase: EffectPhrase,
        package_id: str,
        sequence_file_id: str,
    ) -> PhraseTaxonomyRecord:
        label_scores: list[TaxonomyLabelScore] = []

        for label_name, spec in sorted(self._labels.items(), key=lambda item: item[0]):
            if not isinstance(spec, dict):
                continue
            label = TaxonomyLabel(label_name)
            score = float(spec.get("base", 0.0))
            min_confidence = float(spec.get("min_confidence", 0.25))
            hit_keys: list[str] = []
            rules = spec.get("rules", [])
            if isinstance(rules, list):
                for rule in rules:
                    if not isinstance(rule, dict):
                        continue
                    when = rule.get("when", {})
                    if not isinstance(when, dict):
                        continue
                    if self._matches(phrase, when):
                        score += float(rule.get("weight", 0.0))
                        hit_keys.append(str(rule.get("id", "unknown_rule")))
            score = max(0.0, min(1.0, score))
            if hit_keys and score >= min_confidence:
                label_scores.append(
                    TaxonomyLabelScore(
                        label=label,
                        confidence=score,
                        rule_hits=tuple(sorted(hit_keys)),
                    )
                )

        label_scores.sort(key=lambda row: row.label.value)
        labels = tuple(row.label for row in label_scores)
        confidences = tuple(row.confidence for row in label_scores)
        rule_hit_keys: list[str] = []
        for row in label_scores:
            rule_hit_keys.extend(row.rule_hits)

        return PhraseTaxonomyRecord(
            schema_version=self._schema_version,
            classifier_version=self._classifier_version,
            phrase_id=phrase.phrase_id,
            package_id=package_id,
            sequence_file_id=sequence_file_id,
            effect_event_id=phrase.effect_event_id,
            labels=labels,
            label_confidences=confidences,
            rule_hit_keys=tuple(sorted(set(rule_hit_keys))),
            label_scores=tuple(label_scores),
        )

    @staticmethod
    def _matches(phrase: EffectPhrase, when: dict[str, Any]) -> bool:
        for key, allowed in when.items():
            value = getattr(phrase, key, None)
            if isinstance(value, str):
                actual = value
            elif value is None:
                actual = None
            else:
                actual = getattr(value, "value", str(value))

            if isinstance(allowed, list):
                normalized = {
                    str(item).lower() if isinstance(item, str) else item for item in allowed
                }
                if isinstance(actual, str):
                    if actual.lower() not in normalized:
                        return False
                elif actual not in normalized:
                    return False
            elif isinstance(allowed, dict):
                if not isinstance(actual, (float, int)):
                    return False
                if "min" in allowed and actual < float(allowed["min"]):
                    return False
                if "max" in allowed and actual > float(allowed["max"]):
                    return False
            elif isinstance(actual, str) and isinstance(allowed, str):
                if actual.lower() != allowed.lower():
                    return False
            elif actual != allowed:
                return False
        return True
