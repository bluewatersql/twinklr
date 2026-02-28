"""Tests for feature store protocol definitions."""

from __future__ import annotations

from twinklr.core.feature_store.backends.null import NullFeatureStore
from twinklr.core.feature_store.protocols import FeatureStoreProviderSync


def test_null_store_satisfies_protocol() -> None:
    """NullFeatureStore must satisfy FeatureStoreProviderSync at runtime."""
    store = NullFeatureStore()
    assert isinstance(store, FeatureStoreProviderSync)


def test_protocol_is_runtime_checkable() -> None:
    """FeatureStoreProviderSync must be decorated with @runtime_checkable."""
    # A runtime_checkable Protocol allows isinstance() checks.
    # If not runtime_checkable, isinstance() would raise TypeError.
    store = NullFeatureStore()
    # This line would raise TypeError if not runtime_checkable:
    result = isinstance(store, FeatureStoreProviderSync)
    assert result is True


def test_non_conforming_object_fails_protocol_check() -> None:
    """An object that does not implement the protocol should not pass isinstance."""

    class Stub:
        pass

    assert not isinstance(Stub(), FeatureStoreProviderSync)
