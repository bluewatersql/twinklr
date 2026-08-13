from __future__ import annotations

import json
from pathlib import Path

from twinklr.core.feature_engineering.models import (
    ColorClass,
    ContinuityClass,
    EffectPhrase,
    EnergyClass,
    MotionClass,
    PhraseSource,
    SpatialClass,
)
from twinklr.core.feature_engineering.models.taxonomy import TaxonomyLabel
from twinklr.core.feature_engineering.taxonomy.classifier import (
    TaxonomyClassifier,
    TaxonomyClassifierOptions,
)


def _phrase(effect_event_id: str, *, duration_ms: int, continuity: ContinuityClass) -> EffectPhrase:
    return EffectPhrase(
        schema_version="v1.2.0",
        phrase_id=f"phrase-{effect_event_id}",
        package_id="pkg-1",
        sequence_file_id="seq-1",
        effect_event_id=effect_event_id,
        effect_type="Bars",
        effect_family="pattern_bars",
        motion_class=MotionClass.SWEEP,
        color_class=ColorClass.PALETTE,
        energy_class=EnergyClass.HIGH,
        continuity_class=continuity,
        spatial_class=SpatialClass.MULTI_TARGET,
        source=PhraseSource.EFFECT_TYPE_MAP,
        map_confidence=1.0,
        target_name="Tree",
        layer_index=0,
        start_ms=0,
        end_ms=duration_ms,
        duration_ms=duration_ms,
        onset_sync_score=0.9,
        param_signature="abc",
    )


def test_taxonomy_classifier_assigns_multiple_labels() -> None:
    classifier = TaxonomyClassifier()
    rows = classifier.classify(
        phrases=(_phrase("evt-1", duration_ms=300, continuity=ContinuityClass.RHYTHMIC),),
        package_id="pkg-1",
        sequence_file_id="seq-1",
    )

    assert len(rows) == 1
    labels = {label.value for label in rows[0].labels}
    assert TaxonomyLabel.RHYTHM_DRIVER.value in labels
    assert TaxonomyLabel.ACCENT_HIT.value in labels
    assert rows[0].rule_hit_keys


def test_taxonomy_classifier_deterministic() -> None:
    classifier = TaxonomyClassifier()
    phrases = (
        _phrase("evt-a", duration_ms=2400, continuity=ContinuityClass.SUSTAINED),
        _phrase("evt-b", duration_ms=400, continuity=ContinuityClass.RHYTHMIC),
    )

    left = classifier.classify(phrases=phrases, package_id="pkg-1", sequence_file_id="seq-1")
    right = classifier.classify(phrases=phrases, package_id="pkg-1", sequence_file_id="seq-1")

    assert [row.model_dump(mode="json") for row in left] == [
        row.model_dump(mode="json") for row in right
    ]


def test_corrections_path_overrides_next_classification(tmp_path: Path) -> None:
    """A corrections rule matching effect_type + param_signature wins the label."""
    phrase = _phrase("evt-c", duration_ms=2400, continuity=ContinuityClass.SUSTAINED)
    baseline = TaxonomyClassifier().classify(
        phrases=(phrase,), package_id="pkg-1", sequence_file_id="seq-1"
    )[0]
    assert TaxonomyLabel.SPARKLE_OVERLAY not in baseline.labels

    corrections_path = tmp_path / "corrections.json"
    corrections_path.write_text(
        json.dumps(
            {
                "schema_version": "1.0.0",
                "labels": {
                    TaxonomyLabel.SPARKLE_OVERLAY.value: {
                        "base": 0.0,
                        "min_confidence": 0.0,
                        "rules": [
                            {
                                "id": "correction:abc123",
                                "when": {
                                    "effect_type": phrase.effect_type,
                                    "param_signature": phrase.param_signature,
                                },
                                "weight": 1.0,
                            }
                        ],
                    }
                },
            }
        ),
        encoding="utf-8",
    )

    corrected = TaxonomyClassifier(
        TaxonomyClassifierOptions(corrections_path=corrections_path)
    ).classify(phrases=(phrase,), package_id="pkg-1", sequence_file_id="seq-1")[0]

    assert TaxonomyLabel.SPARKLE_OVERLAY in corrected.labels
    assert "correction:abc123" in corrected.rule_hit_keys
    top = max(corrected.label_scores, key=lambda score: score.confidence)
    assert top.label is TaxonomyLabel.SPARKLE_OVERLAY


def test_corrections_layer_never_drops_base_rules(tmp_path: Path) -> None:
    """Merging a corrections layer leaves the base config's own labels intact."""
    phrase = _phrase("evt-d", duration_ms=300, continuity=ContinuityClass.RHYTHMIC)
    baseline = TaxonomyClassifier().classify(
        phrases=(phrase,), package_id="pkg-1", sequence_file_id="seq-1"
    )[0]

    corrections_path = tmp_path / "corrections.json"
    corrections_path.write_text(
        json.dumps({"schema_version": "1.0.0", "labels": {}}), encoding="utf-8"
    )

    merged = TaxonomyClassifier(
        TaxonomyClassifierOptions(corrections_path=corrections_path)
    ).classify(phrases=(phrase,), package_id="pkg-1", sequence_file_id="seq-1")[0]

    assert merged.model_dump(mode="json") == baseline.model_dump(mode="json")


def test_corrections_layer_ignores_unknown_labels(tmp_path: Path) -> None:
    """A corrections entry naming a label the classifier cannot score is skipped."""
    phrase = _phrase("evt-e", duration_ms=2400, continuity=ContinuityClass.SUSTAINED)
    corrections_path = tmp_path / "corrections.json"
    corrections_path.write_text(
        json.dumps(
            {
                "schema_version": "1.0.0",
                "labels": {
                    "SPARKLE": {
                        "base": 0.0,
                        "min_confidence": 0.0,
                        "rules": [
                            {
                                "id": "correction:bogus",
                                "when": {"effect_type": phrase.effect_type},
                                "weight": 1.0,
                            }
                        ],
                    }
                },
            }
        ),
        encoding="utf-8",
    )

    row = TaxonomyClassifier(TaxonomyClassifierOptions(corrections_path=corrections_path)).classify(
        phrases=(phrase,), package_id="pkg-1", sequence_file_id="seq-1"
    )[0]

    assert "correction:bogus" not in row.rule_hit_keys
