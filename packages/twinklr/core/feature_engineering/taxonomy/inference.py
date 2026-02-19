"""Learned taxonomy inference with deterministic fallback (V2.2 baseline)."""

from __future__ import annotations

from dataclasses import dataclass

from twinklr.core.feature_engineering.models.learned_taxonomy import LearnedTaxonomyModel
from twinklr.core.feature_engineering.models.phrases import EffectPhrase
from twinklr.core.feature_engineering.models.taxonomy import (
    PhraseTaxonomyRecord,
    TaxonomyLabel,
    TaxonomyLabelScore,
)
from twinklr.core.feature_engineering.taxonomy.classifier import TaxonomyClassifier
from twinklr.core.feature_engineering.taxonomy.modeling import LearnedTaxonomyTrainer


@dataclass(frozen=True)
class LearnedTaxonomyInferenceOptions:
    min_label_probability: float = 0.40
    fallback_probability_threshold: float = 0.35


class LearnedTaxonomyInference:
    """Run learned taxonomy predictions and fallback as needed."""

    def __init__(
        self,
        *,
        model: LearnedTaxonomyModel,
        options: LearnedTaxonomyInferenceOptions | None = None,
        fallback_classifier: TaxonomyClassifier | None = None,
    ) -> None:
        self._model = model
        self._options = options or LearnedTaxonomyInferenceOptions()
        self._fallback = fallback_classifier

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
        probabilities = LearnedTaxonomyTrainer.predict_probabilities(
            phrase=phrase,
            model=self._model,
        )
        selected = sorted(
            (
                (label, probability)
                for label, probability in probabilities.items()
                if probability >= self._options.min_label_probability
            ),
            key=lambda item: item[0],
        )

        max_probability = max(probabilities.values()) if probabilities else 0.0
        if (
            (not selected or max_probability < self._options.fallback_probability_threshold)
            and self._fallback is not None
        ):
            fallback_row = self._fallback.classify(
                phrases=(phrase,),
                package_id=package_id,
                sequence_file_id=sequence_file_id,
            )[0]
            return fallback_row.model_copy(
                update={
                    "classifier_version": f"{self._model.model_version}:fallback",
                }
            )

        label_scores: list[TaxonomyLabelScore] = []
        for label_name, probability in selected:
            try:
                label = TaxonomyLabel(label_name)
            except ValueError:
                continue
            label_scores.append(
                TaxonomyLabelScore(
                    label=label,
                    confidence=round(probability, 6),
                    rule_hits=("learned_model",),
                )
            )

        labels = tuple(row.label for row in label_scores)
        confidences = tuple(row.confidence for row in label_scores)
        return PhraseTaxonomyRecord(
            schema_version=self._model.schema_version,
            classifier_version=self._model.model_version,
            phrase_id=phrase.phrase_id,
            package_id=package_id,
            sequence_file_id=sequence_file_id,
            effect_event_id=phrase.effect_event_id,
            labels=labels,
            label_confidences=confidences,
            rule_hit_keys=("learned_model",),
            label_scores=tuple(label_scores),
        )
