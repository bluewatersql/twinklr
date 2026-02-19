from __future__ import annotations

from twinklr.core.feature_engineering.layering import LayeringFeatureExtractor
from twinklr.core.feature_engineering.models import (
    ColorClass,
    ContinuityClass,
    EffectPhrase,
    EnergyClass,
    MotionClass,
    PhraseSource,
    SpatialClass,
)


def _phrase(phrase_id: str, layer: int, target: str, start_ms: int, end_ms: int) -> EffectPhrase:
    return EffectPhrase(
        schema_version="v1.2.0",
        phrase_id=phrase_id,
        package_id="pkg-1",
        sequence_file_id="seq-1",
        effect_event_id=f"evt-{phrase_id}",
        effect_type="On",
        effect_family="on",
        motion_class=MotionClass.STATIC,
        color_class=ColorClass.MONO,
        energy_class=EnergyClass.MID,
        continuity_class=ContinuityClass.SUSTAINED,
        spatial_class=SpatialClass.SINGLE_TARGET,
        source=PhraseSource.EFFECT_TYPE_MAP,
        map_confidence=1.0,
        target_name=target,
        layer_index=layer,
        start_ms=start_ms,
        end_ms=end_ms,
        duration_ms=end_ms - start_ms,
        param_signature="sig",
    )


def test_layering_feature_extractor_outputs_metrics() -> None:
    rows = LayeringFeatureExtractor().extract(
        (
            _phrase("a", 0, "Tree", 0, 1000),
            _phrase("b", 1, "Tree", 200, 800),
            _phrase("c", 2, "Star", 900, 1300),
        )
    )

    assert len(rows) == 1
    row = rows[0]
    assert row.max_concurrent_layers >= 1
    assert row.overlap_pairs >= 1
    assert row.same_target_overlap_pairs >= 1

