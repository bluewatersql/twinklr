"""Tests for Style Fingerprint pipeline integration."""

import json
from pathlib import Path

from twinklr.core.feature_engineering.models.color_narrative import ColorNarrativeRow
from twinklr.core.feature_engineering.models.layering import LayeringFeatureRow
from twinklr.core.feature_engineering.models.phrases import (
    ColorClass,
    ContinuityClass,
    EffectPhrase,
    EnergyClass,
    MotionClass,
    PhraseSource,
    SpatialClass,
)
from twinklr.core.feature_engineering.models.transitions import (
    TransitionGraph,
    TransitionRecord,
    TransitionType,
)
from twinklr.core.feature_engineering.pipeline import (
    FeatureEngineeringPipeline,
    FeatureEngineeringPipelineOptions,
)


def _make_phrase(idx: int) -> EffectPhrase:
    return EffectPhrase(
        schema_version="v1.0.0",
        phrase_id=f"ph_{idx}",
        package_id="pkg-1",
        sequence_file_id="seq-1",
        effect_event_id=f"evt_{idx}",
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
        start_ms=idx * 1000,
        end_ms=(idx + 1) * 1000,
        duration_ms=1000,
        section_label="verse",
        onset_sync_score=0.8,
        param_signature="bars|sweep|palette",
    )


def _make_layering_row() -> LayeringFeatureRow:
    return LayeringFeatureRow(
        schema_version="v1.7.0",
        package_id="pkg-1",
        sequence_file_id="seq-1",
        phrase_count=10,
        max_concurrent_layers=3,
        mean_concurrent_layers=2.0,
        hierarchy_transitions=5,
        overlap_pairs=3,
        same_target_overlap_pairs=1,
        collision_score=0.2,
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
        contrast_shift_from_prev=0.3,
        hue_family_movement="hold",
    )


def test_pipeline_writes_style_fingerprint_when_enabled(tmp_path: Path) -> None:
    """When enable_style_fingerprint=True, pipeline writes style_fingerprint.json."""
    phrases = tuple(_make_phrase(i) for i in range(10))
    layering_rows = (_make_layering_row(),)
    color_rows = (_make_color_row("intro", 0), _make_color_row("verse", 1))
    transition_graph = TransitionGraph(
        schema_version="v1.6.0",
        graph_version="v1",
        total_transitions=1,
        total_nodes=2,
        total_edges=1,
        transitions=(
            TransitionRecord(
                sequence_file_id="seq-1",
                package_id="pkg-1",
                from_phrase_id="ph_0",
                to_phrase_id="ph_1",
                from_template_id="tpl_a",
                to_template_id="tpl_b",
                from_end_ms=1000,
                to_start_ms=1050,
                gap_ms=50,
                transition_type=TransitionType.CROSSFADE,
            ),
        ),
    )

    options = FeatureEngineeringPipelineOptions(enable_style_fingerprint=True)
    pipeline = FeatureEngineeringPipeline(options=options)

    result = pipeline._write_style_fingerprint(
        output_root=tmp_path,
        creator_id="creator-1",
        phrases=phrases,
        layering_rows=layering_rows,
        color_rows=color_rows,
        transition_graph=transition_graph,
    )

    assert result is not None
    output_path = tmp_path / "style_fingerprint.json"
    assert output_path.exists()
    data = json.loads(output_path.read_text())
    assert data["creator_id"] == "creator-1"
    assert data["corpus_sequence_count"] >= 1
    assert "recipe_preferences" in data
    assert "transition_style" in data
    assert "color_tendencies" in data
    assert "timing_style" in data
    assert "layering_style" in data


def test_pipeline_skips_style_fingerprint_when_disabled(tmp_path: Path) -> None:
    """When enable_style_fingerprint=False, pipeline does not write style_fingerprint.json."""
    options = FeatureEngineeringPipelineOptions(enable_style_fingerprint=False)
    pipeline = FeatureEngineeringPipeline(options=options)

    result = pipeline._write_style_fingerprint(
        output_root=tmp_path,
        creator_id="creator-1",
        phrases=(),
        layering_rows=(),
        color_rows=(),
        transition_graph=None,
    )
    assert result is None
    assert not (tmp_path / "style_fingerprint.json").exists()
