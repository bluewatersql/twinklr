"""Phase 2C: Tests for feature store integration in the feature engineering pipeline."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, call, patch

import pytest

from twinklr.core.feature_engineering.pipeline import (
    FeatureEngineeringPipeline,
    FeatureEngineeringPipelineOptions,
)
from twinklr.core.feature_store.backends.null import NullFeatureStore
from twinklr.core.feature_store.models import FeatureStoreConfig

# ---------------------------------------------------------------------------
# Shared test helpers (mirrored from test_pipeline.py)
# ---------------------------------------------------------------------------


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _write_audio(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"audio")


def _seed_profile(profile_dir: Path, *, effect_type: str = "On") -> None:
    _write_json(
        profile_dir / "sequence_metadata.json",
        {
            "package_id": "pkg-1",
            "sequence_file_id": "seq-1",
            "sequence_sha256": "sha-seq",
            "media_file": "Need A Favor.mp3",
            "song": "Need A Favor",
            "artist": "Jelly Roll",
        },
    )
    _write_json(
        profile_dir / "lineage_index.json",
        {
            "sequence_file": {
                "filename": "Need A Favor.xsq",
            }
        },
    )
    _write_json(
        profile_dir / "enriched_effect_events.json",
        [
            {
                "effect_event_id": "evt-1",
                "target_name": "Tree",
                "layer_index": 0,
                "effect_type": effect_type,
                "start_ms": 0,
                "end_ms": 1000,
            }
        ],
    )


def _write_corpus_index(corpus_dir: Path, profile_dir: Path) -> None:
    corpus_dir.mkdir(parents=True, exist_ok=True)
    (corpus_dir / "sequence_index.jsonl").write_text(
        json.dumps(
            {
                "profile_path": str(profile_dir),
                "package_id": "pkg-1",
                "sequence_file_id": "seq-1",
            }
        )
        + "\n",
        encoding="utf-8",
    )


# ---------------------------------------------------------------------------
# Test 1: Default pipeline uses NullFeatureStore
# ---------------------------------------------------------------------------


def test_default_pipeline_uses_null_store() -> None:
    """Pipeline created with default options should have a NullFeatureStore."""
    pipeline = FeatureEngineeringPipeline()
    assert isinstance(pipeline._store, NullFeatureStore)


# ---------------------------------------------------------------------------
# Test 2: Pipeline with sqlite config gets a non-null store
# ---------------------------------------------------------------------------


def test_pipeline_with_sqlite_config(tmp_path: Path) -> None:
    """Pipeline created with a SQLite config should have a non-NullFeatureStore."""
    config = FeatureStoreConfig(backend="sqlite", db_path=tmp_path / "test.db")
    pipeline = FeatureEngineeringPipeline(
        options=FeatureEngineeringPipelineOptions(feature_store_config=config)
    )
    assert not isinstance(pipeline._store, NullFeatureStore)


# ---------------------------------------------------------------------------
# Test 3: Store lifecycle on run_profile — initialize/close called
# ---------------------------------------------------------------------------


def test_store_lifecycle_on_run_profile(tmp_path: Path) -> None:
    """run_profile must call store.initialize() then store.close() in finally block."""
    profile_dir = tmp_path / "profile"
    output_dir = tmp_path / "out"
    _seed_profile(profile_dir)

    mock_store = MagicMock()

    pipeline = FeatureEngineeringPipeline()
    pipeline._store = mock_store

    pipeline.run_profile(profile_dir, output_dir)

    mock_store.initialize.assert_called_once()
    mock_store.close.assert_called_once()
    # initialize must come before close
    assert mock_store.method_calls.index(call.initialize()) < mock_store.method_calls.index(
        call.close()
    )


# ---------------------------------------------------------------------------
# Test 4: Store lifecycle on run_corpus — initialize/close called
# ---------------------------------------------------------------------------


def test_store_lifecycle_on_run_corpus(tmp_path: Path) -> None:
    """run_corpus must call store.initialize() then store.close() in finally block."""
    profile_dir = tmp_path / "profile"
    corpus_dir = tmp_path / "corpus"
    output_root = tmp_path / "out"
    _seed_profile(profile_dir)
    _write_corpus_index(corpus_dir, profile_dir)

    mock_store = MagicMock()

    pipeline = FeatureEngineeringPipeline()
    pipeline._store = mock_store

    pipeline.run_corpus(corpus_dir, output_root)

    mock_store.initialize.assert_called_once()
    mock_store.close.assert_called_once()


# ---------------------------------------------------------------------------
# Test 5: Store close called on exception in run_profile
# ---------------------------------------------------------------------------


def test_store_close_on_exception(tmp_path: Path) -> None:
    """store.close() must be called even when _run_profile_internal raises."""
    profile_dir = tmp_path / "profile"
    output_dir = tmp_path / "out"
    _seed_profile(profile_dir)

    mock_store = MagicMock()

    pipeline = FeatureEngineeringPipeline()
    pipeline._store = mock_store

    with (
        patch.object(
            pipeline,
            "_run_profile_internal",
            side_effect=RuntimeError("boom"),
        ),
        pytest.raises(RuntimeError, match="boom"),
    ):
        pipeline.run_profile(profile_dir, output_dir)

    mock_store.initialize.assert_called_once()
    mock_store.close.assert_called_once()


# ---------------------------------------------------------------------------
# Test 6: Store close called on exception in run_corpus
# ---------------------------------------------------------------------------


def test_store_close_on_corpus_exception(tmp_path: Path) -> None:
    """store.close() must be called even when run_corpus body raises."""
    profile_dir = tmp_path / "profile"
    corpus_dir = tmp_path / "corpus"
    output_root = tmp_path / "out"
    _seed_profile(profile_dir)
    _write_corpus_index(corpus_dir, profile_dir)

    mock_store = MagicMock()

    pipeline = FeatureEngineeringPipeline()
    pipeline._store = mock_store

    with (
        patch.object(
            pipeline,
            "_run_profile_internal",
            side_effect=RuntimeError("corpus-boom"),
        ),
        pytest.raises(RuntimeError, match="corpus-boom"),
    ):
        pipeline.run_corpus(corpus_dir, output_root)

    mock_store.initialize.assert_called_once()
    mock_store.close.assert_called_once()


# ---------------------------------------------------------------------------
# Test 7: upsert_phrases is called with phrase data
# ---------------------------------------------------------------------------


def test_store_receives_phrase_upserts(tmp_path: Path) -> None:
    """After run_profile, store.upsert_phrases should have been called with phrases."""
    profile_dir = tmp_path / "profile"
    output_dir = tmp_path / "out"
    _seed_profile(profile_dir)

    mock_store = MagicMock()

    pipeline = FeatureEngineeringPipeline()
    pipeline._store = mock_store

    pipeline.run_profile(profile_dir, output_dir)

    # upsert_phrases should have been called at least once
    mock_store.upsert_phrases.assert_called()
    # The first call should have received a non-empty tuple
    phrases_arg = mock_store.upsert_phrases.call_args[0][0]
    assert isinstance(phrases_arg, tuple)
    assert len(phrases_arg) > 0


# ---------------------------------------------------------------------------
# Test 8: upsert_taxonomy is called with taxonomy data
# ---------------------------------------------------------------------------


def test_store_receives_taxonomy_upserts(tmp_path: Path) -> None:
    """After run_profile, store.upsert_taxonomy should have been called with taxonomy rows."""
    profile_dir = tmp_path / "profile"
    output_dir = tmp_path / "out"
    _seed_profile(profile_dir)

    mock_store = MagicMock()

    pipeline = FeatureEngineeringPipeline()
    pipeline._store = mock_store

    pipeline.run_profile(profile_dir, output_dir)

    mock_store.upsert_taxonomy.assert_called()
    taxonomy_arg = mock_store.upsert_taxonomy.call_args[0][0]
    assert isinstance(taxonomy_arg, tuple)


# ---------------------------------------------------------------------------
# Test 9: Corpus run calls upsert_corpus_metadata
# ---------------------------------------------------------------------------


def test_store_receives_corpus_metadata_upsert(tmp_path: Path) -> None:
    """run_corpus should call store.upsert_corpus_metadata once after processing."""
    profile_dir = tmp_path / "profile"
    corpus_dir = tmp_path / "corpus"
    output_root = tmp_path / "out"
    _seed_profile(profile_dir)
    _write_corpus_index(corpus_dir, profile_dir)

    mock_store = MagicMock()

    pipeline = FeatureEngineeringPipeline()
    pipeline._store = mock_store

    pipeline.run_corpus(corpus_dir, output_root)

    mock_store.upsert_corpus_metadata.assert_called_once()
    corpus_id_arg, metadata_json_arg = mock_store.upsert_corpus_metadata.call_args[0]
    assert isinstance(corpus_id_arg, str)
    assert len(corpus_id_arg) > 0
    # metadata_json should be valid JSON
    parsed = json.loads(metadata_json_arg)
    assert "sequence_count" in parsed


# ---------------------------------------------------------------------------
# Test 10: SQLite store integration — phrases are persisted and queryable
# ---------------------------------------------------------------------------


def test_sqlite_store_phrases_persisted(tmp_path: Path) -> None:
    """End-to-end: run_profile with SQLite store should persist phrases queryable by target."""
    profile_dir = tmp_path / "profile"
    output_dir = tmp_path / "out"
    _seed_profile(profile_dir)

    db_path = tmp_path / "feature_store.db"
    config = FeatureStoreConfig(backend="sqlite", db_path=db_path)
    pipeline = FeatureEngineeringPipeline(
        options=FeatureEngineeringPipelineOptions(feature_store_config=config)
    )

    pipeline.run_profile(profile_dir, output_dir)

    # Open a fresh store instance and query back
    from twinklr.core.feature_store.factory import create_feature_store

    store = create_feature_store(config)
    store.initialize()
    try:
        phrases = store.query_phrases_by_target(
            package_id="pkg-1",
            sequence_file_id="seq-1",
            target_name="Tree",
        )
        assert len(phrases) > 0
        assert all(p.package_id == "pkg-1" for p in phrases)
        assert all(p.sequence_file_id == "seq-1" for p in phrases)
        assert all(p.target_name == "Tree" for p in phrases)
    finally:
        store.close()
