"""Learned taxonomy training baseline (V2.2)."""

from __future__ import annotations

import math
from collections import defaultdict
from dataclasses import dataclass
from typing import cast

from twinklr.core.feature_engineering.models.learned_taxonomy import (
    LearnedTaxonomyEvalReport,
    LearnedTaxonomyModel,
)
from twinklr.core.feature_engineering.models.phrases import EffectPhrase
from twinklr.core.feature_engineering.models.taxonomy import PhraseTaxonomyRecord


@dataclass(frozen=True)
class LearnedTaxonomyTrainerOptions:
    schema_version: str = "v2.2.0"
    model_version: str = "learned_taxonomy_v1"
    min_label_probability: float = 0.40
    eval_split_modulus: int = 5
    min_recall_for_promotion: float = 0.55
    min_f1_for_promotion: float = 0.60


class LearnedTaxonomyTrainer:
    """Train a lightweight multinomial label model from phrase/taxonomy pairs."""

    def __init__(self, options: LearnedTaxonomyTrainerOptions | None = None) -> None:
        self._options = options or LearnedTaxonomyTrainerOptions()

    def train(
        self,
        *,
        phrases: tuple[EffectPhrase, ...],
        taxonomy_rows: tuple[PhraseTaxonomyRecord, ...],
    ) -> tuple[LearnedTaxonomyModel, LearnedTaxonomyEvalReport]:
        taxonomy_by_phrase = {row.phrase_id: row for row in taxonomy_rows}
        train_pairs: list[tuple[EffectPhrase, tuple[str, ...]]] = []
        eval_pairs: list[tuple[EffectPhrase, tuple[str, ...]]] = []

        for phrase in phrases:
            taxonomy = taxonomy_by_phrase.get(phrase.phrase_id)
            if taxonomy is None:
                continue
            labels = tuple(sorted(label.value for label in taxonomy.labels))
            if not labels:
                continue
            if self._split_bucket(phrase.phrase_id) == 0:
                eval_pairs.append((phrase, labels))
            else:
                train_pairs.append((phrase, labels))

        label_doc_counts: dict[str, int] = defaultdict(int)
        label_token_counts: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
        label_total_tokens: dict[str, int] = defaultdict(int)
        vocabulary: set[str] = set()

        for phrase, labels in train_pairs:
            tokens = self._tokens(phrase)
            vocabulary.update(tokens)
            for label in labels:
                label_doc_counts[label] += 1
                for token in tokens:
                    label_token_counts[label][token] += 1
                    label_total_tokens[label] += 1

        label_names = tuple(sorted(label_doc_counts.keys()))
        total_docs = sum(label_doc_counts.values())
        vocab_list = tuple(sorted(vocabulary))
        vocab_size = max(1, len(vocab_list))

        label_priors: dict[str, float] = {}
        token_likelihoods: dict[str, dict[str, float]] = {}
        for label in label_names:
            label_priors[label] = label_doc_counts[label] / total_docs if total_docs > 0 else 0.0
            total = label_total_tokens[label]
            token_probs: dict[str, float] = {}
            for token in vocab_list:
                count = label_token_counts[label].get(token, 0)
                token_probs[token] = (count + 1.0) / (total + vocab_size)
            token_likelihoods[label] = token_probs

        model = LearnedTaxonomyModel(
            schema_version=self._options.schema_version,
            model_version=self._options.model_version,
            label_names=label_names,
            vocabulary=vocab_list,
            label_priors=label_priors,
            token_likelihoods=token_likelihoods,
        )

        metrics = self._evaluate(eval_pairs=eval_pairs, model=model)
        precision_micro = cast(float, metrics["precision_micro"])
        recall_micro = cast(float, metrics["recall_micro"])
        f1_micro = cast(float, metrics["f1_micro"])
        prediction_coverage = cast(float, metrics["prediction_coverage"])
        notes_raw = metrics["notes"]
        notes = tuple(cast(list[str], notes_raw)) if isinstance(notes_raw, list) else ()
        report = LearnedTaxonomyEvalReport(
            schema_version=self._options.schema_version,
            model_version=self._options.model_version,
            train_samples=len(train_pairs),
            eval_samples=len(eval_pairs),
            precision_micro=precision_micro,
            recall_micro=recall_micro,
            f1_micro=f1_micro,
            prediction_coverage=prediction_coverage,
            min_recall_for_promotion=self._options.min_recall_for_promotion,
            min_f1_for_promotion=self._options.min_f1_for_promotion,
            promotion_passed=(
                recall_micro >= self._options.min_recall_for_promotion
                and f1_micro >= self._options.min_f1_for_promotion
            ),
            notes=notes,
        )
        return model, report

    def _evaluate(
        self,
        *,
        eval_pairs: list[tuple[EffectPhrase, tuple[str, ...]]],
        model: LearnedTaxonomyModel,
    ) -> dict[str, float | list[str]]:
        if not eval_pairs:
            return {
                "precision_micro": 0.0,
                "recall_micro": 0.0,
                "f1_micro": 0.0,
                "prediction_coverage": 0.0,
                "notes": ["no_eval_pairs"],
            }

        tp = 0
        fp = 0
        fn = 0
        covered = 0

        for phrase, gold_labels in eval_pairs:
            probs = self.predict_probabilities(phrase=phrase, model=model)
            predicted = {
                label
                for label, probability in probs.items()
                if probability >= self._options.min_label_probability
            }
            gold = set(gold_labels)
            if predicted:
                covered += 1

            tp += len(predicted & gold)
            fp += len(predicted - gold)
            fn += len(gold - predicted)

        precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        f1 = (2.0 * precision * recall / (precision + recall)) if (precision + recall) > 0 else 0.0

        return {
            "precision_micro": round(precision, 6),
            "recall_micro": round(recall, 6),
            "f1_micro": round(f1, 6),
            "prediction_coverage": round(covered / len(eval_pairs), 6),
            "notes": ["weak_supervision_from_v1_taxonomy"],
        }

    @staticmethod
    def predict_probabilities(
        *,
        phrase: EffectPhrase,
        model: LearnedTaxonomyModel,
    ) -> dict[str, float]:
        if not model.label_names:
            return {}
        tokens = LearnedTaxonomyTrainer._tokens(phrase)
        raw_scores: dict[str, float] = {}
        for label in model.label_names:
            prior = max(1e-9, float(model.label_priors.get(label, 1e-9)))
            log_prob = math.log(prior)
            token_probs = model.token_likelihoods.get(label, {})
            fallback = 1.0 / max(1, len(model.vocabulary))
            for token in tokens:
                log_prob += math.log(max(1e-9, float(token_probs.get(token, fallback))))
            raw_scores[label] = log_prob

        max_score = max(raw_scores.values())
        exps = {label: math.exp(score - max_score) for label, score in raw_scores.items()}
        denom = sum(exps.values())
        if denom <= 0.0:
            return dict.fromkeys(model.label_names, 0.0)
        return {label: exps[label] / denom for label in model.label_names}

    @staticmethod
    def _tokens(phrase: EffectPhrase) -> tuple[str, ...]:
        return (
            f"effect_family={phrase.effect_family}",
            f"motion={phrase.motion_class.value}",
            f"color={phrase.color_class.value}",
            f"energy={phrase.energy_class.value}",
            f"continuity={phrase.continuity_class.value}",
            f"spatial={phrase.spatial_class.value}",
            f"layer={phrase.layer_index}",
            f"section={phrase.section_label or 'none'}",
        )

    def _split_bucket(self, phrase_id: str) -> int:
        acc = 0
        for index, char in enumerate(phrase_id):
            acc += (index + 1) * ord(char)
        return acc % max(2, self._options.eval_split_modulus)
