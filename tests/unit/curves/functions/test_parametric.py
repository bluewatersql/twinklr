"""Tests for parametric curve generators."""

from __future__ import annotations

import math

import pytest

from blinkb0t.core.curves.functions.parametric import generate_bezier, generate_lissajous


class TestGenerateBezier:
    """Tests for generate_bezier function."""

    def test_returns_correct_count(self) -> None:
        """Returns requested number of samples."""
        result = generate_bezier(10)
        assert len(result) == 10

    def test_values_in_valid_range(self) -> None:
        """All values are in [0, 1]."""
        result = generate_bezier(50)
        for p in result:
            assert 0.0 <= p.v <= 1.0

    def test_times_in_valid_range(self) -> None:
        """All times are in [0, 1)."""
        result = generate_bezier(10)
        for p in result:
            assert 0.0 <= p.t < 1.0

    def test_starts_at_zero(self) -> None:
        """Curve starts at t=0."""
        result = generate_bezier(10)
        assert result[0].t == pytest.approx(0.0)

    def test_n_less_than_two_raises(self) -> None:
        """n < 2 raises ValueError."""
        with pytest.raises(ValueError, match="n_samples must be >= 2"):
            generate_bezier(1)

    def test_custom_p1(self) -> None:
        """Custom p1 parameter works."""
        result = generate_bezier(20, p1=0.3)
        assert len(result) == 20

    def test_custom_p2(self) -> None:
        """Custom p2 parameter works."""
        result = generate_bezier(20, p2=0.7)
        assert len(result) == 20

    def test_p1_clamped_high(self) -> None:
        """p1 > 1.0 is clamped to 1.0."""
        result = generate_bezier(10, p1=2.0)
        assert len(result) == 10
        # Values should still be valid
        for p in result:
            assert 0.0 <= p.v <= 1.0

    def test_p1_clamped_low(self) -> None:
        """p1 < 0.0 is clamped to 0.0."""
        result = generate_bezier(10, p1=-0.5)
        assert len(result) == 10
        for p in result:
            assert 0.0 <= p.v <= 1.0

    def test_p2_clamped_high(self) -> None:
        """p2 > 1.0 is clamped to 1.0."""
        result = generate_bezier(10, p2=2.0)
        assert len(result) == 10
        for p in result:
            assert 0.0 <= p.v <= 1.0

    def test_p2_clamped_low(self) -> None:
        """p2 < 0.0 is clamped to 0.0."""
        result = generate_bezier(10, p2=-0.5)
        assert len(result) == 10
        for p in result:
            assert 0.0 <= p.v <= 1.0

    def test_different_p1_p2_produce_different_curves(self) -> None:
        """Different control points produce different curves."""
        result_default = generate_bezier(20, p1=0.1, p2=0.9)
        result_custom = generate_bezier(20, p1=0.5, p2=0.5)
        # At least some values should differ
        differences = [abs(a.v - b.v) for a, b in zip(result_default, result_custom, strict=True)]
        assert any(d > 0.01 for d in differences)


class TestGenerateLissajous:
    """Tests for generate_lissajous function."""

    def test_returns_correct_count(self) -> None:
        """Returns requested number of samples."""
        result = generate_lissajous(10)
        assert len(result) == 10

    def test_values_in_valid_range(self) -> None:
        """All values are in [0, 1]."""
        result = generate_lissajous(50)
        for p in result:
            assert 0.0 <= p.v <= 1.0

    def test_times_in_valid_range(self) -> None:
        """All times are in [0, 1)."""
        result = generate_lissajous(10)
        for p in result:
            assert 0.0 <= p.t < 1.0

    def test_n_less_than_two_raises(self) -> None:
        """n < 2 raises ValueError."""
        with pytest.raises(ValueError, match="n_samples must be >= 2"):
            generate_lissajous(1)

    def test_b_zero_raises(self) -> None:
        """b <= 0 raises ValueError."""
        with pytest.raises(ValueError, match="b must be > 0"):
            generate_lissajous(10, b=0)

    def test_b_negative_raises(self) -> None:
        """Negative b raises ValueError."""
        with pytest.raises(ValueError, match="b must be > 0"):
            generate_lissajous(10, b=-1)

    def test_custom_b(self) -> None:
        """Custom b parameter works."""
        result = generate_lissajous(20, b=3)
        assert len(result) == 20

    def test_custom_delta(self) -> None:
        """Custom delta parameter works."""
        result = generate_lissajous(20, delta=math.pi / 4)
        assert len(result) == 20

    def test_different_b_produce_different_curves(self) -> None:
        """Different b values produce different curves."""
        result_b2 = generate_lissajous(20, b=2)
        result_b3 = generate_lissajous(20, b=3)
        # At least some values should differ
        differences = [abs(a.v - b.v) for a, b in zip(result_b2, result_b3, strict=True)]
        assert any(d > 0.01 for d in differences)

    def test_different_delta_produce_different_curves(self) -> None:
        """Different delta values produce different curves."""
        result_delta_pi2 = generate_lissajous(20, delta=math.pi / 2)
        result_delta_pi = generate_lissajous(20, delta=math.pi)
        # At least some values should differ
        differences = [
            abs(a.v - b.v) for a, b in zip(result_delta_pi2, result_delta_pi, strict=True)
        ]
        assert any(d > 0.01 for d in differences)
