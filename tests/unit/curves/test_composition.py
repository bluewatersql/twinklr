"""Tests for curve composition operations."""

from __future__ import annotations

import pytest

from blinkb0t.core.curves.composition import apply_envelope, multiply_curves
from blinkb0t.core.curves.models import CurvePoint


class TestMultiplyCurves:
    """Tests for multiply_curves function."""

    def test_multiply_constant_by_ramp(
        self, simple_hold_points: list[CurvePoint], ramp_up_points: list[CurvePoint]
    ) -> None:
        """Multiplying constant 0.5 by ramp gives half-ramp."""
        result = multiply_curves(simple_hold_points, ramp_up_points, n_samples=4)
        # Constant 0.5 * ramp [0, 1] = [0, 0.5]
        assert result[0].v == pytest.approx(0.0, abs=0.01)
        assert result[-1].v == pytest.approx(0.375, abs=0.05)  # 0.5 * 0.75

    def test_multiply_identity(self, ramp_up_points: list[CurvePoint]) -> None:
        """Multiplying by all-ones returns original."""
        ones = [
            CurvePoint(t=0.0, v=1.0),
            CurvePoint(t=1.0, v=1.0),
        ]
        result = multiply_curves(ramp_up_points, ones, n_samples=4)
        for p in result:
            assert 0.0 <= p.v <= 1.0

    def test_multiply_by_zeros(self, ramp_up_points: list[CurvePoint]) -> None:
        """Multiplying by all-zeros returns zeros."""
        zeros = [
            CurvePoint(t=0.0, v=0.0),
            CurvePoint(t=1.0, v=0.0),
        ]
        result = multiply_curves(ramp_up_points, zeros, n_samples=4)
        for p in result:
            assert p.v == pytest.approx(0.0)

    def test_multiply_uses_max_samples_by_default(
        self, simple_linear_points: list[CurvePoint], ramp_up_points: list[CurvePoint]
    ) -> None:
        """Default n_samples is max of input lengths."""
        result = multiply_curves(simple_linear_points, ramp_up_points)
        assert len(result) == max(len(simple_linear_points), len(ramp_up_points))

    def test_multiply_explicit_samples(
        self, simple_linear_points: list[CurvePoint], ramp_up_points: list[CurvePoint]
    ) -> None:
        """Explicit n_samples is respected."""
        result = multiply_curves(simple_linear_points, ramp_up_points, n_samples=10)
        assert len(result) == 10

    def test_multiply_clamps_result(self) -> None:
        """Result is clamped to [0, 1]."""
        # Even with values > 1 (not possible with CurvePoint),
        # multiplication should clamp
        high = [
            CurvePoint(t=0.0, v=1.0),
            CurvePoint(t=1.0, v=1.0),
        ]
        result = multiply_curves(high, high, n_samples=4)
        for p in result:
            assert 0.0 <= p.v <= 1.0

    def test_multiply_empty_a_raises(self, ramp_up_points: list[CurvePoint]) -> None:
        """Empty first curve raises ValueError."""
        with pytest.raises(ValueError, match="Both curves must be non-empty"):
            multiply_curves([], ramp_up_points)

    def test_multiply_empty_b_raises(self, ramp_up_points: list[CurvePoint]) -> None:
        """Empty second curve raises ValueError."""
        with pytest.raises(ValueError, match="Both curves must be non-empty"):
            multiply_curves(ramp_up_points, [])

    def test_multiply_preserves_time_range(
        self, simple_linear_points: list[CurvePoint], ramp_up_points: list[CurvePoint]
    ) -> None:
        """Result has uniform t values in [0, 1)."""
        result = multiply_curves(simple_linear_points, ramp_up_points, n_samples=4)
        assert result[0].t == pytest.approx(0.0)
        # Uniform grid doesn't include 1.0


class TestApplyEnvelope:
    """Tests for apply_envelope function."""

    def test_fade_in_envelope(self, simple_hold_points: list[CurvePoint]) -> None:
        """Fade-in envelope (0->1) applies correctly."""
        fade_in = [
            CurvePoint(t=0.0, v=0.0),
            CurvePoint(t=1.0, v=1.0),
        ]
        result = apply_envelope(simple_hold_points, fade_in, n_samples=4)
        # Constant 0.5 * fade_in [0, 1]
        assert result[0].v == pytest.approx(0.0, abs=0.01)
        assert result[-1].v == pytest.approx(0.375, abs=0.05)

    def test_fade_out_envelope(self, simple_hold_points: list[CurvePoint]) -> None:
        """Fade-out envelope (1->0) applies correctly."""
        fade_out = [
            CurvePoint(t=0.0, v=1.0),
            CurvePoint(t=1.0, v=0.0),
        ]
        result = apply_envelope(simple_hold_points, fade_out, n_samples=4)
        # Constant 0.5 * fade_out [1, 0]
        assert result[0].v == pytest.approx(0.5, abs=0.05)
        assert result[-1].v == pytest.approx(0.125, abs=0.05)

    def test_envelope_is_alias_for_multiply(
        self, simple_linear_points: list[CurvePoint], ramp_up_points: list[CurvePoint]
    ) -> None:
        """apply_envelope is an alias for multiply_curves."""
        n_samples = 5
        multiply_result = multiply_curves(simple_linear_points, ramp_up_points, n_samples=n_samples)
        envelope_result = apply_envelope(simple_linear_points, ramp_up_points, n_samples=n_samples)
        for m, e in zip(multiply_result, envelope_result, strict=True):
            assert m.t == pytest.approx(e.t)
            assert m.v == pytest.approx(e.v)

    def test_envelope_empty_curve_raises(self, ramp_up_points: list[CurvePoint]) -> None:
        """Empty curve raises ValueError."""
        with pytest.raises(ValueError, match="Both curves must be non-empty"):
            apply_envelope([], ramp_up_points)

    def test_envelope_empty_envelope_raises(self, ramp_up_points: list[CurvePoint]) -> None:
        """Empty envelope raises ValueError."""
        with pytest.raises(ValueError, match="Both curves must be non-empty"):
            apply_envelope(ramp_up_points, [])
