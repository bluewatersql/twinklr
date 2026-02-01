"""Tests for curve providers."""

from __future__ import annotations

import pytest

from twinklr.core.curves.library import build_default_registry
from twinklr.core.curves.native import NativeCurveType, xLightsNativeCurve
from twinklr.core.curves.providers.custom import CustomCurveProvider
from twinklr.core.curves.providers.native import NativeCurveProvider
from twinklr.core.curves.registry import NativeCurveDefinition


class TestNativeCurveProvider:
    """Tests for NativeCurveProvider class."""

    @pytest.fixture
    def provider(self) -> NativeCurveProvider:
        """Create a NativeCurveProvider instance."""
        return NativeCurveProvider()

    def test_generate_sine(self, provider: NativeCurveProvider) -> None:
        """Generate sine curve spec."""
        defn = NativeCurveDefinition(curve_id="sine")
        result = provider.generate(defn)
        assert isinstance(result, xLightsNativeCurve)
        assert result.type == NativeCurveType.SINE
        assert result.p2 == 100.0  # Default amplitude
        assert result.p4 == 128.0  # Default center

    def test_generate_ramp(self, provider: NativeCurveProvider) -> None:
        """Generate ramp curve spec."""
        defn = NativeCurveDefinition(curve_id="ramp")
        result = provider.generate(defn)
        assert result.type == NativeCurveType.RAMP
        assert result.p1 == 0.0  # Default min
        assert result.p2 == 255.0  # Default max


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

    def test_generate_with_modifiers(self, provider: CustomCurveProvider, registry) -> None:
        """Generate curve with modifiers from definition."""
        from twinklr.core.curves.modifiers import CurveModifier
        from twinklr.core.curves.registry import CurveDefinition
        from twinklr.core.curves.semantics import CurveKind

        # Create a custom definition with modifiers
        def linear_gen(n_samples: int, **kwargs):
            from twinklr.core.curves.models import CurvePoint

            return [
                CurvePoint(t=i / (n_samples - 1), v=i / (n_samples - 1)) for i in range(n_samples)
            ]

        defn = CurveDefinition(
            curve_id="custom_mirrored",
            generator=linear_gen,
            kind=CurveKind.DIMMER_ABSOLUTE,
            default_samples=4,
            modifiers=[CurveModifier.MIRROR],
        )
        registry.register(defn)

        result = provider.generate(defn, num_points=4)
        # Mirrored linear: values should go from 1 to 0
        assert result[0].v == pytest.approx(1.0)
        assert result[-1].v == pytest.approx(0.0)
