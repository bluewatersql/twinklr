"""Tests for corpus_metadata population in _finalize_corpus.

Validates that upsert_corpus_metadata receives actual CorpusStats
instead of minimal JSON with just sequence_count.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

from twinklr.core.feature_engineering.config import FeatureEngineeringPipelineOptions
from twinklr.core.feature_engineering.datasets.writer import FeatureEngineeringWriter
from twinklr.core.feature_engineering.pipeline import FeatureEngineeringPipeline
from twinklr.core.feature_store.models import CorpusStats


def _make_mock_store() -> MagicMock:
    """Create a mock feature store with realistic stats."""
    store = MagicMock()
    store.initialize = MagicMock()
    store.close = MagicMock()
    store.upsert_corpus_metadata = MagicMock()
    store.get_corpus_stats.return_value = CorpusStats(
        phrase_count=1000,
        template_count=200,
        stack_count=50,
        transition_count=30,
        recipe_count=45,
        taxonomy_count=500,
        propensity_count=25,
        profile_count=59,
    )
    return store


class TestCorpusMetadataPopulation:
    """Verify _finalize_corpus writes actual CorpusStats."""

    def test_metadata_includes_phrase_count(self) -> None:
        """upsert_corpus_metadata JSON includes phrase_count."""
        mock_store = _make_mock_store()
        with patch(
            "twinklr.core.feature_store.factory.create_feature_store",
            return_value=mock_store,
        ):
            pipeline = FeatureEngineeringPipeline(
                options=FeatureEngineeringPipelineOptions(),
                writer=FeatureEngineeringWriter(),
            )
        pipeline._store = mock_store

        with patch("twinklr.core.feature_engineering.pipeline._ca.write_v1_tail_artifacts"):
            pipeline._finalize_corpus(
                output_root=Path("/tmp/out"),
                corpus_id="test-corpus",
                bundles=[],
                phrases=[],
                taxonomy=[],
                roles=[],
            )

        mock_store.upsert_corpus_metadata.assert_called_once()
        call_args = mock_store.upsert_corpus_metadata.call_args[0]
        assert call_args[0] == "test-corpus"
        metadata = json.loads(call_args[1])
        assert "phrase_count" in metadata
        assert metadata["phrase_count"] == 1000

    def test_metadata_includes_all_stat_fields(self) -> None:
        """upsert_corpus_metadata JSON includes all CorpusStats fields."""
        mock_store = _make_mock_store()
        with patch(
            "twinklr.core.feature_store.factory.create_feature_store",
            return_value=mock_store,
        ):
            pipeline = FeatureEngineeringPipeline(
                options=FeatureEngineeringPipelineOptions(),
                writer=FeatureEngineeringWriter(),
            )
        pipeline._store = mock_store

        with patch("twinklr.core.feature_engineering.pipeline._ca.write_v1_tail_artifacts"):
            pipeline._finalize_corpus(
                output_root=Path("/tmp/out"),
                corpus_id="test-corpus",
                bundles=[],
                phrases=[],
                taxonomy=[],
                roles=[],
            )

        call_args = mock_store.upsert_corpus_metadata.call_args[0]
        metadata = json.loads(call_args[1])

        expected_fields = [
            "phrase_count",
            "template_count",
            "stack_count",
            "transition_count",
            "recipe_count",
            "taxonomy_count",
            "propensity_count",
            "profile_count",
        ]
        for field in expected_fields:
            assert field in metadata, f"Missing field: {field}"

    def test_metadata_values_from_store(self) -> None:
        """Metadata values come from store.get_corpus_stats()."""
        mock_store = _make_mock_store()
        with patch(
            "twinklr.core.feature_store.factory.create_feature_store",
            return_value=mock_store,
        ):
            pipeline = FeatureEngineeringPipeline(
                options=FeatureEngineeringPipelineOptions(),
                writer=FeatureEngineeringWriter(),
            )
        pipeline._store = mock_store

        with patch("twinklr.core.feature_engineering.pipeline._ca.write_v1_tail_artifacts"):
            pipeline._finalize_corpus(
                output_root=Path("/tmp/out"),
                corpus_id="test-corpus",
                bundles=[],
                phrases=[],
                taxonomy=[],
                roles=[],
            )

        call_args = mock_store.upsert_corpus_metadata.call_args[0]
        metadata = json.loads(call_args[1])
        assert metadata["template_count"] == 200
        assert metadata["recipe_count"] == 45
        assert metadata["profile_count"] == 59
