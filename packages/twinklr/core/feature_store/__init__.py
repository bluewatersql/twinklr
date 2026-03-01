"""Feature store package — backend-agnostic persistence layer for feature engineering."""

from twinklr.core.feature_store.factory import create_feature_store
from twinklr.core.feature_store.models import (
    CorpusStats,
    FeatureStoreConfig,
    FeatureStoreConnectionError,
    FeatureStoreError,
    FeatureStoreSchemaError,
    ProfileRecord,
)
from twinklr.core.feature_store.protocols import FeatureStoreProviderSync

__all__ = [
    "FeatureStoreConfig",
    "CorpusStats",
    "ProfileRecord",
    "FeatureStoreError",
    "FeatureStoreSchemaError",
    "FeatureStoreConnectionError",
    "FeatureStoreProviderSync",
    "create_feature_store",
]
