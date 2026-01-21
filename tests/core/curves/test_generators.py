"""Tests for Curve Generation Helpers.

Tests standard curve generators (linear, hold, sine, triangle, pulse).
All generators produce uniformly-sampled points in [0, 1].
"""

import pytest

from blinkb0t.core.curves.generators import (
    generate_hold,
    generate_linear,
    generate_pulse,
    generate_sine,
    generate_triangle,
)


class TestGenerateLinear:
    """Tests for linear curve generator."""

    def test_linear_produces_n_samples(self) -> None:
        """Test linear produces exactly n_samples points."""
        result = generate_linear(n_samples=8)
        assert len(result) == 8

    def test_linear_values_in_0_to_1(self) -> None:
        """Test linear values are in [0, 1]."""
        result = generate_linear(n_samples=10)
        for p in result:
            assert 0.0 <= p.v <= 1.0
            assert 0.0 <= p.t <= 1.0

    def test_linear_ascending_default(self) -> None:
        """Test linear is ascending by default (0 → 1)."""
        result = generate_linear(n_samples=4)
        # t values: 0.0, 0.25, 0.5, 0.75
        # v values should be: 0.0, 0.333..., 0.666..., 1.0
        assert result[0].v == 0.0
        assert abs(result[-1].v - 1.0) < 1e-10  # Last value approaches 1.0

    def test_linear_descending(self) -> None:
        """Test linear descending (1 → 0)."""
        result = generate_linear(n_samples=4, ascending=False)
        assert result[0].v == 1.0
        assert abs(result[-1].v - 0.0) < 0.01  # Last value approaches 0.0


class TestGenerateHold:
    """Tests for hold (constant) curve generator."""

    def test_hold_produces_n_samples(self) -> None:
        """Test hold produces exactly n_samples points."""
        result = generate_hold(n_samples=8, value=0.5)
        assert len(result) == 8

    def test_hold_all_same_value(self) -> None:
        """Test hold produces constant value."""
        result = generate_hold(n_samples=5, value=0.7)
        for p in result:
            assert p.v == 0.7

    def test_hold_default_value_is_one(self) -> None:
        """Test hold default value is 1.0."""
        result = generate_hold(n_samples=3)
        for p in result:
            assert p.v == 1.0

    def test_hold_value_clamped(self) -> None:
        """Test hold value is clamped to [0, 1]."""
        # Values > 1 should be clamped
        result = generate_hold(n_samples=2, value=1.5)
        assert result[0].v == 1.0

        # Values < 0 should be clamped
        result = generate_hold(n_samples=2, value=-0.5)
        assert result[0].v == 0.0


class TestGenerateSine:
    """Tests for sine wave generator."""

    def test_sine_produces_n_samples(self) -> None:
        """Test sine produces exactly n_samples points."""
        result = generate_sine(n_samples=16, cycles=1.0)
        assert len(result) == 16

    def test_sine_values_in_0_to_1(self) -> None:
        """Test sine values are in [0, 1]."""
        result = generate_sine(n_samples=32, cycles=2.0)
        for p in result:
            assert 0.0 <= p.v <= 1.0

    def test_sine_correct_number_of_peaks_one_cycle(self) -> None:
        """Test sine wave has correct peak for one cycle."""
        result = generate_sine(n_samples=64, cycles=1.0)
        # One cycle should have one maximum near v=1.0
        max_val = max(p.v for p in result)
        assert max_val > 0.95  # Peak should be close to 1.0

    def test_sine_correct_number_of_peaks_two_cycles(self) -> None:
        """Test sine wave has correct peaks for two cycles."""
        result = generate_sine(n_samples=64, cycles=2.0)
        # Find local maxima (values higher than neighbors)
        peaks = []
        for i in range(1, len(result) - 1):
            if (
                result[i].v > result[i - 1].v
                and result[i].v > result[i + 1].v
                and result[i].v > 0.9
            ):  # Only count significant peaks
                peaks.append(result[i])
        assert len(peaks) == 2

    def test_sine_starts_at_midpoint(self) -> None:
        """Test sine starts at midpoint (0.5) by default."""
        result = generate_sine(n_samples=8, cycles=1.0)
        assert abs(result[0].v - 0.5) < 0.01


class TestGenerateTriangle:
    """Tests for triangle wave generator."""

    def test_triangle_produces_n_samples(self) -> None:
        """Test triangle produces exactly n_samples points."""
        result = generate_triangle(n_samples=16, cycles=1.0)
        assert len(result) == 16

    def test_triangle_values_in_0_to_1(self) -> None:
        """Test triangle values are in [0, 1]."""
        result = generate_triangle(n_samples=32, cycles=1.0)
        for p in result:
            assert 0.0 <= p.v <= 1.0

    def test_triangle_shape_one_cycle(self) -> None:
        """Test triangle wave shape for one cycle."""
        result = generate_triangle(n_samples=64, cycles=1.0)
        # Should start at 0, rise to 1, then fall back to 0
        # First quarter should be rising
        quarter = len(result) // 4
        assert result[quarter].v > result[0].v

    def test_triangle_reaches_peak_and_trough(self) -> None:
        """Test triangle reaches both 0 and 1."""
        result = generate_triangle(n_samples=64, cycles=1.0)
        max_val = max(p.v for p in result)
        min_val = min(p.v for p in result)
        assert max_val > 0.95
        assert min_val < 0.05


class TestGeneratePulse:
    """Tests for pulse wave generator."""

    def test_pulse_produces_n_samples(self) -> None:
        """Test pulse produces exactly n_samples points."""
        result = generate_pulse(n_samples=16, cycles=1.0, duty_cycle=0.5)
        assert len(result) == 16

    def test_pulse_values_in_0_to_1(self) -> None:
        """Test pulse values are in [0, 1]."""
        result = generate_pulse(n_samples=32, cycles=1.0, duty_cycle=0.5)
        for p in result:
            assert 0.0 <= p.v <= 1.0

    def test_pulse_duty_cycle_50_percent(self) -> None:
        """Test pulse 50% duty cycle has equal high/low."""
        result = generate_pulse(n_samples=64, cycles=1.0, duty_cycle=0.5)
        high_count = sum(1 for p in result if p.v > 0.5)
        low_count = sum(1 for p in result if p.v <= 0.5)
        # Should be roughly equal (allow some tolerance)
        assert abs(high_count - low_count) < 5

    def test_pulse_duty_cycle_25_percent(self) -> None:
        """Test pulse 25% duty cycle has more lows."""
        result = generate_pulse(n_samples=64, cycles=1.0, duty_cycle=0.25)
        high_count = sum(1 for p in result if p.v > 0.5)
        low_count = sum(1 for p in result if p.v <= 0.5)
        # Config 25% high, 75% low
        assert low_count > high_count * 2

    def test_pulse_high_and_low_values(self) -> None:
        """Test pulse uses correct high and low values."""
        result = generate_pulse(n_samples=64, cycles=1.0, duty_cycle=0.5, high=0.8, low=0.2)
        for p in result:
            # Should be either high or low
            assert abs(p.v - 0.8) < 0.01 or abs(p.v - 0.2) < 0.01


class TestGeneratorEdgeCases:
    """Tests for edge cases."""

    def test_n_samples_minimum(self) -> None:
        """Test minimum n_samples=2 works."""
        result = generate_linear(n_samples=2)
        assert len(result) == 2

    def test_n_samples_1_raises_error(self) -> None:
        """Test n_samples=1 raises ValueError."""
        with pytest.raises(ValueError, match="n_samples must be >= 2"):
            generate_linear(n_samples=1)

    def test_cycles_must_be_positive(self) -> None:
        """Test cycles must be positive."""
        with pytest.raises(ValueError, match="cycles must be > 0"):
            generate_sine(n_samples=8, cycles=0.0)
        with pytest.raises(ValueError, match="cycles must be > 0"):
            generate_sine(n_samples=8, cycles=-1.0)


class TestGeneratorTimeSampling:
    """Tests for time sampling uniformity."""

    def test_all_generators_uniform_time_grid(self) -> None:
        """Test all generators use uniform time grid."""
        generators = [
            generate_linear(n_samples=4),
            generate_hold(n_samples=4, value=0.5),
            generate_sine(n_samples=4, cycles=1.0),
            generate_triangle(n_samples=4, cycles=1.0),
            generate_pulse(n_samples=4, cycles=1.0, duty_cycle=0.5),
        ]
        expected_times = [0.0, 0.25, 0.5, 0.75]

        for result in generators:
            for i, p in enumerate(result):
                assert abs(p.t - expected_times[i]) < 1e-10
