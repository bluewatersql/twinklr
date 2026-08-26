"""Tests for curve registry and preset resolution."""

from __future__ import annotations

import pytest

from twinklr.core.curves.models import CurvePoint
from twinklr.core.curves.registry import (
    CurveDefinition,
    CurveRegistry,
)
from twinklr.core.curves.semantics import CurveKind


def mock_generator(n_samples: int, **kwargs) -> list[CurvePoint]:
    """Mock curve generator for testing."""
    return [CurvePoint(t=i / (n_samples - 1), v=i / (n_samples - 1)) for i in range(n_samples)]


def mock_constant_generator(n_samples: int, value: float = 0.5, **kwargs) -> list[CurvePoint]:
    """Mock generator returning constant value."""
    return [CurvePoint(t=i / (n_samples - 1), v=value) for i in range(n_samples)]


class TestCurveDefinition:
    """Tests for CurveDefinition dataclass."""

    def test_create_with_required_fields(self) -> None:
        """Create with required fields."""
        defn = CurveDefinition(
            curve_id="test",
            generator=mock_generator,
            kind=CurveKind.DIMMER_ABSOLUTE,
            default_samples=64,
        )
        assert defn.curve_id == "test"
        assert defn.generator == mock_generator
        assert defn.kind == CurveKind.DIMMER_ABSOLUTE
        assert defn.default_samples == 64

    def test_create_with_all_fields(self) -> None:
        """Create with all fields."""
        defn = CurveDefinition(
            curve_id="test",
            generator=mock_generator,
            kind=CurveKind.MOVEMENT_OFFSET,
            default_samples=32,
            default_params={"cycles": 2.0},
            description="Test curve",
        )
        assert defn.default_params == {"cycles": 2.0}
        assert defn.description == "Test curve"

    def test_is_frozen(self) -> None:
        """Definition is immutable (frozen dataclass)."""
        from dataclasses import FrozenInstanceError

        defn = CurveDefinition(
            curve_id="test",
            generator=mock_generator,
            kind=CurveKind.DIMMER_ABSOLUTE,
            default_samples=64,
        )
        with pytest.raises(FrozenInstanceError):
            defn.curve_id = "other"  # type: ignore[misc]


class TestCurveRegistry:
    """Tests for CurveRegistry class."""

    def test_register_new_curve(self) -> None:
        """Register a new curve definition."""
        registry = CurveRegistry()
        defn = CurveDefinition(
            curve_id="test",
            generator=mock_generator,
            kind=CurveKind.DIMMER_ABSOLUTE,
            default_samples=64,
        )
        registry.register(defn)
        assert registry.get("test") == defn

    def test_register_duplicate_raises(self) -> None:
        """Registering duplicate curve_id raises ValueError."""
        registry = CurveRegistry()
        defn = CurveDefinition(
            curve_id="test",
            generator=mock_generator,
            kind=CurveKind.DIMMER_ABSOLUTE,
            default_samples=64,
        )
        registry.register(defn)
        with pytest.raises(ValueError, match="already registered"):
            registry.register(defn)

    def test_get_unregistered_raises(self) -> None:
        """Getting unregistered curve raises ValueError."""
        registry = CurveRegistry()
        with pytest.raises(ValueError, match="not registered"):
            registry.get("nonexistent")

    def test_resolve_basic(self) -> None:
        """Resolve returns generated points."""
        registry = CurveRegistry()
        defn = CurveDefinition(
            curve_id="test",
            generator=mock_generator,
            kind=CurveKind.DIMMER_ABSOLUTE,
            default_samples=10,
        )
        registry.register(defn)
        result = registry.resolve(defn)
        assert len(result) == 10

    def test_resolve_with_n_samples_override(self) -> None:
        """Resolve respects n_samples override."""
        registry = CurveRegistry()
        defn = CurveDefinition(
            curve_id="test",
            generator=mock_generator,
            kind=CurveKind.DIMMER_ABSOLUTE,
            default_samples=10,
        )
        registry.register(defn)
        result = registry.resolve(defn, n_samples=5)
        assert len(result) == 5
