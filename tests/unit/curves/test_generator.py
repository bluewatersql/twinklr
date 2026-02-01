"""Tests for curve generator orchestrator."""

from __future__ import annotations

import pytest

from twinklr.core.curves.generator import CurveGenerator
from twinklr.core.curves.library import CurveLibrary


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

    def test_generate_native_spec_invalid_type_raises(self, generator: CurveGenerator) -> None:
        """Invalid native curve type raises ValueError."""
        with pytest.raises(ValueError, match="not a valid native curve type"):
            generator.generate_native_spec("nonexistent")

    def test_generate_custom_points_linear(self, generator: CurveGenerator) -> None:
        """Generate custom linear curve points."""
        result = generator.generate_custom_points(CurveLibrary.LINEAR.value, num_points=10)
        assert len(result) == 10
        for p in result:
            assert 0.0 <= p.t <= 1.0
            assert 0.0 <= p.v <= 1.0

    def test_generate_custom_points_invalid_raises(self, generator: CurveGenerator) -> None:
        """Invalid custom curve ID raises ValueError."""
        with pytest.raises(ValueError, match="not registered"):
            generator.generate_custom_points("nonexistent", num_points=10)

    def test_generate_custom_points_default_count(self, generator: CurveGenerator) -> None:
        """Default num_points is 100."""
        result = generator.generate_custom_points(CurveLibrary.LINEAR.value)
        assert len(result) == 100

    def test_generate_various_easing_curves(self, generator: CurveGenerator) -> None:
        """Various easing curves generate valid points."""
        result = generator.generate_custom_points(CurveLibrary.EASE_IN_SINE.value, num_points=10)
        assert len(result) == 10
        for p in result:
            assert 0.0 <= p.t <= 1.0
            assert 0.0 <= p.v <= 1.0

    def test_generate_movement_curves(self, generator: CurveGenerator) -> None:
        """Movement curves generate valid points with loop-ready behavior."""
        result = generator.generate_custom_points(CurveLibrary.MOVEMENT_LINEAR.value, num_points=10)
        # Movement curves may add an extra point for loop readiness
        assert len(result) >= 10
        for p in result:
            assert 0.0 <= p.t <= 1.0
            assert 0.0 <= p.v <= 1.0
