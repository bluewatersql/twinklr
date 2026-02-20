"""Tests for Color Arc pipeline integration."""

import json
from pathlib import Path

from twinklr.core.feature_engineering.models.color_narrative import ColorNarrativeRow
from twinklr.core.feature_engineering.models.phrases import (
    ColorClass,
    ContinuityClass,
    EffectPhrase,
    EnergyClass,
    MotionClass,
    PhraseSource,
    SpatialClass,
)
from twinklr.core.feature_engineering.pipeline import (
    FeatureEngineeringPipeline,
    FeatureEngineeringPipelineOptions,
)


def _make_phrase(section_label: str, section_index: int) -> EffectPhrase:
    return EffectPhrase(
        schema_version="v1.0.0",
        phrase_id=f"ph_{section_index}",
        package_id="pkg-1",
        sequence_file_id="seq-1",
        effect_event_id=f"evt_{section_index}",
        effect_type="Bars",
        effect_family="single_strand",
        motion_class=MotionClass.SWEEP,
        color_class=ColorClass.PALETTE,
        energy_class=EnergyClass.MID,
        continuity_class=ContinuityClass.SUSTAINED,
        spatial_class=SpatialClass.SINGLE_TARGET,
        source=PhraseSource.EFFECT_TYPE_MAP,
        map_confidence=0.9,
        target_name="MegaTree",
        layer_index=0,
        start_ms=section_index * 4000,
        end_ms=(section_index + 1) * 4000,
        duration_ms=4000,
        section_label=section_label,
        param_signature="bars|sweep|palette",
    )


def _make_color_row(section_label: str, section_index: int) -> ColorNarrativeRow:
    return ColorNarrativeRow(
        schema_version="v1.8.0",
        package_id="pkg-1",
        sequence_file_id="seq-1",
        section_label=section_label,
        section_index=section_index,
        phrase_count=5,
        dominant_color_class="palette",
        contrast_shift_from_prev=0.0,
        hue_family_movement="section_start" if section_index == 0 else "hold",
    )


def test_pipeline_writes_color_arc_when_enabled(tmp_path: Path) -> None:
    """When enable_color_arc=True, pipeline writes color_arc.json."""
    phrases = tuple(_make_phrase(s, i) for i, s in enumerate(["intro", "verse"]))
    color_rows = tuple(_make_color_row(s, i) for i, s in enumerate(["intro", "verse"]))

    options = FeatureEngineeringPipelineOptions(enable_color_arc=True)
    pipeline = FeatureEngineeringPipeline(options=options)

    # Directly call the color arc writer method.
    pipeline._write_color_arc(
        output_root=tmp_path,
        phrases=phrases,
        color_rows=color_rows,
    )

    output_path = tmp_path / "color_arc.json"
    assert output_path.exists()
    data = json.loads(output_path.read_text())
    assert data["schema_version"] == "v1.0.0"
    assert len(data["palette_library"]) >= 1
    assert len(data["section_assignments"]) == 2


def test_pipeline_skips_color_arc_when_disabled(tmp_path: Path) -> None:
    """When enable_color_arc=False, pipeline does not write color_arc.json."""
    options = FeatureEngineeringPipelineOptions(enable_color_arc=False)
    pipeline = FeatureEngineeringPipeline(options=options)

    result = pipeline._write_color_arc(
        output_root=tmp_path,
        phrases=(),
        color_rows=(),
    )

    assert result is None
    assert not (tmp_path / "color_arc.json").exists()
