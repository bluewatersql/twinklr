"""Tests for the feature store factory."""

from __future__ import annotations

from pathlib import Path

import pytest

from twinklr.core.feature_store.backends.null import NullFeatureStore
from twinklr.core.feature_store.factory import create_feature_store
from twinklr.core.feature_store.models import FeatureStoreConfig, FeatureStoreError
from twinklr.core.feature_store.protocols import FeatureStoreProviderSync


def test_factory_returns_null_store() -> None:
    """Factory with backend='null' returns a NullFeatureStore instance."""
    config = FeatureStoreConfig(backend="null")
    store = create_feature_store(config)
    assert isinstance(store, NullFeatureStore)


def test_factory_null_store_satisfies_protocol() -> None:
    """NullFeatureStore returned by factory satisfies the protocol."""
    config = FeatureStoreConfig(backend="null")
    store = create_feature_store(config)
    assert isinstance(store, FeatureStoreProviderSync)


def test_factory_raises_for_unknown_backend() -> None:
    """Factory raises FeatureStoreError for an unrecognised backend string."""
    # We must bypass Pydantic validation to inject an invalid literal.
    config = FeatureStoreConfig.model_construct(backend="unknown")  # type: ignore[call-arg]
    with pytest.raises(FeatureStoreError, match="unknown"):
        create_feature_store(config)


def test_factory_requires_db_path_for_sqlite() -> None:
    """Factory raises FeatureStoreError when backend='sqlite' but db_path is None."""
    config = FeatureStoreConfig(backend="sqlite", db_path=None)
    with pytest.raises(FeatureStoreError, match="db_path"):
        create_feature_store(config)


def test_factory_creates_sqlite_store(tmp_path: Path) -> None:
    """Factory with backend='sqlite' and a valid db_path returns a protocol-satisfying store."""
    db_file = tmp_path / "test.db"
    config = FeatureStoreConfig(backend="sqlite", db_path=db_file)
    store = create_feature_store(config)
    assert isinstance(store, FeatureStoreProviderSync)
