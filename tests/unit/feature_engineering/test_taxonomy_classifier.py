from __future__ import annotations

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
from twinklr.core.feature_engineering.taxonomy.classifier import TaxonomyClassifier


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

