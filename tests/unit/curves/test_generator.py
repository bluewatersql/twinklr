"""Tests for curve generator orchestrator."""

from __future__ import annotations

import pytest

from blinkb0t.core.curves.generator import CurveGenerator
from blinkb0t.core.curves.library import CurveLibrary
from blinkb0t.core.curves.native import NativeCurveType, xLightsNativeCurve


class TestCurveGenerator:
    """Tests for CurveGenerator class."""

    @pytest.fixture
    def generator(self) -> CurveGenerator:
        """Create a CurveGenerator instance."""
        return CurveGenerator()

    def test_initialization(self, generator: CurveGenerator) -> None:
        """Generator initializes with registry and providers."""
        assert generator._registry is not None
        assert generator._native is not None
        assert generator._custom is not None

    def test_generate_native_spec_sine(self, generator: CurveGenerator) -> None:
        """Generate native sine curve spec."""
        result = generator.generate_native_spec("sine")
        assert isinstance(result, xLightsNativeCurve)
        assert result.type == NativeCurveType.SINE

    def test_generate_native_spec_ramp(self, generator: CurveGenerator) -> None:
        """Generate native ramp curve spec."""
        result = generator.generate_native_spec("ramp")
        assert isinstance(result, xLightsNativeCurve)
        assert result.type == NativeCurveType.RAMP

    def test_generate_native_spec_flat(self, generator: CurveGenerator) -> None:
        """Generate native flat curve spec."""
        result = generator.generate_native_spec("flat")
        assert isinstance(result, xLightsNativeCurve)
        assert result.type == NativeCurveType.FLAT

    def test_generate_native_spec_with_params(self, generator: CurveGenerator) -> None:
        """Generate native curve spec with custom params."""
        result = generator.generate_native_spec("sine", {"amplitude": 50.0, "center": 200.0})
        assert result.p2 == 50.0
        assert result.p4 == 200.0

    def test_generate_native_spec_invalid_type_raises(self, generator: CurveGenerator) -> None:
        """Invalid native curve type raises ValueError."""
        with pytest.raises(ValueError, match="not a valid native curve type"):
            generator.generate_native_spec("nonexistent")

    def test_generate_native_spec_case_insensitive(self, generator: CurveGenerator) -> None:
        """Native curve ID is case insensitive."""
        result_lower = generator.generate_native_spec("sine")
        result_upper = generator.generate_native_spec("SINE")
        assert result_lower.type == result_upper.type

    def test_generate_custom_points_linear(self, generator: CurveGenerator) -> None:
        """Generate custom linear curve points."""
        result = generator.generate_custom_points(CurveLibrary.LINEAR.value, num_points=10)
        assert len(result) == 10
        for p in result:
            assert 0.0 <= p.t <= 1.0
            assert 0.0 <= p.v <= 1.0

    def test_generate_custom_points_sine(self, generator: CurveGenerator) -> None:
        """Generate custom sine curve points."""
        result = generator.generate_custom_points(CurveLibrary.SINE.value, num_points=8)
        assert len(result) == 8

    def test_generate_custom_points_invalid_raises(self, generator: CurveGenerator) -> None:
        """Invalid custom curve ID raises ValueError."""
        with pytest.raises(ValueError, match="not registered"):
            generator.generate_custom_points("nonexistent", num_points=10)

    def test_generate_custom_points_default_count(self, generator: CurveGenerator) -> None:
        """Default num_points is 100."""
        result = generator.generate_custom_points(CurveLibrary.LINEAR.value)
        assert len(result) == 100

    @pytest.mark.parametrize(
        "curve_id",
        [
            CurveLibrary.EASE_IN_SINE.value,
            CurveLibrary.EASE_OUT_QUAD.value,
            CurveLibrary.SMOOTH_STEP.value,
        ],
    )
    def test_generate_various_easing_curves(self, generator: CurveGenerator, curve_id: str) -> None:
        """Various easing curves generate valid points."""
        result = generator.generate_custom_points(curve_id, num_points=10)
        assert len(result) == 10
        for p in result:
            assert 0.0 <= p.t <= 1.0
            assert 0.0 <= p.v <= 1.0

    @pytest.mark.parametrize(
        "curve_id",
        [
            CurveLibrary.MOVEMENT_LINEAR.value,
            CurveLibrary.MOVEMENT_SINE.value,
            CurveLibrary.MOVEMENT_HOLD.value,
        ],
    )
    def test_generate_movement_curves(self, generator: CurveGenerator, curve_id: str) -> None:
        """Movement curves generate valid points with loop-ready behavior."""
        result = generator.generate_custom_points(curve_id, num_points=10)
        # Movement curves may add an extra point for loop readiness
        assert len(result) >= 10
        for p in result:
            assert 0.0 <= p.t <= 1.0
            assert 0.0 <= p.v <= 1.0

    @pytest.mark.parametrize(
        "native_type",
        [
            "sine",
            "ramp",
            "flat",
            "parabolic",
            "saw tooth",
            "logarithmic",
            "exponential",
            "abs sine",
        ],
    )
    def test_generate_all_native_types(self, generator: CurveGenerator, native_type: str) -> None:
        """All native curve types can be generated."""
        result = generator.generate_native_spec(native_type)
        assert isinstance(result, xLightsNativeCurve)
