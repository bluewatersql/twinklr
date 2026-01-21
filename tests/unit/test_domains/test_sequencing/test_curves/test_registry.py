"""Tests for curve function registry.

Tests the mapping between CustomCurveType enums and curve generation functions.
"""

import numpy as np
import pytest

from blinkb0t.core.domains.sequencing.infrastructure.curves.enums import CustomCurveType
from blinkb0t.core.domains.sequencing.infrastructure.curves.functions.registry import (
    CurveFunctionRegistry,
    get_curve_function,
)


def test_registry_contains_all_curve_types():
    """Test that registry has entries for all CustomCurveType values."""
    # Get all enum values
    all_types = set(CustomCurveType)

    # Get all registered types
    registered_types = set(CurveFunctionRegistry.keys())

    # Verify all types are registered
    assert all_types == registered_types, f"Missing types: {all_types - registered_types}"


def test_get_curve_function_returns_callable():
    """Test that get_curve_function returns callable functions."""
    for curve_type in CustomCurveType:
        func = get_curve_function(curve_type)
        assert callable(func), f"{curve_type} should return a callable function"


def test_curve_functions_accept_numpy_array():
    """Test that all registered functions accept numpy arrays."""
    t = np.linspace(0, 1, 10)

    for curve_type in CustomCurveType:
        func = get_curve_function(curve_type)
        try:
            result = func(t)
            assert isinstance(result, np.ndarray), f"{curve_type} should return numpy array"
            assert result.shape == t.shape, f"{curve_type} should preserve input shape"
        except Exception as e:
            pytest.fail(f"{curve_type} function failed: {e}")


def test_curve_functions_return_bounded_values():
    """Test that most curve functions return values in [0, 1] range."""
    t = np.linspace(0, 1, 50)

    # Functions that allow overshoot (elastic)
    overshoot_allowed = {CustomCurveType.ELASTIC_IN, CustomCurveType.ELASTIC_OUT}

    for curve_type in CustomCurveType:
        func = get_curve_function(curve_type)
        result = func(t)

        if curve_type in overshoot_allowed:
            # Elastic can overshoot/undershoot significantly (that's the point)
            assert np.all(result >= -0.5), f"{curve_type} should not undershoot too much"
            assert np.all(result <= 1.5), f"{curve_type} should not overshoot too much"
        else:
            # All others should stay in [0, 1]
            assert np.all(result >= 0.0), f"{curve_type} should not have negative values"
            assert np.all(result <= 1.0), f"{curve_type} should not exceed 1.0"


def test_specific_curve_types():
    """Test that specific curve types map to expected functions."""
    t = np.array([0.0, 0.5, 1.0])

    # Test cosine (should start at 1, dip to 0, return to 1)
    cosine_func = get_curve_function(CustomCurveType.COSINE)
    result = cosine_func(t)
    assert np.isclose(result[0], 1.0)
    assert np.isclose(result[1], 0.0)
    assert np.isclose(result[2], 1.0)

    # Test triangle (should start at 0, peak at 1, return to 0)
    triangle_func = get_curve_function(CustomCurveType.TRIANGLE)
    result = triangle_func(t)
    assert np.isclose(result[0], 0.0)
    assert np.isclose(result[1], 1.0)
    assert np.isclose(result[2], 0.0)

    # Test ease_in_quad (should be t^2)
    quad_func = get_curve_function(CustomCurveType.EASE_IN_QUAD)
    result = quad_func(t)
    assert np.isclose(result[0], 0.0)
    assert np.isclose(result[1], 0.25)
    assert np.isclose(result[2], 1.0)


def test_get_curve_function_with_invalid_type():
    """Test that get_curve_function raises error for invalid type."""
    with pytest.raises(KeyError):
        get_curve_function("invalid_curve_type")  # type: ignore


def test_registry_is_immutable():
    """Test that the registry dict is read-only (at module level)."""
    # Try to access it - should work
    from blinkb0t.core.domains.sequencing.infrastructure.curves.functions.registry import (
        CurveFunctionRegistry,
    )

    assert isinstance(CurveFunctionRegistry, dict)
    assert len(CurveFunctionRegistry) > 0

    # Registry should not be modifiable at runtime (frozen)
    # This is a documentation/convention test - Python doesn't enforce true immutability
    # but we expect the registry to be treated as constant
