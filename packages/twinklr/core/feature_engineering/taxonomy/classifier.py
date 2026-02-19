"""Deterministic effect-function taxonomy classifier (V1.3)."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from twinklr.core.feature_engineering.models import EffectPhrase
from twinklr.core.feature_engineering.models.taxonomy import (
    PhraseTaxonomyRecord,
    TaxonomyLabel,
    TaxonomyLabelScore,
)

_DEFAULT_CONFIG = Path(__file__).resolve().parent / "config" / "effect_function_v1.json"


@dataclass(frozen=True)
class TaxonomyClassifierOptions:
    """Runtime options for deterministic taxonomy classification."""

    rules_path: Path | None = None


class TaxonomyClassifier:
    """Classify phrase function with deterministic weighted rules."""

    def __init__(self, options: TaxonomyClassifierOptions | None = None) -> None:
        self._options = options or TaxonomyClassifierOptions()
        self._config = self._load_config(self._options.rules_path or _DEFAULT_CONFIG)
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
            else:
                if isinstance(actual, str) and isinstance(allowed, str):
                    if actual.lower() != allowed.lower():
                        return False
                elif actual != allowed:
                    return False
        return True

