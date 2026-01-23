"""Tests for basic curve generators."""

from __future__ import annotations

import math

import pytest

from blinkb0t.core.curves.functions.basic import (
    generate_cosine,
    generate_hold,
    generate_linear,
    generate_pulse,
    generate_s_curve,
    generate_sine,
    generate_smooth_step,
    generate_smoother_step,
    generate_square,
    generate_triangle,
)


class TestGenerateLinear:
    """Tests for generate_linear function."""

    def test_returns_correct_count(self) -> None:
        """Returns requested number of points."""
        result = generate_linear(10)
        assert len(result) == 10

    def test_ascending_starts_at_zero(self) -> None:
        """Ascending ramp starts near zero."""
        result = generate_linear(4)
        assert result[0].v == pytest.approx(0.0)

    def test_ascending_ends_at_one(self) -> None:
        """Ascending ramp ends at one."""
        result = generate_linear(4)
        assert result[-1].v == pytest.approx(1.0)

    def test_descending_ramp(self) -> None:
        """Descending ramp goes from 1 to 0."""
        result = generate_linear(4, ascending=False)
        assert result[0].v == pytest.approx(1.0)
        assert result[-1].v == pytest.approx(0.0)

    def test_values_in_valid_range(self) -> None:
        """All values are in [0, 1]."""
        result = generate_linear(10)
        for p in result:
            assert 0.0 <= p.v <= 1.0

    def test_n_samples_less_than_two_raises(self) -> None:
        """n_samples < 2 raises ValueError."""
        with pytest.raises(ValueError, match="n_samples must be >= 2"):
            generate_linear(1)


class TestGenerateHold:
    """Tests for generate_hold function."""

    def test_returns_correct_count(self) -> None:
        """Returns requested number of points."""
        result = generate_hold(10)
        assert len(result) == 10

    def test_default_value_is_one(self) -> None:
        """Default value is 1.0."""
        result = generate_hold(4)
        for p in result:
            assert p.v == pytest.approx(1.0)

    def test_custom_value(self) -> None:
        """Custom value is used."""
        result = generate_hold(4, value=0.5)
        for p in result:
            assert p.v == pytest.approx(0.5)

    def test_value_clamped_to_range(self) -> None:
        """Value is clamped to [0, 1]."""
        result = generate_hold(4, value=1.5)
        for p in result:
            assert p.v == pytest.approx(1.0)

        result_low = generate_hold(4, value=-0.5)
        for p in result_low:
            assert p.v == pytest.approx(0.0)

    def test_n_samples_less_than_two_raises(self) -> None:
        """n_samples < 2 raises ValueError."""
        with pytest.raises(ValueError, match="n_samples must be >= 2"):
            generate_hold(1)


class TestGenerateSine:
    """Tests for generate_sine function."""

    def test_returns_correct_count(self) -> None:
        """Returns requested number of points."""
        result = generate_sine(16)
        assert len(result) == 16

    def test_starts_at_midpoint(self) -> None:
        """Sine starts at 0.5 (midpoint)."""
        result = generate_sine(16)
        assert result[0].v == pytest.approx(0.5)

    def test_values_in_valid_range(self) -> None:
        """All values are in [0, 1]."""
        result = generate_sine(16)
        for p in result:
            assert 0.0 <= p.v <= 1.0

    def test_has_peak_and_trough(self) -> None:
        """Sine has values near 1 and 0."""
        result = generate_sine(64)
        values = [p.v for p in result]
        assert max(values) > 0.95
        assert min(values) < 0.05

    def test_multiple_cycles(self) -> None:
        """Multiple cycles creates more peaks."""
        result = generate_sine(64, cycles=2.0)
        values = [p.v for p in result]
        # With 2 cycles, we should have more variation
        peak_count = sum(
            1
            for i in range(1, len(values) - 1)
            if values[i] > values[i - 1] and values[i] > values[i + 1]
        )
        assert peak_count >= 2

    def test_phase_offset(self) -> None:
        """Phase offset shifts starting point."""
        result = generate_sine(16, phase=math.pi / 2)  # Start at peak
        assert result[0].v == pytest.approx(1.0)

    def test_n_samples_less_than_two_raises(self) -> None:
        """n_samples < 2 raises ValueError."""
        with pytest.raises(ValueError, match="n_samples must be >= 2"):
            generate_sine(1)

    def test_cycles_zero_or_negative_raises(self) -> None:
        """cycles <= 0 raises ValueError."""
        with pytest.raises(ValueError, match="cycles must be > 0"):
            generate_sine(10, cycles=0)


class TestGenerateTriangle:
    """Tests for generate_triangle function."""

    def test_returns_correct_count(self) -> None:
        """Returns requested number of points."""
        result = generate_triangle(16)
        assert len(result) == 16

    def test_starts_at_zero(self) -> None:
        """Triangle starts at 0."""
        result = generate_triangle(16)
        assert result[0].v == pytest.approx(0.0)

    def test_peaks_at_middle(self) -> None:
        """Triangle peaks at middle of cycle."""
        result = generate_triangle(64)
        values = [p.v for p in result]
        max_idx = values.index(max(values))
        # Peak should be near middle
        assert 0.4 < result[max_idx].t < 0.6

    def test_values_in_valid_range(self) -> None:
        """All values are in [0, 1]."""
        result = generate_triangle(16)
        for p in result:
            assert 0.0 <= p.v <= 1.0

    def test_n_samples_less_than_two_raises(self) -> None:
        """n_samples < 2 raises ValueError."""
        with pytest.raises(ValueError, match="n_samples must be >= 2"):
            generate_triangle(1)


class TestGeneratePulse:
    """Tests for generate_pulse function."""

    def test_returns_correct_count(self) -> None:
        """Returns requested number of points."""
        result = generate_pulse(16)
        assert len(result) == 16

    def test_default_duty_cycle(self) -> None:
        """Default duty cycle is 50%."""
        result = generate_pulse(100)
        high_count = sum(1 for p in result if p.v > 0.5)
        assert 45 <= high_count <= 55  # Approximately 50%

    def test_custom_duty_cycle(self) -> None:
        """Custom duty cycle works."""
        result = generate_pulse(100, duty_cycle=0.25)
        high_count = sum(1 for p in result if p.v > 0.5)
        assert 20 <= high_count <= 30  # Approximately 25%

    def test_custom_high_low_values(self) -> None:
        """Custom high and low values work."""
        result = generate_pulse(10, high=0.8, low=0.2)
        for p in result:
            assert p.v == pytest.approx(0.8) or p.v == pytest.approx(0.2)

    def test_values_in_valid_range(self) -> None:
        """All values are in [0, 1]."""
        result = generate_pulse(16)
        for p in result:
            assert 0.0 <= p.v <= 1.0

    def test_n_samples_less_than_two_raises(self) -> None:
        """n_samples < 2 raises ValueError."""
        with pytest.raises(ValueError, match="n_samples must be >= 2"):
            generate_pulse(1)


class TestGenerateCosine:
    """Tests for generate_cosine function."""

    def test_returns_correct_count(self) -> None:
        """Returns requested number of points."""
        result = generate_cosine(16)
        assert len(result) == 16

    def test_starts_at_peak(self) -> None:
        """Cosine starts at 1.0 (peak)."""
        result = generate_cosine(16)
        assert result[0].v == pytest.approx(1.0)

    def test_values_in_valid_range(self) -> None:
        """All values are in [0, 1]."""
        result = generate_cosine(16)
        for p in result:
            assert 0.0 <= p.v <= 1.0

    def test_n_samples_less_than_two_raises(self) -> None:
        """n_samples < 2 raises ValueError."""
        with pytest.raises(ValueError, match="n_samples must be >= 2"):
            generate_cosine(1)


class TestGenerateSquare:
    """Tests for generate_square function."""

    def test_returns_correct_count(self) -> None:
        """Returns requested number of points."""
        result = generate_square(16)
        assert len(result) == 16

    def test_binary_values(self) -> None:
        """Square wave has only high and low values."""
        result = generate_square(100)
        for p in result:
            assert p.v == pytest.approx(0.0) or p.v == pytest.approx(1.0)


class TestGenerateSCurve:
    """Tests for generate_s_curve function."""

    def test_returns_correct_count(self) -> None:
        """Returns requested number of points."""
        result = generate_s_curve(16)
        assert len(result) == 16

    def test_starts_near_zero(self) -> None:
        """S-curve starts near 0."""
        result = generate_s_curve(16)
        assert result[0].v < 0.1

    def test_ends_near_one(self) -> None:
        """S-curve ends near 1."""
        result = generate_s_curve(16)
        assert result[-1].v > 0.9

    def test_midpoint_at_half(self) -> None:
        """S-curve passes through 0.5 at midpoint."""
        result = generate_s_curve(64)
        # Find point closest to t=0.5
        mid_point = min(result, key=lambda p: abs(p.t - 0.5))
        assert mid_point.v == pytest.approx(0.5, abs=0.1)

    def test_steepness_affects_transition(self) -> None:
        """Higher steepness creates sharper transition."""
        result_low = generate_s_curve(64, steepness=6.0)
        result_high = generate_s_curve(64, steepness=24.0)
        # High steepness should be closer to 0/1 at edges
        assert result_high[0].v < result_low[0].v
        assert result_high[-1].v > result_low[-1].v

    def test_n_samples_less_than_two_raises(self) -> None:
        """n_samples < 2 raises ValueError."""
        with pytest.raises(ValueError, match="n_samples must be >= 2"):
            generate_s_curve(1)

    def test_steepness_zero_or_negative_raises(self) -> None:
        """steepness <= 0 raises ValueError."""
        with pytest.raises(ValueError, match="steepness must be > 0"):
            generate_s_curve(10, steepness=0)


class TestGenerateSmoothStep:
    """Tests for generate_smooth_step function."""

    def test_returns_correct_count(self) -> None:
        """Returns requested number of points."""
        result = generate_smooth_step(16)
        assert len(result) == 16

    def test_starts_at_zero(self) -> None:
        """Smooth step starts at 0."""
        result = generate_smooth_step(16)
        assert result[0].v == pytest.approx(0.0)

    def test_ends_near_one(self) -> None:
        """Smooth step ends near 1."""
        result = generate_smooth_step(16)
        assert result[-1].v == pytest.approx(0.896, abs=0.1)

    def test_values_in_valid_range(self) -> None:
        """All values are in [0, 1]."""
        result = generate_smooth_step(16)
        for p in result:
            assert 0.0 <= p.v <= 1.0

    def test_n_samples_less_than_two_raises(self) -> None:
        """n_samples < 2 raises ValueError."""
        with pytest.raises(ValueError, match="n_samples must be >= 2"):
            generate_smooth_step(1)


class TestGenerateSmootherStep:
    """Tests for generate_smoother_step function."""

    def test_returns_correct_count(self) -> None:
        """Returns requested number of points."""
        result = generate_smoother_step(16)
        assert len(result) == 16

    def test_starts_at_zero(self) -> None:
        """Smoother step starts at 0."""
        result = generate_smoother_step(16)
        assert result[0].v == pytest.approx(0.0)

    def test_values_in_valid_range(self) -> None:
        """All values are in [0, 1]."""
        result = generate_smoother_step(16)
        for p in result:
            assert 0.0 <= p.v <= 1.0

    def test_n_samples_less_than_two_raises(self) -> None:
        """n_samples < 2 raises ValueError."""
        with pytest.raises(ValueError, match="n_samples must be >= 2"):
            generate_smoother_step(1)
