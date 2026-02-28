"""Tests for the NullFeatureStore backend."""

from __future__ import annotations

import pytest

from twinklr.core.feature_store.backends.null import NullFeatureStore
from twinklr.core.feature_store.models import CorpusStats

# ---------------------------------------------------------------------------
# Helpers / fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def store() -> NullFeatureStore:
    """A fresh NullFeatureStore for each test."""
    return NullFeatureStore()


# ---------------------------------------------------------------------------
# Write methods — all must return 0
# ---------------------------------------------------------------------------


def test_upsert_phrases_returns_zero(store: NullFeatureStore) -> None:
    assert store.upsert_phrases(()) == 0


def test_upsert_templates_returns_zero(store: NullFeatureStore) -> None:
    assert store.upsert_templates(()) == 0


def test_upsert_template_assignments_returns_zero(store: NullFeatureStore) -> None:
    assert store.upsert_template_assignments(()) == 0


def test_upsert_stacks_returns_zero(store: NullFeatureStore) -> None:
    assert store.upsert_stacks(()) == 0


def test_upsert_transitions_returns_zero(store: NullFeatureStore) -> None:
    assert store.upsert_transitions(()) == 0


def test_upsert_recipes_returns_zero(store: NullFeatureStore) -> None:
    assert store.upsert_recipes(()) == 0


def test_upsert_taxonomy_returns_zero(store: NullFeatureStore) -> None:
    assert store.upsert_taxonomy(()) == 0


def test_upsert_propensity_returns_zero(store: NullFeatureStore) -> None:
    assert store.upsert_propensity(()) == 0


def test_upsert_corpus_metadata_returns_zero(store: NullFeatureStore) -> None:
    assert store.upsert_corpus_metadata("corpus-1", "{}") == 0


def test_all_write_methods_return_zero(store: NullFeatureStore) -> None:
    """Comprehensive sweep: every upsert method returns 0."""
    assert store.upsert_phrases(()) == 0
    assert store.upsert_templates(()) == 0
    assert store.upsert_template_assignments(()) == 0
    assert store.upsert_stacks(()) == 0
    assert store.upsert_transitions(()) == 0
    assert store.upsert_recipes(()) == 0
    assert store.upsert_taxonomy(()) == 0
    assert store.upsert_propensity(()) == 0
    assert store.upsert_corpus_metadata("x", "{}") == 0


# ---------------------------------------------------------------------------
# Read methods — all must return empty tuples
# ---------------------------------------------------------------------------


def test_query_phrases_by_target_returns_empty(store: NullFeatureStore) -> None:
    result = store.query_phrases_by_target("pkg", "seq", "MegaTree")
    assert result == ()


def test_query_phrases_by_family_returns_empty(store: NullFeatureStore) -> None:
    result = store.query_phrases_by_family("color_wash")
    assert result == ()


def test_query_templates_returns_empty(store: NullFeatureStore) -> None:
    result = store.query_templates()
    assert result == ()


def test_query_templates_with_filters_returns_empty(store: NullFeatureStore) -> None:
    result = store.query_templates(effect_family="bars", min_support=5, min_stability=0.8)
    assert result == ()


def test_query_stacks_by_target_returns_empty(store: NullFeatureStore) -> None:
    result = store.query_stacks_by_target("pkg", "seq", "Arch")
    assert result == ()


def test_query_stacks_by_signature_returns_empty(store: NullFeatureStore) -> None:
    result = store.query_stacks_by_signature("color_wash|bars")
    assert result == ()


def test_query_recipes_returns_empty(store: NullFeatureStore) -> None:
    result = store.query_recipes()
    assert result == ()


def test_query_recipes_with_filter_returns_empty(store: NullFeatureStore) -> None:
    result = store.query_recipes(template_type="BASE")
    assert result == ()


def test_query_transitions_returns_empty(store: NullFeatureStore) -> None:
    result = store.query_transitions()
    assert result == ()


def test_query_transitions_with_filter_returns_empty(store: NullFeatureStore) -> None:
    result = store.query_transitions(source_template_id="tmpl-001")
    assert result == ()


def test_all_read_methods_return_empty(store: NullFeatureStore) -> None:
    """Comprehensive sweep: every query method returns an empty tuple."""
    assert store.query_phrases_by_target("p", "s", "t") == ()
    assert store.query_phrases_by_family("f") == ()
    assert store.query_templates() == ()
    assert store.query_stacks_by_target("p", "s", "t") == ()
    assert store.query_stacks_by_signature("sig") == ()
    assert store.query_recipes() == ()
    assert store.query_transitions() == ()


# ---------------------------------------------------------------------------
# Metadata methods
# ---------------------------------------------------------------------------


def test_get_corpus_stats_returns_zeros(store: NullFeatureStore) -> None:
    stats = store.get_corpus_stats()
    assert isinstance(stats, CorpusStats)
    assert stats.phrase_count == 0
    assert stats.template_count == 0
    assert stats.stack_count == 0
    assert stats.transition_count == 0
    assert stats.recipe_count == 0
    assert stats.taxonomy_count == 0
    assert stats.propensity_count == 0


def test_get_schema_version_returns_null(store: NullFeatureStore) -> None:
    assert store.get_schema_version() == "null"


def test_store_reference_data_is_noop(store: NullFeatureStore) -> None:
    """store_reference_data must not raise."""
    store.store_reference_data("key", '{"data": 1}', "1.0.0")


def test_load_reference_data_returns_none(store: NullFeatureStore) -> None:
    result = store.load_reference_data("key")
    assert result is None


# ---------------------------------------------------------------------------
# Lifecycle methods
# ---------------------------------------------------------------------------


def test_initialize_is_idempotent(store: NullFeatureStore) -> None:
    """Calling initialize() twice must not raise."""
    store.initialize()
    store.initialize()


def test_close_is_idempotent(store: NullFeatureStore) -> None:
    """Calling close() twice must not raise."""
    store.close()
    store.close()


def test_lifecycle_sequence(store: NullFeatureStore) -> None:
    """initialize → use → close sequence must work without error."""
    store.initialize()
    assert store.get_schema_version() == "null"
    store.close()
