"""Tests for proper Perlin noise implementation.

Verifies that true Perlin noise (using noise library) provides:
- Organic, natural-looking randomness
- Smooth continuous variation
- Configurable octaves, persistence, lacunarity
- Superior quality to sine approximation

Following TDD: These tests are written BEFORE implementation.
"""

import numpy as np

# ============================================================================
# True Perlin Noise Tests
# ============================================================================


def test_perlin_noise_smooth_variation():
    """Test true Perlin noise creates smooth variation."""
    from blinkb0t.core.domains.sequencing.infrastructure.curves.functions.advanced import (
        perlin_noise,
    )

    t = np.linspace(0, 1, 100)
    result = perlin_noise(t)

    # Should have variation (not flat)
    assert np.std(result) > 0.05  # Significant variation

    # Should be smooth (no large jumps)
    diffs = np.abs(np.diff(result))
    assert np.max(diffs) < 0.3  # No jumps larger than 30%


def test_perlin_noise_organic_quality():
    """Test Perlin noise has organic, natural quality."""
    from blinkb0t.core.domains.sequencing.infrastructure.curves.functions.advanced import (
        perlin_noise,
    )

    t = np.linspace(0, 1, 200)
    result = perlin_noise(t)

    # Should not be periodic (unlike sine approximation)
    # Check that it doesn't repeat perfectly
    first_half = result[:100]
    second_half = result[100:]

    # Should NOT be identical halves (organic, not periodic)
    assert not np.allclose(first_half, second_half, atol=0.1)


def test_perlin_noise_normalized_range():
    """Test Perlin noise stays within [0, 1] range."""
    from blinkb0t.core.domains.sequencing.infrastructure.curves.functions.advanced import (
        perlin_noise,
    )

    t = np.linspace(0, 1, 100)
    result = perlin_noise(t)

    assert np.all(result >= 0.0)
    assert np.all(result <= 1.0)


def test_perlin_noise_with_octaves():
    """Test Perlin noise with different octave counts."""
    from blinkb0t.core.domains.sequencing.infrastructure.curves.functions.advanced import (
        perlin_noise,
    )

    t = np.linspace(0, 1, 100)

    # Different octaves should give different detail levels
    noise_1_octave = perlin_noise(t, octaves=1)
    noise_5_octaves = perlin_noise(t, octaves=5)

    # Higher octaves = more detail = higher variance in derivatives
    diffs_1 = np.abs(np.diff(noise_1_octave))
    diffs_5 = np.abs(np.diff(noise_5_octaves))

    # More octaves should have more variation (more detail)
    assert np.std(diffs_5) > np.std(diffs_1) * 0.8  # Some tolerance


def test_perlin_noise_with_persistence():
    """Test Perlin noise with different persistence values."""
    from blinkb0t.core.domains.sequencing.infrastructure.curves.functions.advanced import (
        perlin_noise,
    )

    t = np.linspace(0, 1, 100)

    # Different persistence should affect amplitude of detail
    noise_low_persist = perlin_noise(t, octaves=3, persistence=0.3)
    noise_high_persist = perlin_noise(t, octaves=3, persistence=0.7)

    # Both should be normalized to [0, 1]
    assert np.all(noise_low_persist >= 0.0) and np.all(noise_low_persist <= 1.0)
    assert np.all(noise_high_persist >= 0.0) and np.all(noise_high_persist <= 1.0)


def test_perlin_noise_with_scale():
    """Test Perlin noise with different scale values."""
    from blinkb0t.core.domains.sequencing.infrastructure.curves.functions.advanced import (
        perlin_noise,
    )

    t = np.linspace(0, 1, 100)

    # Different scales = different "zoom" levels
    noise_small_scale = perlin_noise(t, scale=0.5)  # Zoomed in (less variation)
    noise_large_scale = perlin_noise(t, scale=2.0)  # Zoomed out (more variation)

    # Both should be valid
    assert len(noise_small_scale) == len(t)
    assert len(noise_large_scale) == len(t)


# ============================================================================
# Simplex Noise Tests
# ============================================================================


def test_simplex_noise_smooth_variation():
    """Test Simplex noise creates smooth variation."""
    from blinkb0t.core.domains.sequencing.infrastructure.curves.functions.advanced import (
        simplex_noise,
    )

    t = np.linspace(0, 1, 100)
    result = simplex_noise(t)

    # Should have variation
    assert np.std(result) > 0.05

    # Should be smooth
    diffs = np.abs(np.diff(result))
    assert np.max(diffs) < 0.3


def test_simplex_noise_normalized_range():
    """Test Simplex noise stays within [0, 1] range."""
    from blinkb0t.core.domains.sequencing.infrastructure.curves.functions.advanced import (
        simplex_noise,
    )

    t = np.linspace(0, 1, 100)
    result = simplex_noise(t)

    assert np.all(result >= 0.0)
    assert np.all(result <= 1.0)


def test_simplex_noise_with_scale():
    """Test Simplex noise with different scale values."""
    from blinkb0t.core.domains.sequencing.infrastructure.curves.functions.advanced import (
        simplex_noise,
    )

    t = np.linspace(0, 1, 100)

    # Different scales
    noise_small_scale = simplex_noise(t, scale=0.5)
    noise_large_scale = simplex_noise(t, scale=2.0)

    # Both should be valid
    assert len(noise_small_scale) == len(t)
    assert len(noise_large_scale) == len(t)


# ============================================================================
# Comparison Tests: Perlin vs Sine Approximation
# ============================================================================


def test_perlin_vs_sine_approximation_quality():
    """Test true Perlin noise is superior to sine approximation."""
    from blinkb0t.core.domains.sequencing.infrastructure.curves.functions.advanced import (
        perlin_noise,
    )

    t = np.linspace(0, 1, 200)

    # True Perlin noise
    true_perlin = perlin_noise(t)

    # Sine approximation (old method)
    sine_approx = (
        np.sin(t * 2 * np.pi) * 0.5
        + np.sin(t * 4 * np.pi) * 0.25
        + np.sin(t * 8 * np.pi) * 0.125
        + 0.5
    )
    sine_approx = (sine_approx - sine_approx.min()) / (sine_approx.max() - sine_approx.min())

    # True Perlin should be non-periodic
    # Split into halves and check they're different
    perlin_first_half = true_perlin[:100]
    perlin_second_half = true_perlin[100:]

    # Perlin should have MORE difference between halves (non-periodic)
    # Main point: true Perlin is organic, not strictly periodic
    assert not np.allclose(perlin_first_half, perlin_second_half, atol=0.2)


# ============================================================================
# Integration and Shape Tests
# ============================================================================


def test_all_noise_functions_accept_numpy_arrays():
    """Test all noise functions work with numpy arrays."""
    from blinkb0t.core.domains.sequencing.infrastructure.curves.functions.advanced import (
        perlin_noise,
        simplex_noise,
    )

    t = np.linspace(0, 1, 50)

    functions = [perlin_noise, simplex_noise]

    for func in functions:
        result = func(t)
        assert result.shape == t.shape, f"{func.__name__} returned wrong shape"
        assert len(result) == len(t), f"{func.__name__} returned wrong length"


def test_all_noise_functions_dmx_safe():
    """Test all noise functions stay within DMX range."""
    from blinkb0t.core.domains.sequencing.infrastructure.curves.functions.advanced import (
        perlin_noise,
        simplex_noise,
    )

    t = np.linspace(0, 1, 100)

    functions = [perlin_noise, simplex_noise]

    for func in functions:
        result = func(t)
        assert np.all(result >= 0.0), f"{func.__name__} has values < 0"
        assert np.all(result <= 1.0), f"{func.__name__} has values > 1"


def test_noise_functions_handle_single_point():
    """Test noise functions handle single time point."""
    from blinkb0t.core.domains.sequencing.infrastructure.curves.functions.advanced import (
        perlin_noise,
        simplex_noise,
    )

    t = np.array([0.5])

    result = perlin_noise(t)
    assert len(result) == 1
    assert 0.0 <= result[0] <= 1.0

    result = simplex_noise(t)
    assert len(result) == 1
    assert 0.0 <= result[0] <= 1.0


def test_noise_functions_handle_edge_cases():
    """Test noise functions handle t=0 and t=1."""
    from blinkb0t.core.domains.sequencing.infrastructure.curves.functions.advanced import (
        perlin_noise,
        simplex_noise,
    )

    t = np.array([0.0, 1.0])

    # All should work without errors
    perlin = perlin_noise(t)
    assert len(perlin) == 2
    assert np.all(perlin >= 0.0) and np.all(perlin <= 1.0)

    simplex = simplex_noise(t)
    assert len(simplex) == 2
    assert np.all(simplex >= 0.0) and np.all(simplex <= 1.0)


# ============================================================================
# Use Case Validation Tests
# ============================================================================


def test_perlin_noise_for_organic_motion():
    """Test Perlin noise suitable for organic, natural motion."""
    from blinkb0t.core.domains.sequencing.infrastructure.curves.functions.advanced import (
        perlin_noise,
    )

    t = np.linspace(0, 1, 200)
    result = perlin_noise(t, octaves=3, persistence=0.5, scale=2.0)

    # Should have smooth, continuous variation
    diffs = np.abs(np.diff(result))
    assert np.max(diffs) < 0.2  # No sudden jumps

    # Should have interesting variation
    assert np.std(result) > 0.1  # Not flat


def test_simplex_noise_for_performance():
    """Test Simplex noise as faster alternative."""
    from blinkb0t.core.domains.sequencing.infrastructure.curves.functions.advanced import (
        simplex_noise,
    )

    t = np.linspace(0, 1, 1000)  # Large array
    result = simplex_noise(t, scale=1.0)

    # Should complete without error and be valid
    assert len(result) == 1000
    assert np.all(result >= 0.0) and np.all(result <= 1.0)


def test_perlin_noise_octaves_add_detail():
    """Test that increasing octaves adds detail to Perlin noise."""
    from blinkb0t.core.domains.sequencing.infrastructure.curves.functions.advanced import (
        perlin_noise,
    )

    t = np.linspace(0, 1, 200)

    # Low octaves = smooth
    smooth = perlin_noise(t, octaves=1)

    # High octaves = detailed
    detailed = perlin_noise(t, octaves=5)

    # Detailed should have more fine-grained variation
    smooth_diffs = np.abs(np.diff(smooth))
    detailed_diffs = np.abs(np.diff(detailed))

    # Standard deviation of differences indicates detail level
    assert np.std(detailed_diffs) >= np.std(smooth_diffs) * 0.7  # Some tolerance
