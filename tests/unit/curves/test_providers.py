"""Tests for curve providers."""

from __future__ import annotations

import pytest

from twinklr.core.curves.library import build_default_registry
from twinklr.core.curves.providers.custom import CustomCurveProvider


class TestCustomCurveProvider:
    """Tests for CustomCurveProvider class."""

    @pytest.fixture
    def registry(self):
        """Create a default registry."""
        return build_default_registry()

    @pytest.fixture
    def provider(self, registry) -> CustomCurveProvider:
        """Create a CustomCurveProvider instance."""
        return CustomCurveProvider(registry)

    def test_generate_linear(self, provider: CustomCurveProvider, registry) -> None:
        """Generate linear curve points."""
        defn = registry.get("linear")
        result = provider.generate(defn, num_points=10)
        assert len(result) == 10
        for p in result:
            assert 0.0 <= p.t <= 1.0
            assert 0.0 <= p.v <= 1.0
