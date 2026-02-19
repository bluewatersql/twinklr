from __future__ import annotations

from twinklr.core.feature_engineering.models.phrases import (
    ColorClass,
    ContinuityClass,
    EffectPhrase,
    EnergyClass,
    MotionClass,
    PhraseSource,
    SpatialClass,
)
from twinklr.core.feature_engineering.models.taxonomy import (
    PhraseTaxonomyRecord,
    TaxonomyLabel,
)
from twinklr.core.feature_engineering.taxonomy import (
    LearnedTaxonomyInference,
    LearnedTaxonomyInferenceOptions,
    LearnedTaxonomyTrainer,
    TaxonomyClassifier,
)


def _phrase(phrase_id: str, effect_family: str, motion: MotionClass) -> EffectPhrase:
    return EffectPhrase(
        schema_version="v1.2.0",
        phrase_id=phrase_id,
        package_id="pkg-1",
        sequence_file_id="seq-1",
        effect_event_id=f"evt-{phrase_id}",
        effect_type=effect_family,
        effect_family=effect_family,
        motion_class=motion,
        color_class=ColorClass.PALETTE,
        energy_class=EnergyClass.MID,
        continuity_class=ContinuityClass.RHYTHMIC,
        spatial_class=SpatialClass.GROUP,
        source=PhraseSource.EFFECT_TYPE_MAP,
        map_confidence=1.0,
        target_name="Tree",
        layer_index=0,
        start_ms=0,
        end_ms=500,
        duration_ms=500,
        start_beat_index=0,
        end_beat_index=1,
        section_label="verse",
        onset_sync_score=0.8,
        param_signature="sig",
    )


def _taxonomy(phrase_id: str, label: TaxonomyLabel) -> PhraseTaxonomyRecord:
    return PhraseTaxonomyRecord(
        schema_version="v1.3.0",
        classifier_version="test",
        phrase_id=phrase_id,
        package_id="pkg-1",
        sequence_file_id="seq-1",
        effect_event_id=f"evt-{phrase_id}",
        labels=(label,),
        label_confidences=(0.8,),
        rule_hit_keys=("r1",),
        label_scores=(),
    )


def test_learned_taxonomy_trainer_produces_model_and_eval() -> None:
    phrases = (
        _phrase("p1", "on", MotionClass.PULSE),
        _phrase("p2", "on", MotionClass.PULSE),
        _phrase("p3", "bars", MotionClass.SWEEP),
        _phrase("p4", "bars", MotionClass.SWEEP),
        _phrase("p5", "on", MotionClass.PULSE),
    )
    taxonomy_rows = (
        _taxonomy("p1", TaxonomyLabel.RHYTHM_DRIVER),
        _taxonomy("p2", TaxonomyLabel.RHYTHM_DRIVER),
        _taxonomy("p3", TaxonomyLabel.MOTION_DRIVER),
        _taxonomy("p4", TaxonomyLabel.MOTION_DRIVER),
        _taxonomy("p5", TaxonomyLabel.RHYTHM_DRIVER),
    )

    model, report = LearnedTaxonomyTrainer().train(
        phrases=phrases,
        taxonomy_rows=taxonomy_rows,
    )

    assert model.label_names
    assert report.train_samples > 0


def test_learned_taxonomy_inference_uses_fallback_when_low_confidence() -> None:
    phrases = (
        _phrase("p1", "on", MotionClass.PULSE),
        _phrase("p2", "bars", MotionClass.SWEEP),
        _phrase("p3", "on", MotionClass.PULSE),
    )
    taxonomy_rows = (
        _taxonomy("p1", TaxonomyLabel.RHYTHM_DRIVER),
        _taxonomy("p2", TaxonomyLabel.MOTION_DRIVER),
        _taxonomy("p3", TaxonomyLabel.RHYTHM_DRIVER),
    )

    model, _report = LearnedTaxonomyTrainer().train(
        phrases=phrases,
        taxonomy_rows=taxonomy_rows,
    )

    inference = LearnedTaxonomyInference(
        model=model,
        options=LearnedTaxonomyInferenceOptions(
            min_label_probability=0.99,
            fallback_probability_threshold=0.99,
        ),
        fallback_classifier=TaxonomyClassifier(),
    )
    rows = inference.classify(
        phrases=(phrases[0],),
        package_id="pkg-1",
        sequence_file_id="seq-1",
    )

    assert rows[0].classifier_version.endswith(":fallback")
