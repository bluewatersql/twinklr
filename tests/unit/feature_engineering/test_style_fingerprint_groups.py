"""Tests for owner-declared style-group fingerprint extraction."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, cast

import pytest

from twinklr.core.agents.sequencer.group_planner.stage import GroupPlannerStage
from twinklr.core.feature_engineering.component_factory import ComponentFactory
from twinklr.core.feature_engineering.config import FeatureEngineeringPipelineOptions
from twinklr.core.feature_engineering.corpus_artifacts import (
    write_style_group_fingerprints,
)
from twinklr.core.feature_engineering.datasets.writer import FeatureEngineeringWriter
from twinklr.core.feature_engineering.loader import load_fe_artifacts
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
from twinklr.core.feature_engineering.style_groups import (
    StyleGroupDeclaration,
    load_style_group_declaration,
)


def _phrase(package_id: str, sequence_id: str, index: int) -> EffectPhrase:
    return EffectPhrase(
        schema_version="v1.0.0",
        phrase_id=f"{package_id}-{index}",
        package_id=package_id,
        sequence_file_id=sequence_id,
        effect_event_id=f"event-{package_id}-{index}",
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
        start_ms=index * 1000,
        end_ms=(index + 1) * 1000,
        duration_ms=1000,
        section_label="verse",
        param_signature="bars|sweep|palette",
    )


def _declaration() -> StyleGroupDeclaration:
    return StyleGroupDeclaration.model_validate(
        {
            "schema_version": "twinklr.style-groups.v1",
            "groups": [
                {"style_name": "Warm Pop", "selector": {"package_ids": ["pack-warm"]}},
                {
                    "style_name": "Sparse",
                    "selector": {"sequence_keys": ["pack-sparse/seq-sparse"]},
                },
            ],
        }
    )


def _layering(package_id: str, sequence_id: str) -> LayeringFeatureRow:
    return LayeringFeatureRow(
        schema_version="v1.7.0",
        package_id=package_id,
        sequence_file_id=sequence_id,
        phrase_count=3,
        max_concurrent_layers=2,
        mean_concurrent_layers=1.5,
        hierarchy_transitions=1,
        overlap_pairs=1,
        same_target_overlap_pairs=0,
        collision_score=0.1,
    )


def _color(package_id: str, sequence_id: str) -> ColorNarrativeRow:
    return ColorNarrativeRow(
        schema_version="v1.8.0",
        package_id=package_id,
        sequence_file_id=sequence_id,
        section_label="verse",
        section_index=0,
        phrase_count=3,
        dominant_color_class="palette",
        contrast_shift_from_prev=0.2,
        hue_family_movement="hold",
    )


def test_missing_owner_declaration_fails_loudly(tmp_path: Path) -> None:
    """A real grouped refresh cannot silently omit the owner's declaration."""
    with pytest.raises(FileNotFoundError, match="style-group declaration"):
        load_style_group_declaration(tmp_path / "missing.json")


def test_group_fingerprints_are_partitioned_named_and_flag_thin(tmp_path: Path) -> None:
    """Declared groups produce partitioned artifacts and an inspectable confidence report."""
    options = FeatureEngineeringPipelineOptions()
    warm = tuple(_phrase("pack-warm", "seq-warm", index) for index in range(3)) + tuple(
        _phrase("pack-warm", "seq-warm-2", index + 3) for index in range(3)
    )
    sparse = (_phrase("pack-sparse", "seq-sparse", 0),)

    result = write_style_group_fingerprints(
        output_root=tmp_path,
        declaration=_declaration(),
        phrases=warm + sparse,
        layering_rows=(
            _layering("pack-warm", "seq-warm"),
            _layering("pack-warm", "seq-warm-2"),
            _layering("pack-sparse", "seq-sparse"),
        ),
        color_rows=(
            _color("pack-warm", "seq-warm"),
            _color("pack-warm", "seq-warm-2"),
            _color("pack-sparse", "seq-sparse"),
        ),
        transition_graph=None,
        options=options,
        writer=FeatureEngineeringWriter(),
        components=ComponentFactory(options),
    )

    assert set(result.artifact_paths) == {"Warm Pop", "Sparse"}
    assert (tmp_path / "style_fingerprint_warm_pop.json").exists()
    warm_data = json.loads((tmp_path / "style_fingerprint_warm_pop.json").read_text())
    assert warm_data["creator_id"] == "Warm Pop"
    assert warm_data["corpus_sequence_count"] == 2
    report = json.loads(result.report_path.read_text())
    by_style = {row["style_name"]: row for row in report["styles"]}
    assert by_style["Sparse"]["thin"] is True
    assert by_style["Warm Pop"]["thin"] is False


def test_loader_selects_named_group_and_stage_serializes_both_halves(tmp_path: Path) -> None:
    """Named grouped style plus propensity reach the existing planner-context reader."""
    options = FeatureEngineeringPipelineOptions()
    phrases = tuple(_phrase("pack-warm", "seq-warm", index) for index in range(3))
    result = write_style_group_fingerprints(
        output_root=tmp_path,
        declaration=StyleGroupDeclaration.model_validate(
            {
                "schema_version": "twinklr.style-groups.v1",
                "groups": [{"style_name": "Warm Pop", "selector": {"package_ids": ["pack-warm"]}}],
            }
        ),
        phrases=phrases,
        layering_rows=(_layering("pack-warm", "seq-warm"),),
        color_rows=(_color("pack-warm", "seq-warm"),),
        transition_graph=None,
        options=options,
        writer=FeatureEngineeringWriter(),
        components=ComponentFactory(options),
    )
    propensity = ComponentFactory(options).propensity_miner.mine(phrases=phrases)
    propensity_path = tmp_path / "propensity_index.json"
    FeatureEngineeringWriter()._write_json(propensity_path, propensity.model_dump(mode="json"))
    (tmp_path / "feature_store_manifest.json").write_text(
        json.dumps(
            {
                "propensity_index": str(propensity_path),
                "style_fingerprints": {
                    name: str(path) for name, path in result.artifact_paths.items()
                },
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match=r"style_name is required.*Warm Pop"):
        load_fe_artifacts(tmp_path)
    bundle = load_fe_artifacts(tmp_path, style_name="Warm Pop")
    assert bundle.propensity_index is not None
    assert bundle.propensity_index.affinities
    assert bundle.style_fingerprint is not None
    stage = GroupPlannerStage(cast("Any", object()), cast("Any", object()), fe_bundle=bundle)
    fields = stage._extract_fe_fields(section_id="verse_1")
    assert fields["propensity_hints"]["affinities"]
    assert fields["style_constraints"]["timing_style"]


def test_explicit_group_selection_fails_when_artifact_is_missing(tmp_path: Path) -> None:
    """An explicit owner selection cannot degrade to an empty style bundle."""
    (tmp_path / "feature_store_manifest.json").write_text(
        json.dumps({"style_fingerprints": {"Warm Pop": "missing.json"}}),
        encoding="utf-8",
    )

    with pytest.raises(FileNotFoundError, match=r"Warm Pop.*was not found"):
        load_fe_artifacts(tmp_path, style_name="Warm Pop")


def test_explicit_group_selection_fails_when_artifact_is_invalid(tmp_path: Path) -> None:
    """Malformed selected content is an actionable error rather than a warning."""
    invalid = tmp_path / "style_fingerprint_warm_pop.json"
    invalid.write_text("not JSON", encoding="utf-8")
    (tmp_path / "feature_store_manifest.json").write_text(
        json.dumps({"style_fingerprints": {"Warm Pop": str(invalid)}}),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match=r"Warm Pop.*is invalid"):
        load_fe_artifacts(tmp_path, style_name="Warm Pop")
