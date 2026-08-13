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
    "CorpusStats",
    "FeatureStoreConfig",
    "FeatureStoreConnectionError",
    "FeatureStoreError",
    "FeatureStoreProviderSync",
    "FeatureStoreSchemaError",
    "ProfileRecord",
    "create_feature_store",
]
