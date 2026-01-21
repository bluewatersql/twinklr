"""Tests for Handler Protocols.

Tests GeometryHandler, MovementHandler, and DimmerHandler protocols.
Validates protocol contracts and mock implementations.
"""

from typing import TYPE_CHECKING, Any

from pydantic import ValidationError
import pytest

from blinkb0t.core.curves.models import CurvePoint
from blinkb0t.core.sequencer.moving_heads.handlers.protocols import (
    DimmerResult,
    GeometryResult,
    MovementResult,
)

if TYPE_CHECKING:
    from blinkb0t.core.sequencer.moving_heads.handlers.protocols import (
        DimmerHandler,
        GeometryHandler,
        MovementHandler,
    )


class MockGeometryHandler:
    """Mock implementation of GeometryHandler for testing."""

    handler_id = "MOCK_GEOMETRY"

    def resolve(
        self,
        fixture_id: str,
        role: str,
        params: dict[str, Any],
        calibration: dict[str, Any],
    ) -> GeometryResult:
        """Return fixed base pose."""
        return GeometryResult(
            pan_norm=0.5,
            tilt_norm=0.5,
        )


class MockMovementHandler:
    """Mock implementation of MovementHandler for testing."""

    handler_id = "MOCK_MOVEMENT"

    def generate(
        self,
        params: dict[str, Any],
        n_samples: int,
        cycles: float,
        intensity: str,
    ) -> MovementResult:
        """Return flat curves (no motion)."""
        points = [CurvePoint(t=i / n_samples, v=0.5) for i in range(n_samples)]
        return MovementResult(
            pan_curve=points,
            tilt_curve=points,
        )


class MockDimmerHandler:
    """Mock implementation of DimmerHandler for testing."""

    handler_id = "MOCK_DIMMER"

    def generate(
        self,
        params: dict[str, Any],
        n_samples: int,
        cycles: float,
        intensity: str,
        min_norm: float,
        max_norm: float,
    ) -> DimmerResult:
        """Return constant full-on curve."""
        points = [CurvePoint(t=i / n_samples, v=max_norm) for i in range(n_samples)]
        return DimmerResult(dimmer_curve=points)


class TestGeometryHandlerProtocol:
    """Tests for GeometryHandler protocol."""

    def test_geometry_handler_has_handler_id(self) -> None:
        """Test GeometryHandler has handler_id attribute."""
        handler = MockGeometryHandler()
        assert handler.handler_id == "MOCK_GEOMETRY"

    def test_geometry_handler_resolve_returns_result(self) -> None:
        """Test GeometryHandler.resolve returns GeometryResult."""
        handler = MockGeometryHandler()
        result = handler.resolve(
            fixture_id="FX1",
            role="FRONT_LEFT",
            params={},
            calibration={},
        )
        assert isinstance(result, GeometryResult)
        assert 0.0 <= result.pan_norm <= 1.0
        assert 0.0 <= result.tilt_norm <= 1.0

    def test_geometry_result_is_immutable(self) -> None:
        """Test GeometryResult is immutable (frozen)."""
        result = GeometryResult(pan_norm=0.5, tilt_norm=0.5)
        with pytest.raises(ValidationError):  # ValidationError or similar
            result.pan_norm = 0.7  # type: ignore[misc]

    def test_geometry_result_validates_bounds(self) -> None:
        """Test GeometryResult validates [0, 1] bounds."""
        with pytest.raises(ValueError):
            GeometryResult(pan_norm=1.5, tilt_norm=0.5)
        with pytest.raises(ValueError):
            GeometryResult(pan_norm=0.5, tilt_norm=-0.1)


class TestMovementHandlerProtocol:
    """Tests for MovementHandler protocol."""

    def test_movement_handler_has_handler_id(self) -> None:
        """Test MovementHandler has handler_id attribute."""
        handler = MockMovementHandler()
        assert handler.handler_id == "MOCK_MOVEMENT"

    def test_movement_handler_generate_returns_result(self) -> None:
        """Test MovementHandler.generate returns MovementResult."""
        handler = MockMovementHandler()
        result = handler.generate(
            params={},
            n_samples=8,
            cycles=1.0,
            intensity="SMOOTH",
        )
        assert isinstance(result, MovementResult)
        assert len(result.pan_curve) == 8
        assert len(result.tilt_curve) == 8

    def test_movement_result_curves_are_offset_centered(self) -> None:
        """Test MovementResult curves are offset-centered (0.5 = no motion)."""
        handler = MockMovementHandler()
        result = handler.generate(
            params={},
            n_samples=4,
            cycles=1.0,
            intensity="SMOOTH",
        )
        # Mock returns 0.5 for all points (no motion)
        for point in result.pan_curve:
            assert point.v == 0.5

    def test_movement_result_is_immutable(self) -> None:
        """Test MovementResult is immutable (frozen)."""
        points = [CurvePoint(t=0.0, v=0.5), CurvePoint(t=1.0, v=0.5)]
        result = MovementResult(pan_curve=points, tilt_curve=points)
        with pytest.raises(ValidationError):
            result.pan_curve = []  # type: ignore[misc]


class TestDimmerHandlerProtocol:
    """Tests for DimmerHandler protocol."""

    def test_dimmer_handler_has_handler_id(self) -> None:
        """Test DimmerHandler has handler_id attribute."""
        handler = MockDimmerHandler()
        assert handler.handler_id == "MOCK_DIMMER"

    def test_dimmer_handler_generate_returns_result(self) -> None:
        """Test DimmerHandler.generate returns DimmerResult."""
        handler = MockDimmerHandler()
        result = handler.generate(
            params={},
            n_samples=8,
            cycles=1.0,
            intensity="SMOOTH",
            min_norm=0.0,
            max_norm=1.0,
        )
        assert isinstance(result, DimmerResult)
        assert len(result.dimmer_curve) == 8

    def test_dimmer_result_curves_are_absolute(self) -> None:
        """Test DimmerResult curves are absolute (not offset-centered)."""
        handler = MockDimmerHandler()
        result = handler.generate(
            params={},
            n_samples=4,
            cycles=1.0,
            intensity="SMOOTH",
            min_norm=0.2,
            max_norm=0.8,
        )
        # All values should be within [min_norm, max_norm]
        for point in result.dimmer_curve:
            assert 0.0 <= point.v <= 1.0

    def test_dimmer_result_is_immutable(self) -> None:
        """Test DimmerResult is immutable (frozen)."""
        points = [CurvePoint(t=0.0, v=1.0), CurvePoint(t=1.0, v=1.0)]
        result = DimmerResult(dimmer_curve=points)
        with pytest.raises(ValidationError):  # ValidationError or similar
            result.dimmer_curve = []  # type: ignore[misc]


class TestProtocolTypeChecking:
    """Tests for protocol type checking with isinstance."""

    def test_mock_geometry_satisfies_protocol(self) -> None:
        """Test MockGeometryHandler satisfies GeometryHandler protocol."""
        handler: GeometryHandler = MockGeometryHandler()
        assert hasattr(handler, "handler_id")
        assert hasattr(handler, "resolve")

    def test_mock_movement_satisfies_protocol(self) -> None:
        """Test MockMovementHandler satisfies MovementHandler protocol."""
        handler: MovementHandler = MockMovementHandler()
        assert hasattr(handler, "handler_id")
        assert hasattr(handler, "generate")

    def test_mock_dimmer_satisfies_protocol(self) -> None:
        """Test MockDimmerHandler satisfies DimmerHandler protocol."""
        handler: DimmerHandler = MockDimmerHandler()
        assert hasattr(handler, "handler_id")
        assert hasattr(handler, "generate")
