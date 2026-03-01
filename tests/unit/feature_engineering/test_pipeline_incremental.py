"""Tests for store-driven incremental feature engineering (Phase 03)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING
from unittest.mock import MagicMock, patch

import pytest

from twinklr.core.feature_engineering.models.bundle import (
    AudioDiscoveryResult,
    AudioStatus,
    FeatureBundle,
)
from twinklr.core.feature_engineering.pipeline import (
    FeatureEngineeringPipeline,
    FeatureEngineeringPipelineOptions,
    _ProfileOutputs,
)
from twinklr.core.feature_store.factory import create_feature_store
from twinklr.core.feature_store.models import FeatureStoreConfig, ProfileRecord

if TYPE_CHECKING:
    from twinklr.core.feature_store.backends.sqlite import SQLiteFeatureStore


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_audio() -> AudioDiscoveryResult:
    return AudioDiscoveryResult(
        audio_path=None,
        audio_status=AudioStatus.MISSING,
    )


def _make_bundle(package_id: str = "pkg-a", sequence_file_id: str = "seq-1") -> FeatureBundle:
    return FeatureBundle(
        schema_version="v1.0.0",
        source_profile_path=f"/fake/{package_id}/{sequence_file_id}",
        package_id=package_id,
        sequence_file_id=sequence_file_id,
        sequence_sha256="abc123",
        song="Test Song",
        artist="Test Artist",
        audio=_make_audio(),
    )


def _make_profile_outputs(
    package_id: str = "pkg-a", sequence_file_id: str = "seq-1"
) -> _ProfileOutputs:
    return _ProfileOutputs(
        bundle=_make_bundle(package_id, sequence_file_id),
        phrases=(),
        taxonomy_rows=(),
        target_roles=(),
    )


def _make_profile_record(
    package_id: str = "pkg-a",
    sequence_file_id: str = "seq-1",
    fe_status: str = "pending",
    profile_path: str = "/fake/profile",
) -> ProfileRecord:
    return ProfileRecord(
        profile_id=f"{package_id}/{sequence_file_id}",
        package_id=package_id,
        sequence_file_id=sequence_file_id,
        profile_path=profile_path,
        fe_status=fe_status,
    )


def _write_feature_bundle(output_root: Path, profile: ProfileRecord) -> Path:
    """Write a fake feature_bundle.json for a completed profile."""
    bundle = _make_bundle(profile.package_id, profile.sequence_file_id)
    out_dir = output_root / profile.package_id / profile.sequence_file_id
    out_dir.mkdir(parents=True, exist_ok=True)
    bundle_path = out_dir / "feature_bundle.json"
    bundle_path.write_text(json.dumps(bundle.model_dump(mode="json")), encoding="utf-8")
    return bundle_path


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def sqlite_store(tmp_path: Path) -> SQLiteFeatureStore:  # type: ignore[misc]
    cfg = FeatureStoreConfig(backend="sqlite", db_path=tmp_path / "fe.db")
    store = create_feature_store(cfg)
    store.initialize()
    try:
        yield store  # type: ignore[misc]
    finally:
        store.close()


@pytest.fixture
def pipeline_with_store(tmp_path: Path) -> FeatureEngineeringPipeline:
    cfg = FeatureStoreConfig(backend="sqlite", db_path=tmp_path / "fe.db")
    opts = FeatureEngineeringPipelineOptions(feature_store_config=cfg, fail_fast=True)
    return FeatureEngineeringPipeline(options=opts)


# ---------------------------------------------------------------------------
# Test 1: run() with no pending profiles — returns cached bundles, no processing
# ---------------------------------------------------------------------------


def test_run_no_pending_profiles(tmp_path: Path) -> None:
    """run() with all complete profiles returns loaded bundles without calling _run_profile_internal."""
    cfg = FeatureStoreConfig(backend="sqlite", db_path=tmp_path / "fe.db")
    opts = FeatureEngineeringPipelineOptions(feature_store_config=cfg, fail_fast=True)
    pipeline = FeatureEngineeringPipeline(options=opts)

    # Set up store with 2 complete profiles
    store = create_feature_store(cfg)
    store.initialize()
    p1 = _make_profile_record("pkg-a", "seq-1", fe_status="complete")
    p2 = _make_profile_record("pkg-b", "seq-2", fe_status="complete")
    store.upsert_profile(p1)
    store.upsert_profile(p2)
    store.close()

    # Write feature_bundle.json for each
    output_root = tmp_path / "out"
    _write_feature_bundle(output_root, p1)
    _write_feature_bundle(output_root, p2)

    mock_internal = MagicMock()
    with patch.object(pipeline, "_run_profile_internal", mock_internal):
        bundles = pipeline.run(output_root)

    mock_internal.assert_not_called()
    assert len(bundles) == 2
    pkg_ids = {b.package_id for b in bundles}
    assert pkg_ids == {"pkg-a", "pkg-b"}


# ---------------------------------------------------------------------------
# Test 2: run() processes pending profiles and marks complete
# ---------------------------------------------------------------------------


def test_run_processes_pending(tmp_path: Path) -> None:
    """run() calls _run_profile_internal for pending profiles and marks them complete."""
    cfg = FeatureStoreConfig(backend="sqlite", db_path=tmp_path / "fe.db")
    opts = FeatureEngineeringPipelineOptions(feature_store_config=cfg, fail_fast=True)
    pipeline = FeatureEngineeringPipeline(options=opts)

    store = create_feature_store(cfg)
    store.initialize()
    p1 = _make_profile_record("pkg-a", "seq-1", fe_status="pending")
    store.upsert_profile(p1)
    store.close()

    output_root = tmp_path / "out"
    fake_outputs = _make_profile_outputs("pkg-a", "seq-1")

    with patch.object(pipeline, "_run_profile_internal", return_value=fake_outputs):
        bundles = pipeline.run(output_root)

    assert len(bundles) == 1
    assert bundles[0].package_id == "pkg-a"

    # Verify the profile is now marked complete in the store
    store2 = create_feature_store(cfg)
    store2.initialize()
    complete = store2.query_profiles(fe_status="complete")
    store2.close()
    assert len(complete) == 1
    assert complete[0].profile_id == "pkg-a/seq-1"


# ---------------------------------------------------------------------------
# Test 3: run() marks profile as error when _run_profile_internal raises
# ---------------------------------------------------------------------------


def test_run_marks_error_on_failure(tmp_path: Path) -> None:
    """run() marks a profile as error when _run_profile_internal raises."""
    cfg = FeatureStoreConfig(backend="sqlite", db_path=tmp_path / "fe.db")
    opts = FeatureEngineeringPipelineOptions(feature_store_config=cfg, fail_fast=False)
    pipeline = FeatureEngineeringPipeline(options=opts)

    store = create_feature_store(cfg)
    store.initialize()
    p1 = _make_profile_record("pkg-a", "seq-1", fe_status="pending")
    store.upsert_profile(p1)
    store.close()

    output_root = tmp_path / "out"

    with patch.object(
        pipeline, "_run_profile_internal", side_effect=RuntimeError("processing failed")
    ):
        bundles = pipeline.run(output_root)

    # No bundles returned for failed profiles
    assert bundles == []

    # Profile is marked error
    store2 = create_feature_store(cfg)
    store2.initialize()
    error_profiles = store2.query_profiles(fe_status="error")
    store2.close()
    assert len(error_profiles) == 1
    assert error_profiles[0].profile_id == "pkg-a/seq-1"
    assert error_profiles[0].fe_error is not None
    assert "processing failed" in error_profiles[0].fe_error


# ---------------------------------------------------------------------------
# Test 4: run() with fail_fast=True re-raises on processing error
# ---------------------------------------------------------------------------


def test_run_fail_fast_true(tmp_path: Path) -> None:
    """run() with fail_fast=True re-raises exceptions from _run_profile_internal."""
    cfg = FeatureStoreConfig(backend="sqlite", db_path=tmp_path / "fe.db")
    opts = FeatureEngineeringPipelineOptions(feature_store_config=cfg, fail_fast=True)
    pipeline = FeatureEngineeringPipeline(options=opts)

    store = create_feature_store(cfg)
    store.initialize()
    p1 = _make_profile_record("pkg-a", "seq-1", fe_status="pending")
    store.upsert_profile(p1)
    store.close()

    output_root = tmp_path / "out"

    with (
        patch.object(
            pipeline, "_run_profile_internal", side_effect=RuntimeError("fail fast trigger")
        ),
        pytest.raises(RuntimeError, match="fail fast trigger"),
    ):
        pipeline.run(output_root)


# ---------------------------------------------------------------------------
# Test 5: run() with fail_fast=False continues past errors
# ---------------------------------------------------------------------------


def test_run_fail_fast_false(tmp_path: Path) -> None:
    """run() with fail_fast=False continues processing and marks errors without raising."""
    cfg = FeatureStoreConfig(backend="sqlite", db_path=tmp_path / "fe.db")
    opts = FeatureEngineeringPipelineOptions(feature_store_config=cfg, fail_fast=False)
    pipeline = FeatureEngineeringPipeline(options=opts)

    store = create_feature_store(cfg)
    store.initialize()
    p1 = _make_profile_record("pkg-a", "seq-1", fe_status="pending")
    p2 = _make_profile_record("pkg-b", "seq-2", fe_status="pending")
    store.upsert_profile(p1)
    store.upsert_profile(p2)
    store.close()

    output_root = tmp_path / "out"
    good_outputs = _make_profile_outputs("pkg-b", "seq-2")

    call_count = 0

    def side_effect(profile_dir: Path, output_dir: Path) -> _ProfileOutputs:
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            raise RuntimeError("first profile fails")
        return good_outputs

    with patch.object(pipeline, "_run_profile_internal", side_effect=side_effect):
        bundles = pipeline.run(output_root)

    # Should not raise; returns bundles for the successful profile only
    assert len(bundles) == 1

    store2 = create_feature_store(cfg)
    store2.initialize()
    error_profiles = store2.query_profiles(fe_status="error")
    complete_profiles = store2.query_profiles(fe_status="complete")
    store2.close()
    assert len(error_profiles) == 1
    assert len(complete_profiles) == 1


# ---------------------------------------------------------------------------
# Test 6: run(force=True) resets all to pending and reprocesses
# ---------------------------------------------------------------------------


def test_run_force_reprocesses_all(tmp_path: Path) -> None:
    """run(force=True) resets all complete profiles to pending and reprocesses them."""
    cfg = FeatureStoreConfig(backend="sqlite", db_path=tmp_path / "fe.db")
    opts = FeatureEngineeringPipelineOptions(feature_store_config=cfg, fail_fast=True)
    pipeline = FeatureEngineeringPipeline(options=opts)

    store = create_feature_store(cfg)
    store.initialize()
    p1 = _make_profile_record("pkg-a", "seq-1", fe_status="complete")
    p2 = _make_profile_record("pkg-b", "seq-2", fe_status="complete")
    store.upsert_profile(p1)
    store.upsert_profile(p2)
    store.close()

    output_root = tmp_path / "out"
    call_args: list[tuple[Path, Path]] = []

    def capturing_side_effect(profile_dir: Path, output_dir: Path) -> _ProfileOutputs:
        call_args.append((profile_dir, output_dir))
        pkg = output_dir.parent.name
        seq = output_dir.name
        return _make_profile_outputs(pkg, seq)

    with patch.object(pipeline, "_run_profile_internal", side_effect=capturing_side_effect):
        bundles = pipeline.run(output_root, force=True)

    # Both profiles should have been reprocessed
    assert len(call_args) == 2
    assert len(bundles) == 2


# ---------------------------------------------------------------------------
# Test 7: run() calls _write_template_catalogs when pending profiles are processed
# ---------------------------------------------------------------------------


def test_run_tail_artifacts_on_new_profiles(tmp_path: Path) -> None:
    """run() calls _write_template_catalogs when there are newly processed profiles."""
    cfg = FeatureStoreConfig(backend="sqlite", db_path=tmp_path / "fe.db")
    opts = FeatureEngineeringPipelineOptions(feature_store_config=cfg, fail_fast=True)
    pipeline = FeatureEngineeringPipeline(options=opts)

    store = create_feature_store(cfg)
    store.initialize()
    p1 = _make_profile_record("pkg-a", "seq-1", fe_status="pending")
    store.upsert_profile(p1)
    store.close()

    output_root = tmp_path / "out"
    fake_outputs = _make_profile_outputs("pkg-a", "seq-1")

    with (
        patch.object(pipeline, "_run_profile_internal", return_value=fake_outputs),
        patch.object(pipeline, "_write_template_catalogs", return_value=None) as mock_catalogs,
    ):
        pipeline.run(output_root)

    mock_catalogs.assert_called_once()


# ---------------------------------------------------------------------------
# Test 8: run() does NOT call _write_template_catalogs when all are cached
# ---------------------------------------------------------------------------


def test_run_no_tail_artifacts_when_all_cached(tmp_path: Path) -> None:
    """run() skips _write_template_catalogs when no pending profiles were processed."""
    cfg = FeatureStoreConfig(backend="sqlite", db_path=tmp_path / "fe.db")
    opts = FeatureEngineeringPipelineOptions(feature_store_config=cfg, fail_fast=True)
    pipeline = FeatureEngineeringPipeline(options=opts)

    store = create_feature_store(cfg)
    store.initialize()
    p1 = _make_profile_record("pkg-a", "seq-1", fe_status="complete")
    store.upsert_profile(p1)
    store.close()

    output_root = tmp_path / "out"
    _write_feature_bundle(output_root, p1)

    with patch.object(pipeline, "_write_template_catalogs") as mock_catalogs:
        pipeline.run(output_root)

    mock_catalogs.assert_not_called()


# ---------------------------------------------------------------------------
# Test 9: run_corpus() registers profiles in store then delegates to run()
# ---------------------------------------------------------------------------


def test_run_corpus_registers_and_delegates(tmp_path: Path) -> None:
    """run_corpus() reads sequence_index.jsonl, registers profiles, then calls run()."""
    cfg = FeatureStoreConfig(backend="sqlite", db_path=tmp_path / "fe.db")
    opts = FeatureEngineeringPipelineOptions(feature_store_config=cfg, fail_fast=True)
    pipeline = FeatureEngineeringPipeline(options=opts)

    # Build a corpus directory with a sequence_index.jsonl
    corpus_dir = tmp_path / "corpus" / "v1.0.0"
    corpus_dir.mkdir(parents=True, exist_ok=True)
    profile_path = tmp_path / "profiles" / "pkg-a" / "seq-1"
    profile_path.mkdir(parents=True, exist_ok=True)

    index_row = {
        "profile_path": str(profile_path),
        "package_id": "pkg-a",
        "sequence_file_id": "seq-1",
    }
    (corpus_dir / "sequence_index.jsonl").write_text(json.dumps(index_row) + "\n", encoding="utf-8")

    output_root = tmp_path / "out"
    fake_outputs = _make_profile_outputs("pkg-a", "seq-1")

    with patch.object(pipeline, "_run_profile_internal", return_value=fake_outputs):
        bundles = pipeline.run_corpus(corpus_dir, output_root)

    assert len(bundles) == 1

    # Verify the profile was registered in the store
    store2 = create_feature_store(cfg)
    store2.initialize()
    all_profiles = store2.query_profiles()
    store2.close()
    assert len(all_profiles) == 1
    assert all_profiles[0].package_id == "pkg-a"
    assert all_profiles[0].sequence_file_id == "seq-1"


# ---------------------------------------------------------------------------
# Test 10: _load_existing_bundles loads feature_bundle.json
# ---------------------------------------------------------------------------


def test_load_existing_bundles(tmp_path: Path) -> None:
    """_load_existing_bundles returns FeatureBundle loaded from feature_bundle.json."""
    pipeline = FeatureEngineeringPipeline()

    output_root = tmp_path / "out"
    p1 = _make_profile_record("pkg-a", "seq-1", fe_status="complete")
    _write_feature_bundle(output_root, p1)

    bundles = pipeline._load_existing_bundles((p1,), output_root)

    assert len(bundles) == 1
    assert bundles[0].package_id == "pkg-a"
    assert bundles[0].sequence_file_id == "seq-1"


# ---------------------------------------------------------------------------
# Test 11: _load_existing_bundles skips gracefully when file is missing
# ---------------------------------------------------------------------------


def test_load_existing_bundles_missing_file(tmp_path: Path) -> None:
    """_load_existing_bundles skips profiles without a feature_bundle.json gracefully."""
    pipeline = FeatureEngineeringPipeline()

    output_root = tmp_path / "out"
    # Profile record points to a dir that exists but has no feature_bundle.json
    p1 = _make_profile_record("pkg-a", "seq-1", fe_status="complete")
    # Don't write any bundle file

    bundles = pipeline._load_existing_bundles((p1,), output_root)

    assert bundles == []
