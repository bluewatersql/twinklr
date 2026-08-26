"""Tests for parametric curve generators."""

from __future__ import annotations

import math

import pytest

from twinklr.core.curves.functions.parametric import (
    _evaluate_bezier_ordinate,
    generate_bezier,
    generate_lissajous,
)


class TestGenerateBezier:
    """Tests for generate_bezier function."""

    def test_n_less_than_two_raises(self) -> None:
        """n < 2 raises ValueError."""
        with pytest.raises(ValueError, match="n_samples must be >= 2"):
            generate_bezier(1)

    def test_preserves_sample_shape_order_and_known_cubic_values(self) -> None:
        """The in-repo evaluator preserves the historical bezier package seam."""
        points = generate_bezier(4, p1=0.1, p2=0.9)

        assert [(point.t, point.v) for point in points] == [
            (0.0, 0.0),
            (0.25, 0.184375),
            (0.5, 0.5),
            (0.75, 0.815625),
        ]
        assert all(type(point.t) is float and type(point.v) is float for point in points)

    def test_clamps_control_ordinates_before_evaluation(self) -> None:
        points = generate_bezier(4, p1=-10.0, p2=10.0)

        assert [point.v for point in points] == [0.0, 0.15625, 0.5, 0.84375]


class TestBezierOrdinateEvaluator:
    """Reference properties for the dependency-free de Casteljau evaluator."""

    @pytest.mark.parametrize(
        ("control_points", "t", "expected"),
        [
            ((0.0, 1.0), 0.25, 0.25),
            ((0.0, 0.0, 1.0), 0.5, 0.25),
            ((0.0, 0.0, 1.0, 1.0), 0.25, 0.15625),
        ],
    )
    def test_matches_known_linear_quadratic_and_cubic_references(
        self,
        control_points: tuple[float, ...],
        t: float,
        expected: float,
    ) -> None:
        assert _evaluate_bezier_ordinate(control_points, t) == expected

    def test_endpoints_are_exact(self) -> None:
        control_points = (0.125, 0.2, 0.8, 0.875)

        assert _evaluate_bezier_ordinate(control_points, 0.0) == 0.125
        assert _evaluate_bezier_ordinate(control_points, 1.0) == 0.875

    @pytest.mark.parametrize(
        ("control_points", "t"), [((), 0.5), ((0.0, 1.0), -0.1), ((0.0, 1.0), 1.1)]
    )
    def test_rejects_invalid_input(self, control_points: tuple[float, ...], t: float) -> None:
        with pytest.raises(ValueError):
            _evaluate_bezier_ordinate(control_points, t)

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
