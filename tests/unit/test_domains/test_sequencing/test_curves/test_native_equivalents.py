"""Tests for native curve custom implementations.

Verifies that custom implementations (point arrays) match expected
behavior of xLights native curves (parametric formulas).

Following TDD: These tests are written BEFORE implementation.
"""

import numpy as np

# ============================================================================
# FLAT_X Tests
# ============================================================================


def test_flat_x_constant_value():
    """Test FLAT_X returns constant value."""
    from blinkb0t.core.domains.sequencing.infrastructure.curves.functions.native_equivalents import (
        flat_x,
    )

    t = np.linspace(0, 1, 100)
    result = flat_x(t, p1=50.0)

    # All values should be 0.5 (50% normalized)
    assert np.allclose(result, 0.5)
    assert result.shape == t.shape


def test_flat_x_zero_value():
    """Test FLAT_X with 0% value."""
    from blinkb0t.core.domains.sequencing.infrastructure.curves.functions.native_equivalents import (
        flat_x,
    )

    t = np.linspace(0, 1, 10)
    result = flat_x(t, p1=0.0)

    assert np.allclose(result, 0.0)


def test_flat_x_full_value():
    """Test FLAT_X with 100% value."""
    from blinkb0t.core.domains.sequencing.infrastructure.curves.functions.native_equivalents import (
        flat_x,
    )

    t = np.linspace(0, 1, 10)
    result = flat_x(t, p1=100.0)

    assert np.allclose(result, 1.0)


def test_flat_x_partial_value():
    """Test FLAT_X with partial value."""
    from blinkb0t.core.domains.sequencing.infrastructure.curves.functions.native_equivalents import (
        flat_x,
    )

    t = np.linspace(0, 1, 10)
    result = flat_x(t, p1=75.0)

    assert np.allclose(result, 0.75)


# ============================================================================
# RAMP_X Tests
# ============================================================================


def test_ramp_x_linear_progression():
    """Test RAMP_X creates linear ramp from 0 to 100."""
    from blinkb0t.core.domains.sequencing.infrastructure.curves.functions.native_equivalents import (
        ramp_x,
    )

    t = np.array([0.0, 0.5, 1.0])
    result = ramp_x(t, p1=0.0, p2=100.0)

    # Should go from 0 to 1 linearly
    assert np.isclose(result[0], 0.0)
    assert np.isclose(result[1], 0.5)
    assert np.isclose(result[2], 1.0)


def test_ramp_x_reverse():
    """Test RAMP_X can go from high to low."""
    from blinkb0t.core.domains.sequencing.infrastructure.curves.functions.native_equivalents import (
        ramp_x,
    )

    t = np.array([0.0, 0.5, 1.0])
    result = ramp_x(t, p1=100.0, p2=0.0)

    # Should go from 1 to 0 linearly (reverse)
    assert np.isclose(result[0], 1.0)
    assert np.isclose(result[1], 0.5)
    assert np.isclose(result[2], 0.0)


def test_ramp_x_partial_range():
    """Test RAMP_X with partial range."""
    from blinkb0t.core.domains.sequencing.infrastructure.curves.functions.native_equivalents import (
        ramp_x,
    )

    t = np.linspace(0, 1, 5)
    result = ramp_x(t, p1=25.0, p2=75.0)

    # Should go from 0.25 to 0.75
    assert np.isclose(result[0], 0.25)
    assert np.isclose(result[-1], 0.75)
    assert all(0.25 <= v <= 0.75 for v in result)


# ============================================================================
# SINE_X Tests
# ============================================================================


def test_sine_x_full_oscillation():
    """Test SINE_X creates sine wave."""
    from blinkb0t.core.domains.sequencing.infrastructure.curves.functions.native_equivalents import (
        sine_x,
    )

    t = np.array([0.0, 0.25, 0.5, 0.75, 1.0])
    result = sine_x(t, p2=100.0, p4=50.0)

    # Sine wave centered at 0.5
    assert np.isclose(result[0], 0.5, atol=0.01)
    assert np.isclose(result[1], 1.0, atol=0.01)
    assert np.isclose(result[2], 0.5, atol=0.01)
    assert np.isclose(result[3], 0.0, atol=0.01)
    assert np.isclose(result[4], 0.5, atol=0.01)


def test_sine_x_bounded():
    """Test SINE_X stays within [0, 1] bounds."""
    from blinkb0t.core.domains.sequencing.infrastructure.curves.functions.native_equivalents import (
        sine_x,
    )

    t = np.linspace(0, 1, 100)
    result = sine_x(t, p2=100.0, p4=50.0)

    assert np.all(result >= 0.0)
    assert np.all(result <= 1.0)


def test_sine_x_reduced_amplitude():
    """Test SINE_X with reduced amplitude."""
    from blinkb0t.core.domains.sequencing.infrastructure.curves.functions.native_equivalents import (
        sine_x,
    )

    t = np.linspace(0, 1, 100)
    result = sine_x(t, p2=50.0, p4=50.0)  # Half amplitude

    # Should oscillate less
    assert np.all(result >= 0.25)
    assert np.all(result <= 0.75)


# ============================================================================
# ABS_SINE_X Tests
# ============================================================================


def test_abs_sine_x_always_positive():
    """Test ABS_SINE_X has no negative oscillations."""
    from blinkb0t.core.domains.sequencing.infrastructure.curves.functions.native_equivalents import (
        abs_sine_x,
    )

    t = np.linspace(0, 1, 100)
    result = abs_sine_x(t, p2=100.0, p4=50.0)

    # Absolute sine should never go below center
    assert np.all(result >= 0.0)
    assert np.all(result <= 1.0)


def test_abs_sine_x_peaks():
    """Test ABS_SINE_X has peaks at quarter points."""
    from blinkb0t.core.domains.sequencing.infrastructure.curves.functions.native_equivalents import (
        abs_sine_x,
    )

    t = np.array([0.0, 0.25, 0.5, 0.75, 1.0])
    result = abs_sine_x(t, p2=100.0, p4=0.0)  # Center at 0

    # Should have peaks at 0.25 and 0.75
    assert result[1] > result[0]  # Rising to peak
    assert result[3] > result[2]  # Rising to second peak


# ============================================================================
# PARABOLIC_X Tests
# ============================================================================


def test_parabolic_x_u_shape():
    """Test PARABOLIC_X creates U-shaped curve."""
    from blinkb0t.core.domains.sequencing.infrastructure.curves.functions.native_equivalents import (
        parabolic_x,
    )

    t = np.array([0.0, 0.5, 1.0])
    result = parabolic_x(t, p2=100.0, p4=50.0)

    # U-shape: high at edges, low in middle
    assert result[0] > result[1]  # Edge higher than middle
    assert result[2] > result[1]  # Edge higher than middle


def test_parabolic_x_bounded():
    """Test PARABOLIC_X stays within bounds."""
    from blinkb0t.core.domains.sequencing.infrastructure.curves.functions.native_equivalents import (
        parabolic_x,
    )

    t = np.linspace(0, 1, 100)
    result = parabolic_x(t, p2=100.0, p4=50.0)

    assert np.all(result >= 0.0)
    assert np.all(result <= 1.0)


# ============================================================================
# LOGARITHMIC_X Tests
# ============================================================================


def test_logarithmic_x_fast_start():
    """Test LOGARITHMIC_X has fast start, slow end."""
    from blinkb0t.core.domains.sequencing.infrastructure.curves.functions.native_equivalents import (
        logarithmic_x,
    )

    t = np.array([0.0, 0.1, 0.5, 0.9, 1.0])
    result = logarithmic_x(t, p1=0.0, p2=100.0)

    # Should progress more in first 10% than last 10%
    first_segment = result[1] - result[0]
    last_segment = result[4] - result[3]
    assert first_segment > last_segment


def test_logarithmic_x_range():
    """Test LOGARITHMIC_X respects start/end values."""
    from blinkb0t.core.domains.sequencing.infrastructure.curves.functions.native_equivalents import (
        logarithmic_x,
    )

    t = np.array([0.0, 1.0])
    result = logarithmic_x(t, p1=20.0, p2=80.0)

    assert np.isclose(result[0], 0.2, atol=0.01)
    assert np.isclose(result[1], 0.8, atol=0.01)


# ============================================================================
# EXPONENTIAL_X Tests
# ============================================================================


def test_exponential_x_slow_start():
    """Test EXPONENTIAL_X has slow start, fast end."""
    from blinkb0t.core.domains.sequencing.infrastructure.curves.functions.native_equivalents import (
        exponential_x,
    )

    t = np.array([0.0, 0.1, 0.5, 0.9, 1.0])
    result = exponential_x(t, p1=0.0, p2=100.0)

    # Should progress less in first 10% than last 10%
    first_segment = result[1] - result[0]
    last_segment = result[4] - result[3]
    assert first_segment < last_segment


def test_exponential_x_range():
    """Test EXPONENTIAL_X respects start/end values."""
    from blinkb0t.core.domains.sequencing.infrastructure.curves.functions.native_equivalents import (
        exponential_x,
    )

    t = np.array([0.0, 1.0])
    result = exponential_x(t, p1=20.0, p2=80.0)

    assert np.isclose(result[0], 0.2, atol=0.01)
    assert np.isclose(result[1], 0.8, atol=0.01)


# ============================================================================
# SAW_TOOTH_X Tests
# ============================================================================


def test_saw_tooth_x_repeating_ramp():
    """Test SAW_TOOTH_X creates repeating ramp pattern."""
    from blinkb0t.core.domains.sequencing.infrastructure.curves.functions.native_equivalents import (
        saw_tooth_x,
    )

    t = np.linspace(0, 1, 100)
    result = saw_tooth_x(t, p1=0.0, p2=100.0, p3=50.0)

    # Should have multiple cycles
    # Check for at least one reset (value drops back down)
    diffs = np.diff(result)
    has_reset = np.any(diffs < -0.5)  # Large negative jump indicates reset
    assert has_reset


def test_saw_tooth_x_range():
    """Test SAW_TOOTH_X respects min/max values."""
    from blinkb0t.core.domains.sequencing.infrastructure.curves.functions.native_equivalents import (
        saw_tooth_x,
    )

    t = np.linspace(0, 1, 100)
    result = saw_tooth_x(t, p1=25.0, p2=75.0, p3=30.0)

    assert np.all(result >= 0.24)  # Allow small tolerance
    assert np.all(result <= 0.76)


# ============================================================================
# Shape and Parameter Tests
# ============================================================================


def test_all_functions_accept_four_parameters():
    """Test all functions accept 4 xLights parameters."""
    from blinkb0t.core.domains.sequencing.infrastructure.curves.functions.native_equivalents import (
        abs_sine_x,
        exponential_x,
        flat_x,
        logarithmic_x,
        parabolic_x,
        ramp_x,
        saw_tooth_x,
        sine_x,
    )

    t = np.linspace(0, 1, 10)

    functions = [
        flat_x,
        ramp_x,
        sine_x,
        abs_sine_x,
        parabolic_x,
        logarithmic_x,
        exponential_x,
        saw_tooth_x,
    ]

    for func in functions:
        # Should accept all 4 parameters without error
        result = func(t, p1=10.0, p2=90.0, p3=50.0, p4=50.0)
        assert result.shape == t.shape, f"{func.__name__} returned wrong shape"


def test_all_functions_return_same_shape():
    """Test all functions return arrays of same shape as input."""
    from blinkb0t.core.domains.sequencing.infrastructure.curves.functions.native_equivalents import (
        abs_sine_x,
        exponential_x,
        flat_x,
        logarithmic_x,
        parabolic_x,
        ramp_x,
        saw_tooth_x,
        sine_x,
    )

    t = np.linspace(0, 1, 20)

    functions = [
        flat_x,
        ramp_x,
        sine_x,
        abs_sine_x,
        parabolic_x,
        logarithmic_x,
        exponential_x,
        saw_tooth_x,
    ]

    for func in functions:
        result = func(t)
        assert result.shape == t.shape, f"{func.__name__} returned wrong shape"
        assert len(result) == len(t), f"{func.__name__} returned wrong length"


def test_dmx_range_compliance():
    """Test all functions produce values in [0, 1] range (DMX safe)."""
    from blinkb0t.core.domains.sequencing.infrastructure.curves.functions.native_equivalents import (
        abs_sine_x,
        exponential_x,
        flat_x,
        logarithmic_x,
        parabolic_x,
        ramp_x,
        saw_tooth_x,
        sine_x,
    )

    t = np.linspace(0, 1, 100)

    functions = [
        flat_x,
        ramp_x,
        sine_x,
        abs_sine_x,
        parabolic_x,
        logarithmic_x,
        exponential_x,
        saw_tooth_x,
    ]

    for func in functions:
        result = func(t)
        assert np.all(result >= 0.0), f"{func.__name__} has values < 0"
        assert np.all(result <= 1.0), f"{func.__name__} has values > 1"


def test_functions_handle_edge_values():
    """Test functions handle t=0 and t=1 correctly."""
    from blinkb0t.core.domains.sequencing.infrastructure.curves.functions.native_equivalents import (
        exponential_x,
        logarithmic_x,
        ramp_x,
    )

    t = np.array([0.0, 1.0])

    # Ramp should go from p1 to p2
    result = ramp_x(t, p1=0.0, p2=100.0)
    assert np.isclose(result[0], 0.0)
    assert np.isclose(result[1], 1.0)

    # Logarithmic should go from p1 to p2
    result = logarithmic_x(t, p1=0.0, p2=100.0)
    assert np.isclose(result[0], 0.0, atol=0.01)
    assert np.isclose(result[1], 1.0, atol=0.01)

    # Exponential should go from p1 to p2
    result = exponential_x(t, p1=0.0, p2=100.0)
    assert np.isclose(result[0], 0.0, atol=0.01)
    assert np.isclose(result[1], 1.0, atol=0.01)


def test_functions_handle_single_point():
    """Test functions handle single time point."""
    from blinkb0t.core.domains.sequencing.infrastructure.curves.functions.native_equivalents import (
        flat_x,
        ramp_x,
    )

    t = np.array([0.5])

    # Should not crash and should return single value
    result = flat_x(t, p1=50.0)
    assert len(result) == 1
    assert np.isclose(result[0], 0.5)

    result = ramp_x(t, p1=0.0, p2=100.0)
    assert len(result) == 1
    assert np.isclose(result[0], 0.5)
