from __future__ import annotations

from twinklr.core.feature_engineering.color_narrative import ColorNarrativeExtractor
from twinklr.core.feature_engineering.models import (
    ColorClass,
    ContinuityClass,
    EffectPhrase,
    EnergyClass,
    MotionClass,
    PhraseSource,
    SpatialClass,
)


def _phrase(phrase_id: str, section: str, color: ColorClass) -> EffectPhrase:
    return EffectPhrase(
        schema_version="v1.2.0",
        phrase_id=phrase_id,
        package_id="pkg-1",
        sequence_file_id="seq-1",
        effect_event_id=f"evt-{phrase_id}",
        effect_type="On",
        effect_family="on",
        motion_class=MotionClass.STATIC,
        color_class=color,
        energy_class=EnergyClass.MID,
        continuity_class=ContinuityClass.SUSTAINED,
        spatial_class=SpatialClass.SINGLE_TARGET,
        source=PhraseSource.EFFECT_TYPE_MAP,
        map_confidence=1.0,
        target_name="Tree",
        layer_index=0,
        start_ms=0,
        end_ms=1000,
        duration_ms=1000,
        section_label=section,
        param_signature="sig",
    )


def test_color_narrative_extractor_outputs_section_rows() -> None:
    rows = ColorNarrativeExtractor().extract(
        (
            _phrase("a", "intro", ColorClass.MONO),
            _phrase("b", "verse", ColorClass.PALETTE),
            _phrase("c", "verse", ColorClass.PALETTE),
        )
    )

    assert len(rows) == 2
    assert rows[0].section_label == "intro"
    assert rows[1].section_label == "verse"
    assert rows[1].contrast_shift_from_prev >= 0.0
