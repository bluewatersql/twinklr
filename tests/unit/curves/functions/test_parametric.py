"""Tests for parametric curve generators."""

from __future__ import annotations

import math

import pytest

from twinklr.core.curves.functions.parametric import generate_bezier, generate_lissajous


class TestGenerateBezier:
    """Tests for generate_bezier function."""

    def test_n_less_than_two_raises(self) -> None:
        """n < 2 raises ValueError."""
        with pytest.raises(ValueError, match="n_samples must be >= 2"):
            generate_bezier(1)

    def test_b_zero_raises(self) -> None:
        """b <= 0 raises ValueError."""
        with pytest.raises(ValueError, match="b must be > 0"):
            generate_lissajous(10, b=0)

    def test_b_negative_raises(self) -> None:
        """Negative b raises ValueError."""
        with pytest.raises(ValueError, match="b must be > 0"):
            generate_lissajous(10, b=-1)

    def test_different_delta_produce_different_curves(self) -> None:
        """Different delta values produce different curves."""
        result_delta_pi2 = generate_lissajous(20, delta=math.pi / 2)
        result_delta_pi = generate_lissajous(20, delta=math.pi)
        # At least some values should differ
        differences = [
            abs(a.v - b.v) for a, b in zip(result_delta_pi2, result_delta_pi, strict=True)
        ]
        assert any(d > 0.01 for d in differences)
