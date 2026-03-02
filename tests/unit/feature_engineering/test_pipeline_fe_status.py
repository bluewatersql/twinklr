"""Tests for fe_status lifecycle in the FE pipeline.

Validates that _corpus_sequential and _corpus_parallel correctly
call mark_fe_complete on success and mark_fe_error on failure.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

from twinklr.core.feature_engineering.config import FeatureEngineeringPipelineOptions
from twinklr.core.feature_engineering.constants import FEATURE_BUNDLE_SCHEMA_VERSION
from twinklr.core.feature_engineering.datasets.writer import FeatureEngineeringWriter
from twinklr.core.feature_engineering.models.bundle import (
    AudioDiscoveryResult,
    AudioStatus,
    FeatureBundle,
)
from twinklr.core.feature_engineering.pipeline import (
    FeatureEngineeringPipeline,
    _ProfileOutputs,
)


def _make_mock_store() -> MagicMock:
    """Create a mock feature store with all required protocol methods."""
    store = MagicMock()
    store.initialize = MagicMock()
    store.close = MagicMock()
    store.mark_fe_complete = MagicMock()
    store.mark_fe_error = MagicMock()
    return store


def _make_profile_outputs() -> _ProfileOutputs:
    """Create a minimal valid _ProfileOutputs for mocking."""
    bundle = FeatureBundle(
        schema_version=FEATURE_BUNDLE_SCHEMA_VERSION,
        source_profile_path="/tmp/test",
        package_id="pkg-1",
        sequence_file_id="seq-1",
        sequence_sha256="abc123",
        song="Test Song",
        artist="Test Artist",
        audio=AudioDiscoveryResult(audio_path=None, audio_status=AudioStatus.MISSING),
    )
    return _ProfileOutputs(
        bundle=bundle,
        phrases=(),
        taxonomy_rows=(),
        target_roles=(),
    )


def _make_pipeline_with_mock_store(
    mock_store: MagicMock,
) -> FeatureEngineeringPipeline:
    """Create a pipeline with the store replaced by a mock."""
    opts = FeatureEngineeringPipelineOptions(fail_fast=False)
    with patch(
        "twinklr.core.feature_store.factory.create_feature_store",
        return_value=mock_store,
    ):
        pipeline = FeatureEngineeringPipeline(
            options=opts,
            writer=FeatureEngineeringWriter(),
        )
    pipeline._store = mock_store
    return pipeline


# ── Sequential path ────────────────────────────────────────────────────────


class TestCorpusSequentialFeStatus:
    """fe_status transitions in _corpus_sequential."""

    def test_marks_complete_on_success(self) -> None:
        """Successful profile processing calls mark_fe_complete."""
        mock_store = _make_mock_store()
        pipeline = _make_pipeline_with_mock_store(mock_store)

        rows = [{"package_id": "pkg-1", "sequence_file_id": "seq-1", "profile_path": "/tmp/p"}]

        with patch.object(pipeline, "_run_profile_internal", return_value=_make_profile_outputs()):
            pipeline._corpus_sequential(rows, Path("/tmp/out"), None)

        mock_store.mark_fe_complete.assert_called_once_with("pkg-1/seq-1")

    def test_marks_error_on_failure(self) -> None:
        """Failed profile processing calls mark_fe_error."""
        mock_store = _make_mock_store()
        pipeline = _make_pipeline_with_mock_store(mock_store)

        rows = [{"package_id": "pkg-1", "sequence_file_id": "seq-1", "profile_path": "/tmp/p"}]

        with patch.object(pipeline, "_run_profile_internal", side_effect=RuntimeError("boom")):
            pipeline._corpus_sequential(rows, Path("/tmp/out"), None)

        mock_store.mark_fe_error.assert_called_once()
        args = mock_store.mark_fe_error.call_args[0]
        assert args[0] == "pkg-1/seq-1"
        assert "boom" in args[1]

    def test_does_not_mark_complete_on_failure(self) -> None:
        """Failed profile should NOT call mark_fe_complete."""
        mock_store = _make_mock_store()
        pipeline = _make_pipeline_with_mock_store(mock_store)

        rows = [{"package_id": "pkg-1", "sequence_file_id": "seq-1", "profile_path": "/tmp/p"}]

        with patch.object(pipeline, "_run_profile_internal", side_effect=RuntimeError("boom")):
            pipeline._corpus_sequential(rows, Path("/tmp/out"), None)

        mock_store.mark_fe_complete.assert_not_called()


# ── Parallel path ──────────────────────────────────────────────────────────


class TestCorpusParallelFeStatus:
    """fe_status transitions in _corpus_parallel."""

    def test_marks_complete_on_success(self) -> None:
        """Successful parallel profile processing calls mark_fe_complete."""
        mock_store = _make_mock_store()
        pipeline = _make_pipeline_with_mock_store(mock_store)

        rows = [{"package_id": "pkg-1", "sequence_file_id": "seq-1", "profile_path": "/tmp/p"}]

        with patch.object(pipeline, "_run_profile_internal", return_value=_make_profile_outputs()):
            pipeline._corpus_parallel(rows, Path("/tmp/out"), 1, None)

        mock_store.mark_fe_complete.assert_called_once_with("pkg-1/seq-1")
