"""Tests for basic curve generators."""

from __future__ import annotations

import pytest

from twinklr.core.curves.functions.basic import (
    generate_cosine,
    generate_hold,
    generate_linear,
    generate_pulse,
    generate_s_curve,
    generate_sine,
    generate_smooth_step,
    generate_smoother_step,
    generate_triangle,
)


class TestGenerateLinear:
    """Tests for generate_linear function."""

    def test_n_samples_less_than_two_raises(self) -> None:
        """n_samples < 2 raises ValueError."""
        with pytest.raises(ValueError, match="n_samples must be >= 2"):
            generate_linear(1)


class TestGenerateHold:
    """Tests for generate_hold function."""

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

    def test_n_samples_less_than_two_raises(self) -> None:
        """n_samples < 2 raises ValueError."""
        with pytest.raises(ValueError, match="n_samples must be >= 2"):
            generate_triangle(1)


class TestGeneratePulse:
    """Tests for generate_pulse function."""

    def test_n_samples_less_than_two_raises(self) -> None:
        """n_samples < 2 raises ValueError."""
        with pytest.raises(ValueError, match="n_samples must be >= 2"):
            generate_pulse(1)


class TestGenerateCosine:
    """Tests for generate_cosine function."""

    def test_n_samples_less_than_two_raises(self) -> None:
        """n_samples < 2 raises ValueError."""
        with pytest.raises(ValueError, match="n_samples must be >= 2"):
            generate_cosine(1)


class TestGenerateSquare:
    """Tests for generate_square function."""

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

    def test_n_samples_less_than_two_raises(self) -> None:
        """n_samples < 2 raises ValueError."""
        with pytest.raises(ValueError, match="n_samples must be >= 2"):
            generate_smooth_step(1)


class TestGenerateSmootherStep:
    """Tests for generate_smoother_step function."""

    def test_n_samples_less_than_two_raises(self) -> None:
        """n_samples < 2 raises ValueError."""
        with pytest.raises(ValueError, match="n_samples must be >= 2"):
            generate_smoother_step(1)
