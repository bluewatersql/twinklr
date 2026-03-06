"""Tests for STAB-02: corpus tail recompute with full profile data."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

from twinklr.core.feature_engineering.models import (
    EffectPhrase,
    PhraseTaxonomyRecord,
    TargetRoleAssignment,
)
from twinklr.core.feature_engineering.pipeline import FeatureEngineeringPipeline


def _make_phrase(phrase_id: str, package_id: str = "pkg_a") -> EffectPhrase:
    return EffectPhrase(
        schema_version="1.0",
        phrase_id=phrase_id,
        package_id=package_id,
        sequence_file_id="seq_1",
        effect_event_id=f"evt_{phrase_id}",
        effect_type="chase",
        effect_family="MOTION",
        motion_class="sweep",
        color_class="mono",
        energy_class="mid",
        continuity_class="sustained",
        spatial_class="single_target",
        source="effect_type_map",
        map_confidence=0.9,
        target_name="Arch1",
        layer_index=0,
        start_ms=0,
        end_ms=1000,
        duration_ms=1000,
        param_signature="chase::sweep",
    )


def _make_taxonomy(phrase_id: str, package_id: str = "pkg_a") -> PhraseTaxonomyRecord:
    return PhraseTaxonomyRecord(
        schema_version="1.0",
        classifier_version="1.0",
        phrase_id=phrase_id,
        package_id=package_id,
        sequence_file_id="seq_1",
        effect_event_id=f"evt_{phrase_id}",
    )


def _make_role(target_id: str, package_id: str = "pkg_a") -> TargetRoleAssignment:
    return TargetRoleAssignment(
        schema_version="1.0",
        role_engine_version="1.0",
        package_id=package_id,
        sequence_file_id="seq_1",
        target_id=target_id,
        target_name=f"Target_{target_id}",
        target_kind="model",
        role="lead",
        role_confidence=0.8,
        role_binding_key=f"{target_id}::model",
        event_count=10,
        active_duration_ms=5000,
    )


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    """Write rows as JSONL file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")


class TestLoadProfileArtifacts:
    """Test _load_profile_artifacts reads from completed profile dirs."""

    def test_reads_jsonl_artifacts(self, tmp_path: Path) -> None:
        """JSONL artifact files are loaded and parsed into model instances."""
        phrase = _make_phrase("ph1")
        taxonomy = _make_taxonomy("ph1")
        role = _make_role("t1")

        _write_jsonl(
            tmp_path / "effect_phrases.jsonl",
            [phrase.model_dump(mode="json")],
        )
        _write_jsonl(
            tmp_path / "phrase_taxonomy.jsonl",
            [taxonomy.model_dump(mode="json")],
        )
        _write_jsonl(
            tmp_path / "target_roles.jsonl",
            [role.model_dump(mode="json")],
        )

        pipeline = FeatureEngineeringPipeline()
        result = pipeline._load_profile_artifacts(tmp_path)

        assert result is not None
        phrases, tax_rows, roles = result
        assert len(phrases) == 1
        assert phrases[0].phrase_id == "ph1"
        assert len(tax_rows) == 1
        assert tax_rows[0].phrase_id == "ph1"
        assert len(roles) == 1
        assert roles[0].target_id == "t1"

    def test_missing_files_returns_none(self, tmp_path: Path) -> None:
        """Returns None when artifact files are absent."""
        pipeline = FeatureEngineeringPipeline()
        result = pipeline._load_profile_artifacts(tmp_path)
        assert result is None

    def test_partial_files_returns_available(self, tmp_path: Path) -> None:
        """Returns available artifacts even when some files are missing."""
        phrase = _make_phrase("ph2")
        _write_jsonl(
            tmp_path / "effect_phrases.jsonl",
            [phrase.model_dump(mode="json")],
        )

        pipeline = FeatureEngineeringPipeline()
        result = pipeline._load_profile_artifacts(tmp_path)

        assert result is not None
        phrases, tax_rows, roles = result
        assert len(phrases) == 1
        assert len(tax_rows) == 0
        assert len(roles) == 0


class TestRunMergesCachedArtifacts:
    """Test that run() merges cached + new artifacts for _finalize_corpus."""

    def test_finalize_receives_all_artifacts(self, tmp_path: Path) -> None:
        """_finalize_corpus gets merged cached + new artifacts."""
        cached_phrase = _make_phrase("cached_ph", package_id="pkg_cached")
        cached_taxonomy = _make_taxonomy("cached_ph", package_id="pkg_cached")
        cached_role = _make_role("cached_t", package_id="pkg_cached")

        # Write cached profile artifacts
        cached_dir = tmp_path / "pkg_cached" / "seq_1"
        _write_jsonl(
            cached_dir / "effect_phrases.jsonl",
            [cached_phrase.model_dump(mode="json")],
        )
        _write_jsonl(
            cached_dir / "phrase_taxonomy.jsonl",
            [cached_taxonomy.model_dump(mode="json")],
        )
        _write_jsonl(
            cached_dir / "target_roles.jsonl",
            [cached_role.model_dump(mode="json")],
        )
        # Write a minimal feature_bundle.json for _load_existing_bundles
        (cached_dir / "feature_bundle.json").write_text(
            json.dumps(
                {
                    "schema_version": "1.0",
                    "source_profile_path": str(cached_dir),
                    "package_id": "pkg_cached",
                    "sequence_file_id": "seq_1",
                    "sequence_sha256": "abc123",
                    "song": "Test Song",
                    "artist": "Test Artist",
                    "audio": {
                        "audio_path": None,
                        "audio_status": "missing",
                    },
                }
            ),
            encoding="utf-8",
        )

        from twinklr.core.feature_store.models import ProfileRecord

        completed_prof = ProfileRecord(
            profile_id="pkg_cached/seq_1",
            package_id="pkg_cached",
            sequence_file_id="seq_1",
            profile_path=str(cached_dir),
            fe_status="complete",
        )
        pending_prof = ProfileRecord(
            profile_id="pkg_new/seq_2",
            package_id="pkg_new",
            sequence_file_id="seq_2",
            profile_path="/fake/new",
            fe_status="pending",
        )

        new_phrase = _make_phrase("new_ph", package_id="pkg_new")
        new_taxonomy = _make_taxonomy("new_ph", package_id="pkg_new")
        new_role = _make_role("new_t", package_id="pkg_new")

        from twinklr.core.feature_engineering.models import FeatureBundle
        from twinklr.core.feature_engineering.models.bundle import (
            AudioDiscoveryResult,
        )
        from twinklr.core.feature_engineering.pipeline import _ProfileOutputs

        new_bundle = FeatureBundle(
            schema_version="1.0",
            source_profile_path="/fake/new",
            package_id="pkg_new",
            sequence_file_id="seq_2",
            sequence_sha256="def456",
            song="New Song",
            artist="New Artist",
            audio=AudioDiscoveryResult(
                audio_path=None,
                audio_status="missing",
            ),
        )
        new_outputs = _ProfileOutputs(
            bundle=new_bundle,
            phrases=(new_phrase,),
            taxonomy_rows=(new_taxonomy,),
            target_roles=(new_role,),
        )

        mock_store = MagicMock()
        mock_store.query_profiles.side_effect = lambda fe_status=None: {
            "complete": (completed_prof,),
            "pending": (pending_prof,),
        }.get(fe_status, ())

        pipeline = FeatureEngineeringPipeline()
        pipeline._store = mock_store

        with (
            patch.object(pipeline, "_run_profile_internal", return_value=new_outputs),
            patch.object(pipeline, "_finalize_corpus") as mock_finalize,
        ):
            pipeline.run(tmp_path)

        mock_finalize.assert_called_once()
        call_args = mock_finalize.call_args
        # args: output_root, corpus_id, bundles, phrases, taxonomy, roles
        all_phrases = call_args[0][3]
        all_taxonomy = call_args[0][4]
        all_roles = call_args[0][5]

        # Should contain BOTH cached and new artifacts
        assert len(all_phrases) == 2
        phrase_ids = {p.phrase_id for p in all_phrases}
        assert "cached_ph" in phrase_ids
        assert "new_ph" in phrase_ids

        assert len(all_taxonomy) == 2
        assert len(all_roles) == 2

    def test_no_pending_skips_finalize(self, tmp_path: Path) -> None:
        """Zero pending profiles → _finalize_corpus not called."""
        mock_store = MagicMock()
        mock_store.query_profiles.side_effect = lambda fe_status=None: {
            "complete": (),
            "pending": (),
        }.get(fe_status, ())

        pipeline = FeatureEngineeringPipeline()
        pipeline._store = mock_store

        with patch.object(pipeline, "_finalize_corpus") as mock_finalize:
            pipeline.run(tmp_path)

        mock_finalize.assert_not_called()
