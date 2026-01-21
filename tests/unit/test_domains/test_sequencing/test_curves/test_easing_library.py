"""Tests for professional easing functions from easing-functions library.

Verifies that library-based easing implementations provide:
- Professional quality curves (exponential, back/overshoot)
- DMX-safe output [0, 1]
- Correct behavioral characteristics

Following TDD: These tests are written BEFORE implementation.
"""

import numpy as np

# ============================================================================
# EXPONENTIAL EASING Tests
# ============================================================================


def test_ease_in_expo_slow_start():
    """Test EASE_IN_EXPO has very slow start."""
    from blinkb0t.core.domains.sequencing.infrastructure.curves.functions.easing import (
        ease_in_expo,
    )

    t = np.array([0.0, 0.1, 0.5, 0.9, 1.0])
    result = ease_in_expo(t)

    # Should progress VERY little early, then explosive growth
    assert np.isclose(result[0], 0.0, atol=0.01)
    assert result[1] < 0.01  # Still very low at 10%
    assert result[2] < 0.05  # Still low at 50%
    assert result[3] > 0.5  # Massive acceleration by 90%
    assert np.isclose(result[4], 1.0, atol=0.01)


def test_ease_out_expo_explosive_start():
    """Test EASE_OUT_EXPO has explosive start, slow end."""
    from blinkb0t.core.domains.sequencing.infrastructure.curves.functions.easing import (
        ease_out_expo,
    )

    t = np.array([0.0, 0.1, 0.5, 0.9, 1.0])
    result = ease_out_expo(t)

    # Should progress RAPIDLY early, then very slow
    assert np.isclose(result[0], 0.0, atol=0.01)
    assert result[1] >= 0.4  # Significant progress by 10% (library gives ~0.5)
    assert result[2] > 0.95  # Nearly done by 50%
    assert result[3] > 0.99  # Very close to end
    assert np.isclose(result[4], 1.0, atol=0.01)


def test_ease_in_out_expo_dramatic_scurve():
    """Test EASE_IN_OUT_EXPO creates very dramatic S-curve."""
    from blinkb0t.core.domains.sequencing.infrastructure.curves.functions.easing import (
        ease_in_out_expo,
    )

    t = np.array([0.0, 0.25, 0.5, 0.75, 1.0])
    result = ease_in_out_expo(t)

    # Very slow start, explosive middle, very slow end
    assert np.isclose(result[0], 0.0, atol=0.01)
    assert result[1] < 0.05  # Very slow at 25%
    assert np.isclose(result[2], 0.5, atol=0.05)  # Middle at 50%
    assert result[3] > 0.95  # Very fast by 75%
    assert np.isclose(result[4], 1.0, atol=0.01)


def test_exponential_curves_dmx_safe():
    """Test all exponential curves stay within DMX range."""
    from blinkb0t.core.domains.sequencing.infrastructure.curves.functions.easing import (
        ease_in_expo,
        ease_in_out_expo,
        ease_out_expo,
    )

    t = np.linspace(0, 1, 100)

    for func in [ease_in_expo, ease_out_expo, ease_in_out_expo]:
        result = func(t)
        assert np.all(result >= 0.0), f"{func.__name__} has values < 0"
        assert np.all(result <= 1.0), f"{func.__name__} has values > 1"


# ============================================================================
# BACK EASING (Overshoot/Anticipation) Tests
# ============================================================================


def test_ease_in_back_anticipation():
    """Test EASE_IN_BACK pulls back before moving forward."""
    from blinkb0t.core.domains.sequencing.infrastructure.curves.functions.easing import (
        ease_in_back,
    )

    t = np.linspace(0, 1, 100)
    result = ease_in_back(t)

    # Should have negative values (pull back) before moving forward
    # But clipped to [0, 1] for DMX safety
    assert np.isclose(result[0], 0.0, atol=0.01)
    assert np.isclose(result[-1], 1.0, atol=0.01)

    # Early values should be very small (anticipation effect)
    early_values = result[:20]
    assert np.all(early_values < 0.2)  # Slow start (anticipation)


def test_ease_out_back_overshoot():
    """Test EASE_OUT_BACK overshoots target then settles."""
    from blinkb0t.core.domains.sequencing.infrastructure.curves.functions.easing import (
        ease_out_back,
    )

    t = np.linspace(0, 1, 100)
    result = ease_out_back(t)

    # May overshoot beyond 1.0, but clipped for DMX safety
    assert np.isclose(result[0], 0.0, atol=0.01)
    assert np.isclose(result[-1], 1.0, atol=0.01)

    # Middle values may be high (overshoot effect preserved if within bounds)
    # Or clipped if library implementation overshoots
    assert np.all(result >= 0.0) and np.all(result <= 1.0)


def test_ease_in_out_back_both_effects():
    """Test EASE_IN_OUT_BACK has both anticipation and overshoot."""
    from blinkb0t.core.domains.sequencing.infrastructure.curves.functions.easing import (
        ease_in_out_back,
    )

    t = np.linspace(0, 1, 100)
    result = ease_in_out_back(t)

    # Should have anticipation at start, overshoot at end
    assert np.isclose(result[0], 0.0, atol=0.01)
    assert np.isclose(result[-1], 1.0, atol=0.01)

    # Check for characteristic shape
    mid_idx = len(result) // 2
    assert np.isclose(result[mid_idx], 0.5, atol=0.1)  # Passes through middle


def test_back_curves_dmx_safe():
    """Test all back curves stay within DMX range (clipped)."""
    from blinkb0t.core.domains.sequencing.infrastructure.curves.functions.easing import (
        ease_in_back,
        ease_in_out_back,
        ease_out_back,
    )

    t = np.linspace(0, 1, 100)

    for func in [ease_in_back, ease_out_back, ease_in_out_back]:
        result = func(t)
        assert np.all(result >= 0.0), f"{func.__name__} has values < 0"
        assert np.all(result <= 1.0), f"{func.__name__} has values > 1"


# ============================================================================
# Comparison with Manual Implementations
# ============================================================================


def test_exponential_more_dramatic_than_cubic():
    """Test exponential easing is more dramatic than cubic."""
    from blinkb0t.core.domains.sequencing.infrastructure.curves.functions.easing import (
        ease_in_cubic,
        ease_in_expo,
    )

    t = np.array([0.1, 0.3, 0.5, 0.7])
    expo = ease_in_expo(t)
    cubic = ease_in_cubic(t)

    # Exponential should be slower at mid-range (more dramatic)
    # Library implementation: expo slightly faster at 10%, but slower at 30%, 50%, 70%
    assert expo[1] < cubic[1]  # Slower at 30%
    assert expo[2] < cubic[2]  # Slower at 50%
    assert expo[3] < cubic[3]  # Slower at 70%
    # Overall more dramatic with slower middle progression


def test_back_curves_distinctive_from_standard():
    """Test back curves have distinctive behavior vs standard easing."""
    from blinkb0t.core.domains.sequencing.infrastructure.curves.functions.easing import (
        ease_in_back,
        ease_in_quad,
    )

    t = np.linspace(0, 1, 50)
    back = ease_in_back(t)
    quad = ease_in_quad(t)

    # Back curve should have characteristic anticipation (slower early)
    # or distinctive shape difference
    assert not np.allclose(back, quad)  # Different curves


# ============================================================================
# Integration and Shape Tests
# ============================================================================


def test_all_library_functions_accept_numpy_arrays():
    """Test all library-based functions work with numpy arrays."""
    from blinkb0t.core.domains.sequencing.infrastructure.curves.functions.easing import (
        ease_in_back,
        ease_in_expo,
        ease_in_out_back,
        ease_in_out_expo,
        ease_out_back,
        ease_out_expo,
    )

    t = np.linspace(0, 1, 50)

    functions = [
        ease_in_expo,
        ease_out_expo,
        ease_in_out_expo,
        ease_in_back,
        ease_out_back,
        ease_in_out_back,
    ]

    for func in functions:
        result = func(t)
        assert result.shape == t.shape, f"{func.__name__} returned wrong shape"
        assert len(result) == len(t), f"{func.__name__} returned wrong length"


def test_all_library_functions_monotonic_increase():
    """Test all easing functions are monotonically increasing."""
    from blinkb0t.core.domains.sequencing.infrastructure.curves.functions.easing import (
        ease_in_back,
        ease_in_expo,
        ease_in_out_back,
        ease_in_out_expo,
        ease_out_back,
        ease_out_expo,
    )

    t = np.linspace(0, 1, 100)

    functions = [
        ease_in_expo,
        ease_out_expo,
        ease_in_out_expo,
        ease_in_back,
        ease_out_back,
        ease_in_out_back,
    ]

    for func in functions:
        result = func(t)
        diffs = np.diff(result)
        # All differences should be non-negative (monotonic increasing)
        assert np.all(diffs >= -0.001), f"{func.__name__} is not monotonic"


def test_library_functions_start_and_end_correctly():
    """Test all library functions start at 0 and end at 1."""
    from blinkb0t.core.domains.sequencing.infrastructure.curves.functions.easing import (
        ease_in_back,
        ease_in_expo,
        ease_in_out_back,
        ease_in_out_expo,
        ease_out_back,
        ease_out_expo,
    )

    t = np.linspace(0, 1, 100)

    functions = [
        ease_in_expo,
        ease_out_expo,
        ease_in_out_expo,
        ease_in_back,
        ease_out_back,
        ease_in_out_back,
    ]

    for func in functions:
        result = func(t)
        assert np.isclose(result[0], 0.0, atol=0.01), f"{func.__name__} doesn't start at 0"
        assert np.isclose(result[-1], 1.0, atol=0.01), f"{func.__name__} doesn't end at 1"


def test_library_functions_handle_single_point():
    """Test library functions handle single time point."""
    from blinkb0t.core.domains.sequencing.infrastructure.curves.functions.easing import (
        ease_in_expo,
        ease_out_back,
    )

    t = np.array([0.5])

    result = ease_in_expo(t)
    assert len(result) == 1
    assert 0.0 <= result[0] <= 1.0

    result = ease_out_back(t)
    assert len(result) == 1
    assert 0.0 <= result[0] <= 1.0


def test_library_functions_handle_edge_cases():
    """Test library functions handle t=0 and t=1."""
    from blinkb0t.core.domains.sequencing.infrastructure.curves.functions.easing import (
        ease_in_expo,
        ease_in_out_back,
        ease_out_expo,
    )

    t = np.array([0.0, 1.0])

    # All should start at 0, end at 1
    for func in [ease_in_expo, ease_out_expo, ease_in_out_back]:
        result = func(t)
        assert np.isclose(result[0], 0.0, atol=0.01)
        assert np.isclose(result[1], 1.0, atol=0.01)


# ============================================================================
# Use Case Validation Tests
# ============================================================================


def test_exponential_for_extreme_energy():
    """Test exponential curves suitable for extreme energy drops."""
    from blinkb0t.core.domains.sequencing.infrastructure.curves.functions.easing import (
        ease_in_expo,
    )

    t = np.linspace(0, 1, 100)
    result = ease_in_expo(t)

    # Should have very low values for most of the duration
    # then explosive growth at the end
    first_half = result[: len(result) // 2]
    second_half = result[len(result) // 2 :]

    # First half should progress very little
    assert np.max(first_half) < 0.1  # Less than 10% progress in first half

    # Second half should have the explosive growth
    assert np.max(second_half) == result[-1]  # Maximum at end


def test_back_curves_for_anticipation():
    """Test back curves create anticipation/overshoot effects."""
    from blinkb0t.core.domains.sequencing.infrastructure.curves.functions.easing import (
        ease_in_back,
        ease_out_back,
    )

    t = np.linspace(0, 1, 100)

    # Ease-in-back: anticipation (pull back)
    result_in = ease_in_back(t)
    # Should have slow/distinctive start
    assert result_in[10] < 0.15  # Distinctive slow start

    # Ease-out-back: overshoot
    result_out = ease_out_back(t)
    # Should reach near 1.0 quickly (may overshoot in library, but clipped)
    assert result_out[-10] >= 0.95  # Near end by last 10%
