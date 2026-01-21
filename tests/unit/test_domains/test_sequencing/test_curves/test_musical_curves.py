"""Tests for musical curves optimized for beat-aligned timing.

Verifies that musical curves provide:
- Sharp attack/release for percussive elements
- Smooth attack/decay for swells and builds
- Beat-aligned pulsing

Following TDD: These tests are written BEFORE implementation.
"""

import numpy as np

# ============================================================================
# MUSICAL_ACCENT Tests (Sharp attack, smooth decay)
# ============================================================================


def test_musical_accent_sharp_attack():
    """Test MUSICAL_ACCENT has sharp attack phase."""
    from blinkb0t.core.domains.sequencing.infrastructure.curves.functions.musical import (
        musical_accent,
    )

    t = np.linspace(0, 1, 100)
    result = musical_accent(t)

    # Sharp attack: should reach high value quickly (within first 10%)
    attack_idx = int(0.1 * len(result))
    assert result[attack_idx] > 0.8  # Near peak by 10%


def test_musical_accent_smooth_decay():
    """Test MUSICAL_ACCENT has smooth exponential decay."""
    from blinkb0t.core.domains.sequencing.infrastructure.curves.functions.musical import (
        musical_accent,
    )

    t = np.linspace(0, 1, 100)
    result = musical_accent(t)

    # Smooth decay: should decrease gradually
    # Check decay phase (after 10%)
    decay_start_idx = int(0.1 * len(result))
    decay_values = result[decay_start_idx:]

    # Should be monotonically decreasing
    diffs = np.diff(decay_values)
    assert np.all(diffs <= 0.01)  # Decreasing (with small tolerance)


def test_musical_accent_percussive_shape():
    """Test MUSICAL_ACCENT has percussive envelope shape."""
    from blinkb0t.core.domains.sequencing.infrastructure.curves.functions.musical import (
        musical_accent,
    )

    t = np.linspace(0, 1, 100)
    result = musical_accent(t)

    # Percussive: high at start, low at end
    assert result[0] >= 0.0  # Starts at or near 0
    peak_idx = int(0.1 * len(result))
    assert result[peak_idx] > 0.8  # Quick rise to peak
    assert result[-1] < 0.5  # Decayed significantly by end


def test_musical_accent_dmx_safe():
    """Test MUSICAL_ACCENT stays within DMX range."""
    from blinkb0t.core.domains.sequencing.infrastructure.curves.functions.musical import (
        musical_accent,
    )

    t = np.linspace(0, 1, 100)
    result = musical_accent(t)

    assert np.all(result >= 0.0)
    assert np.all(result <= 1.0)


# ============================================================================
# MUSICAL_SWELL Tests (Smooth rise, sharp cutoff)
# ============================================================================


def test_musical_swell_smooth_rise():
    """Test MUSICAL_SWELL has smooth gradual rise."""
    from blinkb0t.core.domains.sequencing.infrastructure.curves.functions.musical import (
        musical_swell,
    )

    t = np.linspace(0, 1, 100)
    result = musical_swell(t)

    # Smooth rise: should increase gradually over first 90%
    rise_end_idx = int(0.9 * len(result))
    rise_values = result[:rise_end_idx]

    # Should be monotonically increasing
    diffs = np.diff(rise_values)
    assert np.all(diffs >= -0.01)  # Increasing (with small tolerance)


def test_musical_swell_sharp_cutoff():
    """Test MUSICAL_SWELL has sharp cutoff at end."""
    from blinkb0t.core.domains.sequencing.infrastructure.curves.functions.musical import (
        musical_swell,
    )

    t = np.linspace(0, 1, 100)
    result = musical_swell(t)

    # Sharp cutoff: should drop quickly in last 10%
    cutoff_start_idx = int(0.9 * len(result))
    assert result[cutoff_start_idx] > 0.8  # High before cutoff
    assert result[-1] < 0.2  # Low at end (sharp drop)


def test_musical_swell_buildup_shape():
    """Test MUSICAL_SWELL has build-up envelope shape."""
    from blinkb0t.core.domains.sequencing.infrastructure.curves.functions.musical import (
        musical_swell,
    )

    t = np.linspace(0, 1, 100)
    result = musical_swell(t)

    # Build-up: low at start, high at peak, drops at end
    assert result[0] < 0.2  # Starts low
    peak_idx = int(0.9 * len(result))
    assert result[peak_idx] > 0.8  # High at 90%
    assert result[-1] < 0.2  # Drops at end


def test_musical_swell_dmx_safe():
    """Test MUSICAL_SWELL stays within DMX range."""
    from blinkb0t.core.domains.sequencing.infrastructure.curves.functions.musical import (
        musical_swell,
    )

    t = np.linspace(0, 1, 100)
    result = musical_swell(t)

    assert np.all(result >= 0.0)
    assert np.all(result <= 1.0)


def test_musical_accent_and_swell_complementary():
    """Test MUSICAL_ACCENT and MUSICAL_SWELL are complementary shapes."""
    from blinkb0t.core.domains.sequencing.infrastructure.curves.functions.musical import (
        musical_accent,
        musical_swell,
    )

    t = np.linspace(0, 1, 100)
    accent = musical_accent(t)
    swell = musical_swell(t)

    # Accent: high early, low late
    # Swell: low early, high late (before cutoff)
    assert accent[10] > swell[10]  # Accent higher early
    assert swell[80] > accent[80]  # Swell higher late (before cutoff)


# ============================================================================
# BEAT_PULSE Tests (Beat-aligned pulsing)
# ============================================================================


def test_beat_pulse_default_oscillation():
    """Test BEAT_PULSE creates oscillating pattern."""
    from blinkb0t.core.domains.sequencing.infrastructure.curves.functions.musical import (
        beat_pulse,
    )

    t = np.linspace(0, 1, 100)
    result = beat_pulse(t)

    # Should oscillate (not constant)
    assert np.std(result) > 0.1  # Has variation
    assert result.min() < result.max()  # Not flat


def test_beat_pulse_frequency():
    """Test BEAT_PULSE with different beat subdivisions."""
    from blinkb0t.core.domains.sequencing.infrastructure.curves.functions.musical import (
        beat_pulse,
    )

    t = np.linspace(0, 1, 1000)

    # 4 pulses per cycle (quarter notes)
    pulse_4 = beat_pulse(t, beat_subdivision=4)

    # 8 pulses per cycle (eighth notes)
    pulse_8 = beat_pulse(t, beat_subdivision=8)

    # pulse_8 should have more oscillations
    # Count zero crossings (rough frequency measure)
    crossings_4 = np.sum(np.diff(np.sign(pulse_4 - 0.5)) != 0)
    crossings_8 = np.sum(np.diff(np.sign(pulse_8 - 0.5)) != 0)

    assert crossings_8 > crossings_4  # More oscillations with higher subdivision


def test_beat_pulse_range():
    """Test BEAT_PULSE oscillates around 0.5."""
    from blinkb0t.core.domains.sequencing.infrastructure.curves.functions.musical import (
        beat_pulse,
    )

    t = np.linspace(0, 1, 100)
    result = beat_pulse(t)

    # Should oscillate around 0.5
    assert 0.4 < np.mean(result) < 0.6  # Average near 0.5


def test_beat_pulse_dmx_safe():
    """Test BEAT_PULSE stays within DMX range."""
    from blinkb0t.core.domains.sequencing.infrastructure.curves.functions.musical import (
        beat_pulse,
    )

    t = np.linspace(0, 1, 100)
    result = beat_pulse(t)

    assert np.all(result >= 0.0)
    assert np.all(result <= 1.0)


def test_beat_pulse_custom_subdivision():
    """Test BEAT_PULSE with custom beat subdivision."""
    from blinkb0t.core.domains.sequencing.infrastructure.curves.functions.musical import (
        beat_pulse,
    )

    t = np.linspace(0, 1, 100)

    # Test various subdivisions
    for subdivision in [1, 2, 4, 8, 16]:
        result = beat_pulse(t, beat_subdivision=subdivision)
        assert len(result) == len(t)
        assert np.all(result >= 0.0) and np.all(result <= 1.0)


# ============================================================================
# Integration and Shape Tests
# ============================================================================


def test_all_musical_curves_accept_numpy_arrays():
    """Test all musical curves work with numpy arrays."""
    from blinkb0t.core.domains.sequencing.infrastructure.curves.functions.musical import (
        beat_pulse,
        musical_accent,
        musical_swell,
    )

    t = np.linspace(0, 1, 50)

    functions = [musical_accent, musical_swell, beat_pulse]

    for func in functions:
        result = func(t)
        assert result.shape == t.shape, f"{func.__name__} returned wrong shape"
        assert len(result) == len(t), f"{func.__name__} returned wrong length"


def test_all_musical_curves_dmx_safe():
    """Test all musical curves stay within DMX range."""
    from blinkb0t.core.domains.sequencing.infrastructure.curves.functions.musical import (
        beat_pulse,
        musical_accent,
        musical_swell,
    )

    t = np.linspace(0, 1, 100)

    functions = [musical_accent, musical_swell, beat_pulse]

    for func in functions:
        result = func(t)
        assert np.all(result >= 0.0), f"{func.__name__} has values < 0"
        assert np.all(result <= 1.0), f"{func.__name__} has values > 1"


def test_musical_curves_start_and_end():
    """Test musical curves have appropriate start/end values."""
    from blinkb0t.core.domains.sequencing.infrastructure.curves.functions.musical import (
        beat_pulse,
        musical_accent,
        musical_swell,
    )

    t = np.linspace(0, 1, 100)

    # Musical accent: starts low, rises, decays
    accent = musical_accent(t)
    assert accent[0] < 0.3  # Starts low

    # Musical swell: starts low, rises, drops
    swell = musical_swell(t)
    assert swell[0] < 0.3  # Starts low

    # Beat pulse: oscillates
    pulse = beat_pulse(t)
    # Should have some variation
    assert np.std(pulse) > 0.1


def test_musical_curves_handle_single_point():
    """Test musical curves handle single time point."""
    from blinkb0t.core.domains.sequencing.infrastructure.curves.functions.musical import (
        musical_accent,
        musical_swell,
    )

    t = np.array([0.5])

    result = musical_accent(t)
    assert len(result) == 1
    assert 0.0 <= result[0] <= 1.0

    result = musical_swell(t)
    assert len(result) == 1
    assert 0.0 <= result[0] <= 1.0


def test_musical_curves_handle_edge_cases():
    """Test musical curves handle t=0 and t=1."""
    from blinkb0t.core.domains.sequencing.infrastructure.curves.functions.musical import (
        musical_accent,
        musical_swell,
    )

    t = np.array([0.0, 1.0])

    # All should work without errors
    accent = musical_accent(t)
    assert len(accent) == 2
    assert np.all(accent >= 0.0) and np.all(accent <= 1.0)

    swell = musical_swell(t)
    assert len(swell) == 2
    assert np.all(swell >= 0.0) and np.all(swell <= 1.0)


# ============================================================================
# Use Case Validation Tests
# ============================================================================


def test_musical_accent_for_drum_hits():
    """Test MUSICAL_ACCENT suitable for percussive drum hits."""
    from blinkb0t.core.domains.sequencing.infrastructure.curves.functions.musical import (
        musical_accent,
    )

    t = np.linspace(0, 1, 100)
    result = musical_accent(t)

    # Drum hit: instant attack, quick decay
    # Should have peak very early
    peak_idx = np.argmax(result)
    assert peak_idx < 15  # Peak within first 15%

    # Should decay significantly
    assert result[-1] < result[peak_idx] * 0.5  # At least 50% decay


def test_musical_swell_for_buildups():
    """Test MUSICAL_SWELL suitable for musical buildups."""
    from blinkb0t.core.domains.sequencing.infrastructure.curves.functions.musical import (
        musical_swell,
    )

    t = np.linspace(0, 1, 100)
    result = musical_swell(t)

    # Build-up: gradual rise to climax
    # Should have peak near end (before cutoff)
    peak_idx = np.argmax(result)
    assert peak_idx > 80  # Peak near end (in last 20%)

    # Should start low and build
    assert result[10] < result[50] < result[peak_idx]


def test_beat_pulse_for_rhythmic_effects():
    """Test BEAT_PULSE creates rhythmic pulsing."""
    from blinkb0t.core.domains.sequencing.infrastructure.curves.functions.musical import (
        beat_pulse,
    )

    t = np.linspace(0, 1, 400)  # 4 bars @ 100 points/bar
    result = beat_pulse(t, beat_subdivision=4)

    # Should have regular peaks (4 in this case)
    # Find local maxima
    peaks = []
    for i in range(1, len(result) - 1):
        if (
            result[i] > result[i - 1]
            and result[i] > result[i + 1]
            and result[i] > 0.7  # Significant peak
        ):
            peaks.append(i)

    # Should have approximately 4 peaks (quarter notes)
    assert 3 <= len(peaks) <= 5  # Allow some tolerance
