"""Feature store factory — selects and constructs the correct backend.

Usage::

    from twinklr.core.feature_store.factory import create_feature_store
    from twinklr.core.feature_store.models import FeatureStoreConfig

    config = FeatureStoreConfig(backend="null")
    store = create_feature_store(config)
    store.initialize()
"""

from __future__ import annotations

from twinklr.core.feature_store.models import FeatureStoreConfig, FeatureStoreError
from twinklr.core.feature_store.protocols import FeatureStoreProviderSync


def create_feature_store(config: FeatureStoreConfig) -> FeatureStoreProviderSync:
    """Construct a feature store backend from *config*.

    Args:
        config: Backend selection and connection parameters.

    Returns:
        An initialised ``FeatureStoreProviderSync`` implementation.

    Raises:
        FeatureStoreError: If the backend is unknown, or if required
            parameters (e.g. ``db_path`` for SQLite) are missing.
    """
    if config.backend == "null":
        from twinklr.core.feature_store.backends.null import NullFeatureStore

        return NullFeatureStore()

    if config.backend == "sqlite":
        if config.db_path is None:
            raise FeatureStoreError(
                "backend='sqlite' requires a db_path but none was provided. "
                "Set FeatureStoreConfig.db_path to a valid file path."
            )
        # Lazy import so that the sqlite3 / bootstrap dependencies are only
        # pulled in when the SQLite backend is actually requested.
        from twinklr.core.feature_store.backends.sqlite import (
            SQLiteFeatureStore,  # type: ignore[import]
        )

        return SQLiteFeatureStore(config)

    raise FeatureStoreError(
        f"Unknown feature store backend: {config.backend!r}. Supported backends: 'null', 'sqlite'."
    )
