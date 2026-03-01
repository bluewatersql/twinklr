"""Tests for ArtifactWriter — CQ-01 extracted write logic."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING
from unittest.mock import MagicMock

from twinklr.core.feature_engineering.artifact_writer import ArtifactWriter
from twinklr.core.feature_engineering.datasets.writer import FeatureEngineeringWriter
from twinklr.core.feature_engineering.models import (
    EffectPhrase,
)
from twinklr.core.feature_engineering.models.phrases import (
    ColorClass,
    ContinuityClass,
    EnergyClass,
    MotionClass,
    PhraseSource,
    SpatialClass,
)

if TYPE_CHECKING:
    from twinklr.core.feature_engineering.models import (
        AlignedEffectEvent,
        PhraseTaxonomyRecord,
        TargetRoleAssignment,
    )
    from twinklr.core.feature_engineering.models.color_narrative import ColorNarrativeRow
    from twinklr.core.feature_engineering.models.layering import LayeringFeatureRow

# ---------------------------------------------------------------------------
# Helpers — minimal valid model construction
# ---------------------------------------------------------------------------


def _make_phrase(
    phrase_id: str = "ph-1",
    effect_family: str = "utility",
    motion_class: MotionClass = MotionClass.STATIC,
) -> EffectPhrase:
    return EffectPhrase(
        schema_version="v1.0.0",
        phrase_id=phrase_id,
        package_id="pkg-1",
        sequence_file_id="seq-1",
        effect_event_id="evt-1",
        effect_type="On",
        effect_family=effect_family,
        motion_class=motion_class,
        color_class=ColorClass.MONO,
        energy_class=EnergyClass.LOW,
        continuity_class=ContinuityClass.SUSTAINED,
        spatial_class=SpatialClass.SINGLE_TARGET,
        source=PhraseSource.EFFECT_TYPE_MAP,
        map_confidence=0.9,
        target_name="Tree",
        layer_index=0,
        start_ms=0,
        end_ms=1000,
        duration_ms=1000,
        param_signature="{}",
    )


# ---------------------------------------------------------------------------
# ArtifactWriter construction
# ---------------------------------------------------------------------------


class TestArtifactWriterConstruction:
    """ArtifactWriter can be constructed with or without a writer."""

    def test_default_construction(self) -> None:
        writer = ArtifactWriter()
        assert writer is not None

    def test_custom_writer_injection(self) -> None:
        inner = FeatureEngineeringWriter()
        writer = ArtifactWriter(writer=inner)
        assert writer is not None

    def test_inner_property_returns_writer(self) -> None:
        inner = FeatureEngineeringWriter()
        writer = ArtifactWriter(writer=inner)
        assert writer.inner is inner


# ---------------------------------------------------------------------------
# write_aligned_events — delegates to inner writer
# ---------------------------------------------------------------------------


class TestWriteAlignedEvents:
    """ArtifactWriter.write_aligned_events delegates to FeatureEngineeringWriter."""

    def test_delegates_to_inner_writer(self, tmp_path: Path) -> None:
        inner = MagicMock(spec=FeatureEngineeringWriter)
        inner.write_aligned_events.return_value = tmp_path / "aligned_events.jsonl"
        writer = ArtifactWriter(writer=inner)
        events: tuple[AlignedEffectEvent, ...] = ()
        result = writer.write_aligned_events(tmp_path, events)
        inner.write_aligned_events.assert_called_once_with(tmp_path, events)
        assert result == tmp_path / "aligned_events.jsonl"


# ---------------------------------------------------------------------------
# write_effect_phrases — delegates to inner writer
# ---------------------------------------------------------------------------


class TestWriteEffectPhrases:
    """ArtifactWriter.write_effect_phrases delegates to FeatureEngineeringWriter."""

    def test_delegates_to_inner_writer(self, tmp_path: Path) -> None:
        inner = MagicMock(spec=FeatureEngineeringWriter)
        inner.write_effect_phrases.return_value = tmp_path / "effect_phrases.jsonl"
        writer = ArtifactWriter(writer=inner)
        phrases: tuple[EffectPhrase, ...] = ()
        result = writer.write_effect_phrases(tmp_path, phrases)
        inner.write_effect_phrases.assert_called_once_with(tmp_path, phrases)
        assert result == tmp_path / "effect_phrases.jsonl"


# ---------------------------------------------------------------------------
# write_phrase_taxonomy — delegates to inner writer
# ---------------------------------------------------------------------------


class TestWritePhraseTaxonomy:
    """ArtifactWriter.write_phrase_taxonomy delegates to FeatureEngineeringWriter."""

    def test_delegates_to_inner_writer(self, tmp_path: Path) -> None:
        inner = MagicMock(spec=FeatureEngineeringWriter)
        inner.write_phrase_taxonomy.return_value = tmp_path / "phrase_taxonomy.jsonl"
        writer = ArtifactWriter(writer=inner)
        rows: tuple[PhraseTaxonomyRecord, ...] = ()
        result = writer.write_phrase_taxonomy(tmp_path, rows)
        inner.write_phrase_taxonomy.assert_called_once_with(tmp_path, rows)
        assert result == tmp_path / "phrase_taxonomy.jsonl"


# ---------------------------------------------------------------------------
# write_target_roles — delegates to inner writer
# ---------------------------------------------------------------------------


class TestWriteTargetRoles:
    """ArtifactWriter.write_target_roles delegates to FeatureEngineeringWriter."""

    def test_delegates_to_inner_writer(self, tmp_path: Path) -> None:
        inner = MagicMock(spec=FeatureEngineeringWriter)
        inner.write_target_roles.return_value = tmp_path / "target_roles.jsonl"
        writer = ArtifactWriter(writer=inner)
        rows: tuple[TargetRoleAssignment, ...] = ()
        result = writer.write_target_roles(tmp_path, rows)
        inner.write_target_roles.assert_called_once_with(tmp_path, rows)
        assert result == tmp_path / "target_roles.jsonl"


# ---------------------------------------------------------------------------
# write_layering_features — delegates to inner writer
# ---------------------------------------------------------------------------


class TestWriteLayeringFeatures:
    """ArtifactWriter.write_layering_features delegates to FeatureEngineeringWriter."""

    def test_delegates_to_inner_writer(self, tmp_path: Path) -> None:
        inner = MagicMock(spec=FeatureEngineeringWriter)
        inner.write_layering_features.return_value = tmp_path / "layering_features.jsonl"
        writer = ArtifactWriter(writer=inner)
        rows: tuple[LayeringFeatureRow, ...] = ()
        result = writer.write_layering_features(tmp_path, rows)
        inner.write_layering_features.assert_called_once_with(tmp_path, rows)
        assert result == tmp_path / "layering_features.jsonl"


# ---------------------------------------------------------------------------
# write_color_narrative — delegates to inner writer
# ---------------------------------------------------------------------------


class TestWriteColorNarrative:
    """ArtifactWriter.write_color_narrative delegates to FeatureEngineeringWriter."""

    def test_delegates_to_inner_writer(self, tmp_path: Path) -> None:
        inner = MagicMock(spec=FeatureEngineeringWriter)
        inner.write_color_narrative.return_value = tmp_path / "color_narrative.jsonl"
        writer = ArtifactWriter(writer=inner)
        rows: tuple[ColorNarrativeRow, ...] = ()
        result = writer.write_color_narrative(tmp_path, rows)
        inner.write_color_narrative.assert_called_once_with(tmp_path, rows)
        assert result == tmp_path / "color_narrative.jsonl"


# ---------------------------------------------------------------------------
# build_unknown_diagnostics — pure logic test
# ---------------------------------------------------------------------------


class TestBuildUnknownDiagnostics:
    """ArtifactWriter.build_unknown_diagnostics computes correct diagnostics."""

    def test_empty_phrases(self) -> None:
        writer = ArtifactWriter()
        data = writer.build_unknown_diagnostics(())
        assert data["total_phrase_count"] == 0
        assert data["unknown_effect_family_count"] == 0
        assert data["unknown_motion_count"] == 0

    def test_known_phrase_not_counted(self) -> None:
        writer = ArtifactWriter()
        phrase = _make_phrase(effect_family="utility", motion_class=MotionClass.STATIC)
        data = writer.build_unknown_diagnostics((phrase,))
        assert data["total_phrase_count"] == 1
        assert data["unknown_effect_family_count"] == 0
        assert data["unknown_motion_count"] == 0

    def test_unknown_family_counted(self) -> None:
        writer = ArtifactWriter()
        phrase = _make_phrase(effect_family="unknown", motion_class=MotionClass.UNKNOWN)
        data = writer.build_unknown_diagnostics((phrase,))
        assert data["unknown_effect_family_count"] == 1
        assert data["unknown_motion_count"] == 1
        assert len(data["top_unknown_effect_types"]) == 1
        assert data["top_unknown_effect_types"][0]["effect_type"] == "On"

    def test_schema_version_present(self) -> None:
        writer = ArtifactWriter()
        data = writer.build_unknown_diagnostics(())
        assert data["schema_version"] == "v1.0.0"


# ---------------------------------------------------------------------------
# write_unknown_diagnostics — writes JSON to disk
# ---------------------------------------------------------------------------


class TestWriteUnknownDiagnostics:
    """ArtifactWriter.write_unknown_diagnostics writes diagnostics JSON."""

    def test_writes_json_file(self, tmp_path: Path) -> None:
        inner = MagicMock(spec=FeatureEngineeringWriter)
        inner.write_unknown_diagnostics.return_value = tmp_path / "unknown_diagnostics.json"
        writer = ArtifactWriter(writer=inner)
        phrases = (_make_phrase(),)
        path = writer.write_unknown_diagnostics(tmp_path, phrases)
        inner.write_unknown_diagnostics.assert_called_once()
        # First arg is output_root, second is the built dict
        call_args = inner.write_unknown_diagnostics.call_args
        assert call_args[0][0] == tmp_path
        assert isinstance(call_args[0][1], dict)
        assert "total_phrase_count" in call_args[0][1]
        assert path == tmp_path / "unknown_diagnostics.json"


# ---------------------------------------------------------------------------
# File size guard
# ---------------------------------------------------------------------------


class TestArtifactWriterFileSize:
    """artifact_writer.py must be under 500 lines."""

    def test_file_size(self) -> None:
        repo_root = Path(__file__).parents[3]
        src = repo_root / "packages/twinklr/core/feature_engineering/artifact_writer.py"
        lines = len(src.read_text().splitlines())
        assert lines < 500, f"artifact_writer.py is {lines} lines (must be < 500)"
