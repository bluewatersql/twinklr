"""Tests for curve providers."""

from __future__ import annotations

import pytest

from blinkb0t.core.curves.library import build_default_registry
from blinkb0t.core.curves.native import NativeCurveType, xLightsNativeCurve
from blinkb0t.core.curves.providers.custom import CustomCurveProvider
from blinkb0t.core.curves.providers.native import NativeCurveProvider
from blinkb0t.core.curves.registry import NativeCurveDefinition


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

    def test_generate_sine_with_params(self, provider: NativeCurveProvider) -> None:
        """Generate sine curve with custom params."""
        defn = NativeCurveDefinition(curve_id="sine", default_params={"amplitude": 50.0})
        result = provider.generate(defn, params={"center": 200.0})
        assert result.p2 == 50.0  # From definition
        assert result.p4 == 200.0  # From params

    def test_generate_ramp(self, provider: NativeCurveProvider) -> None:
        """Generate ramp curve spec."""
        defn = NativeCurveDefinition(curve_id="ramp")
        result = provider.generate(defn)
        assert result.type == NativeCurveType.RAMP
        assert result.p1 == 0.0  # Default min
        assert result.p2 == 255.0  # Default max

    def test_generate_flat(self, provider: NativeCurveProvider) -> None:
        """Generate flat curve spec."""
        defn = NativeCurveDefinition(curve_id="flat")
        result = provider.generate(defn)
        assert result.type == NativeCurveType.FLAT
        assert result.p1 == 128.0  # Default value

    def test_generate_parabolic(self, provider: NativeCurveProvider) -> None:
        """Generate parabolic curve spec."""
        defn = NativeCurveDefinition(curve_id="parabolic")
        result = provider.generate(defn)
        assert result.type == NativeCurveType.PARABOLIC

    def test_generate_saw_tooth(self, provider: NativeCurveProvider) -> None:
        """Generate saw tooth curve spec."""
        defn = NativeCurveDefinition(curve_id="saw tooth")
        result = provider.generate(defn)
        assert result.type == NativeCurveType.SAW_TOOTH

    def test_generate_abs_sine(self, provider: NativeCurveProvider) -> None:
        """Generate abs sine curve spec."""
        defn = NativeCurveDefinition(curve_id="abs sine")
        result = provider.generate(defn)
        assert result.type == NativeCurveType.ABS_SINE

    def test_generate_logarithmic(self, provider: NativeCurveProvider) -> None:
        """Generate logarithmic curve spec."""
        defn = NativeCurveDefinition(curve_id="logarithmic")
        result = provider.generate(defn)
        assert result.type == NativeCurveType.LOGARITHMIC

    def test_generate_exponential(self, provider: NativeCurveProvider) -> None:
        """Generate exponential curve spec."""
        defn = NativeCurveDefinition(curve_id="exponential")
        result = provider.generate(defn)
        assert result.type == NativeCurveType.EXPONENTIAL

    def test_params_override_defaults(self, provider: NativeCurveProvider) -> None:
        """Runtime params override definition defaults."""
        defn = NativeCurveDefinition(curve_id="ramp", default_params={"min": 10.0, "max": 200.0})
        result = provider.generate(defn, params={"min": 50.0})
        assert result.p1 == 50.0  # Overridden
        assert result.p2 == 200.0  # From defaults


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

    def test_generate_sine(self, provider: CustomCurveProvider, registry) -> None:
        """Generate sine curve points."""
        defn = registry.get("sine")
        result = provider.generate(defn, num_points=8)
        assert len(result) == 8

    def test_generate_with_modifiers(self, provider: CustomCurveProvider, registry) -> None:
        """Generate curve with modifiers from definition."""
        from blinkb0t.core.curves.modifiers import CurveModifier
        from blinkb0t.core.curves.registry import CurveDefinition
        from blinkb0t.core.curves.semantics import CurveKind

        # Create a custom definition with modifiers
        def linear_gen(n_samples: int, **kwargs):
            from blinkb0t.core.curves.models import CurvePoint

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

    def test_default_num_points(self, provider: CustomCurveProvider, registry) -> None:
        """Default num_points is 100."""
        defn = registry.get("linear")
        result = provider.generate(defn)
        assert len(result) == 100

    def test_points_in_valid_range(self, provider: CustomCurveProvider, registry) -> None:
        """All points are in valid range [0, 1]."""
        defn = registry.get("ease_in_out_cubic")
        result = provider.generate(defn, num_points=20)
        for p in result:
            assert 0.0 <= p.t <= 1.0
            assert 0.0 <= p.v <= 1.0
