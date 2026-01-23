"""Tests for curve registry and preset resolution."""

from __future__ import annotations

import pytest

from blinkb0t.core.curves.models import CurvePoint
from blinkb0t.core.curves.modifiers import CurveModifier
from blinkb0t.core.curves.registry import (
    CurveDefinition,
    CurveRegistry,
    NativeCurveDefinition,
    _apply_modifiers,
)
from blinkb0t.core.curves.semantics import CurveKind


def mock_generator(n_samples: int, **kwargs) -> list[CurvePoint]:
    """Mock curve generator for testing."""
    return [CurvePoint(t=i / (n_samples - 1), v=i / (n_samples - 1)) for i in range(n_samples)]


def mock_constant_generator(n_samples: int, value: float = 0.5, **kwargs) -> list[CurvePoint]:
    """Mock generator returning constant value."""
    return [CurvePoint(t=i / (n_samples - 1), v=value) for i in range(n_samples)]


class TestNativeCurveDefinition:
    """Tests for NativeCurveDefinition dataclass."""

    def test_create_with_required_fields(self) -> None:
        """Create with only curve_id."""
        defn = NativeCurveDefinition(curve_id="sine")
        assert defn.curve_id == "sine"
        assert defn.default_params is None
        assert defn.description is None

    def test_create_with_all_fields(self) -> None:
        """Create with all fields."""
        defn = NativeCurveDefinition(
            curve_id="sine",
            default_params={"amplitude": 100.0},
            description="Sine wave curve",
        )
        assert defn.curve_id == "sine"
        assert defn.default_params == {"amplitude": 100.0}
        assert defn.description == "Sine wave curve"

    def test_is_frozen(self) -> None:
        """Definition is immutable (frozen dataclass)."""
        from dataclasses import FrozenInstanceError

        defn = NativeCurveDefinition(curve_id="sine")
        with pytest.raises(FrozenInstanceError):
            defn.curve_id = "cosine"  # type: ignore[misc]


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
            modifiers=[CurveModifier.REVERSE],
            description="Test curve",
        )
        assert defn.default_params == {"cycles": 2.0}
        assert defn.modifiers == [CurveModifier.REVERSE]
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


class TestApplyModifiers:
    """Tests for _apply_modifiers function."""

    def test_reverse_modifier(self) -> None:
        """Reverse modifier reverses curve."""
        points = [
            CurvePoint(t=0.0, v=0.0),
            CurvePoint(t=1.0, v=1.0),
        ]
        result = _apply_modifiers(points, [CurveModifier.REVERSE])
        assert result[0].t == pytest.approx(0.0)
        assert result[0].v == pytest.approx(1.0)

    def test_mirror_modifier(self) -> None:
        """Mirror modifier mirrors curve."""
        points = [
            CurvePoint(t=0.0, v=0.0),
            CurvePoint(t=1.0, v=1.0),
        ]
        result = _apply_modifiers(points, [CurveModifier.MIRROR])
        assert result[0].v == pytest.approx(1.0)
        assert result[1].v == pytest.approx(0.0)

    def test_bounce_modifier(self) -> None:
        """Bounce modifier bounces curve."""
        points = [
            CurvePoint(t=0.0, v=0.0),
            CurvePoint(t=0.5, v=0.5),
            CurvePoint(t=1.0, v=1.0),
        ]
        result = _apply_modifiers(points, [CurveModifier.BOUNCE])
        assert result[1].v == pytest.approx(1.0)  # Peak at v=0.5 input

    def test_pingpong_modifier(self) -> None:
        """Pingpong modifier doubles curve."""
        points = [
            CurvePoint(t=0.0, v=0.0),
            CurvePoint(t=1.0, v=1.0),
        ]
        result = _apply_modifiers(points, [CurveModifier.PINGPONG])
        assert len(result) == 4

    def test_repeat_modifier(self) -> None:
        """Repeat modifier doubles curve."""
        points = [
            CurvePoint(t=0.0, v=0.0),
            CurvePoint(t=1.0, v=1.0),
        ]
        result = _apply_modifiers(points, [CurveModifier.REPEAT])
        assert len(result) == 4

    def test_multiple_modifiers_applied_in_order(self) -> None:
        """Multiple modifiers are applied in order."""
        points = [
            CurvePoint(t=0.0, v=0.0),
            CurvePoint(t=1.0, v=1.0),
        ]
        # Mirror then reverse
        result = _apply_modifiers(points, [CurveModifier.MIRROR, CurveModifier.REVERSE])
        # After mirror: [(0, 1), (1, 0)]
        # After reverse: [(0, 0), (1, 1)]
        assert result[0].v == pytest.approx(0.0)
        assert result[1].v == pytest.approx(1.0)

    def test_empty_modifiers_returns_same(self) -> None:
        """Empty modifier list returns same points."""
        points = [
            CurvePoint(t=0.0, v=0.0),
            CurvePoint(t=1.0, v=1.0),
        ]
        result = _apply_modifiers(points, [])
        assert result == points


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

    def test_resolve_applies_modifiers(self) -> None:
        """Resolve applies definition's modifiers."""
        registry = CurveRegistry()
        defn_base = CurveDefinition(
            curve_id="test",
            generator=mock_generator,
            kind=CurveKind.DIMMER_ABSOLUTE,
            default_samples=4,
        )
        registry.register(defn_base)
        defn_with_mod = CurveDefinition(
            curve_id="test",
            generator=mock_generator,
            kind=CurveKind.DIMMER_ABSOLUTE,
            default_samples=4,
            modifiers=[CurveModifier.MIRROR],
        )
        result = registry.resolve(defn_with_mod)
        # Original linear goes 0->1, mirrored goes 1->0
        assert result[0].v == pytest.approx(1.0)
        assert result[-1].v == pytest.approx(0.0)
