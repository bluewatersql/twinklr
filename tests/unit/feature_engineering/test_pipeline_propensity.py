"""Tests for Propensity Miner pipeline integration."""

import json
from pathlib import Path

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


def _make_phrase(target_name: str, effect_family: str, idx: int) -> EffectPhrase:
    return EffectPhrase(
        schema_version="v1.0.0",
        phrase_id=f"ph_{idx}",
        package_id="pkg-1",
        sequence_file_id="seq-1",
        effect_event_id=f"evt_{idx}",
        effect_type="Bars",
        effect_family=effect_family,
        motion_class=MotionClass.SWEEP,
        color_class=ColorClass.PALETTE,
        energy_class=EnergyClass.MID,
        continuity_class=ContinuityClass.SUSTAINED,
        spatial_class=SpatialClass.SINGLE_TARGET,
        source=PhraseSource.EFFECT_TYPE_MAP,
        map_confidence=0.9,
        target_name=target_name,
        layer_index=0,
        start_ms=idx * 1000,
        end_ms=(idx + 1) * 1000,
        duration_ms=1000,
        section_label="verse",
        param_signature="bars|sweep|palette",
    )


def test_pipeline_writes_propensity_when_enabled(tmp_path: Path) -> None:
    """When enable_propensity=True, pipeline writes propensity_index.json."""
    phrases = tuple(
        _make_phrase("MegaTree", "single_strand", i) for i in range(10)
    ) + tuple(
        _make_phrase("Arch", "bars", i + 10) for i in range(5)
    )

    options = FeatureEngineeringPipelineOptions(enable_propensity=True)
    pipeline = FeatureEngineeringPipeline(options=options)

    pipeline._write_propensity(output_root=tmp_path, phrases=phrases)

    output_path = tmp_path / "propensity_index.json"
    assert output_path.exists()
    data = json.loads(output_path.read_text())
    assert data["schema_version"] == "v1.0.0"
    assert len(data["affinities"]) >= 1


def test_pipeline_skips_propensity_when_disabled(tmp_path: Path) -> None:
    """When enable_propensity=False, pipeline does not write propensity_index.json."""
    options = FeatureEngineeringPipelineOptions(enable_propensity=False)
    pipeline = FeatureEngineeringPipeline(options=options)

    result = pipeline._write_propensity(output_root=tmp_path, phrases=())
    assert result is None
    assert not (tmp_path / "propensity_index.json").exists()
