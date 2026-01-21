"""Tests for Curve Composition (Envelope/Multiply).

Tests multiply_curves and apply_envelope functions.
All 9 test cases per implementation plan Task 1.3.
"""

import time

import pytest

from blinkb0t.core.curves.composition import apply_envelope, multiply_curves
from blinkb0t.core.curves.models import CurvePoint


class TestMultiplyCurvesIdentity:
    """Tests for identity multiplication."""

    def test_multiply_by_identity_constant_one(self) -> None:
        """Test multiply by identity (a * 1.0 = a)."""
        curve_a = [
            CurvePoint(t=0.0, v=0.3),
            CurvePoint(t=0.5, v=0.7),
            CurvePoint(t=1.0, v=0.5),
        ]
        identity = [
            CurvePoint(t=0.0, v=1.0),
            CurvePoint(t=1.0, v=1.0),
        ]
        result = multiply_curves(curve_a, identity, n_samples=4)

        # Result should be approximately equal to curve_a sampled at grid
        # At t=0.0: 0.3 * 1.0 = 0.3
        # At t=0.25: interpolated ~0.5 * 1.0 = 0.5
        # At t=0.5: 0.7 * 1.0 = 0.7
        # At t=0.75: interpolated ~0.6 * 1.0 = 0.6
        assert abs(result[0].v - 0.3) < 1e-10
        assert abs(result[2].v - 0.7) < 1e-10


class TestMultiplyCurvesZero:
    """Tests for multiplication by zero."""

    def test_multiply_by_zero(self) -> None:
        """Test multiply by zero (a * 0.0 = 0)."""
        curve_a = [
            CurvePoint(t=0.0, v=0.5),
            CurvePoint(t=1.0, v=0.8),
        ]
        zero = [
            CurvePoint(t=0.0, v=0.0),
            CurvePoint(t=1.0, v=0.0),
        ]
        result = multiply_curves(curve_a, zero, n_samples=4)

        # All values should be 0
        for p in result:
            assert p.v == 0.0


class TestMultiplyCurvesRamps:
    """Tests for multiplying linear ramps."""

    def test_multiply_two_linear_ramps(self) -> None:
        """Test multiply two linear ramps."""
        ramp_a = [
            CurvePoint(t=0.0, v=0.0),
            CurvePoint(t=1.0, v=1.0),
        ]
        ramp_b = [
            CurvePoint(t=0.0, v=0.0),
            CurvePoint(t=1.0, v=1.0),
        ]
        result = multiply_curves(ramp_a, ramp_b, n_samples=4)

        # a * b where both are linear ramps = quadratic
        # At t=0.0: 0 * 0 = 0
        # At t=0.25: 0.25 * 0.25 = 0.0625
        # At t=0.5: 0.5 * 0.5 = 0.25
        # At t=0.75: 0.75 * 0.75 = 0.5625
        assert abs(result[0].v - 0.0) < 1e-10
        assert abs(result[1].v - 0.0625) < 1e-10
        assert abs(result[2].v - 0.25) < 1e-10
        assert abs(result[3].v - 0.5625) < 1e-10


class TestApplyEnvelope:
    """Tests for apply_envelope function."""

    def test_envelope_fade_in_on_constant(self) -> None:
        """Test envelope fade-in (0→1) on constant."""
        constant = [
            CurvePoint(t=0.0, v=0.8),
            CurvePoint(t=1.0, v=0.8),
        ]
        fade_in = [
            CurvePoint(t=0.0, v=0.0),
            CurvePoint(t=1.0, v=1.0),
        ]
        result = apply_envelope(constant, fade_in, n_samples=4)

        # Constant 0.8 * linear 0→1
        # At t=0: 0.8 * 0 = 0
        # At t=0.25: 0.8 * 0.25 = 0.2
        # At t=0.5: 0.8 * 0.5 = 0.4
        # At t=0.75: 0.8 * 0.75 = 0.6
        assert abs(result[0].v - 0.0) < 1e-10
        assert abs(result[1].v - 0.2) < 1e-10
        assert abs(result[2].v - 0.4) < 1e-10
        assert abs(result[3].v - 0.6) < 1e-10

    def test_envelope_fade_out_on_constant(self) -> None:
        """Test envelope fade-out (1→0) on constant."""
        constant = [
            CurvePoint(t=0.0, v=0.8),
            CurvePoint(t=1.0, v=0.8),
        ]
        fade_out = [
            CurvePoint(t=0.0, v=1.0),
            CurvePoint(t=1.0, v=0.0),
        ]
        result = apply_envelope(constant, fade_out, n_samples=4)

        # Constant 0.8 * linear 1→0
        # At t=0: 0.8 * 1.0 = 0.8
        # At t=0.25: 0.8 * 0.75 = 0.6
        # At t=0.5: 0.8 * 0.5 = 0.4
        # At t=0.75: 0.8 * 0.25 = 0.2
        assert abs(result[0].v - 0.8) < 1e-10
        assert abs(result[1].v - 0.6) < 1e-10
        assert abs(result[2].v - 0.4) < 1e-10
        assert abs(result[3].v - 0.2) < 1e-10


class TestMultiplyCurvesMismatchedSamples:
    """Tests for mismatched sample counts."""

    def test_mismatched_sample_counts_resamples(self) -> None:
        """Test mismatched sample counts (resamples to max)."""
        short_curve = [
            CurvePoint(t=0.0, v=0.5),
            CurvePoint(t=1.0, v=0.5),
        ]
        long_curve = [
            CurvePoint(t=0.0, v=1.0),
            CurvePoint(t=0.25, v=0.8),
            CurvePoint(t=0.5, v=0.6),
            CurvePoint(t=0.75, v=0.4),
            CurvePoint(t=1.0, v=0.2),
        ]
        # n_samples not specified, should use max(2, 5) = 5
        result = multiply_curves(short_curve, long_curve)

        # Should have 5 samples
        assert len(result) == 5


class TestMultiplyCurvesNSamplesOverride:
    """Tests for n_samples override."""

    def test_n_samples_override(self) -> None:
        """Test n_samples override."""
        curve_a = [
            CurvePoint(t=0.0, v=0.5),
            CurvePoint(t=1.0, v=0.5),
        ]
        curve_b = [
            CurvePoint(t=0.0, v=1.0),
            CurvePoint(t=1.0, v=1.0),
        ]
        result = multiply_curves(curve_a, curve_b, n_samples=8)

        # Should have exactly 8 samples
        assert len(result) == 8
        # All values should be 0.5 * 1.0 = 0.5
        for p in result:
            assert abs(p.v - 0.5) < 1e-10


class TestResultBounds:
    """Tests for result bounds."""

    def test_result_bounds_0_to_1(self) -> None:
        """Test result bounds [0, 1]."""
        curve_a = [
            CurvePoint(t=0.0, v=0.9),
            CurvePoint(t=1.0, v=1.0),
        ]
        curve_b = [
            CurvePoint(t=0.0, v=0.8),
            CurvePoint(t=1.0, v=0.9),
        ]
        result = multiply_curves(curve_a, curve_b, n_samples=10)

        # All results should be in [0, 1]
        for p in result:
            assert 0.0 <= p.v <= 1.0


class TestMultiplyCurvesEdgeCases:
    """Tests for edge cases."""

    def test_empty_curve_a_raises_error(self) -> None:
        """Test empty curve a raises ValueError."""
        curve_b = [CurvePoint(t=0.0, v=0.5), CurvePoint(t=1.0, v=0.5)]
        with pytest.raises(ValueError, match="Both curves must be non-empty"):
            multiply_curves([], curve_b)

    def test_empty_curve_b_raises_error(self) -> None:
        """Test empty curve b raises ValueError."""
        curve_a = [CurvePoint(t=0.0, v=0.5), CurvePoint(t=1.0, v=0.5)]
        with pytest.raises(ValueError, match="Both curves must be non-empty"):
            multiply_curves(curve_a, [])


class TestMultiplyCurvesPerformance:
    """Performance benchmarks."""

    def test_64_sample_multiply_under_1ms(self) -> None:
        """Benchmark: 64-sample multiply < 1ms."""
        curve_a = [CurvePoint(t=i / 63, v=(i / 63) ** 2) for i in range(64)]
        curve_b = [CurvePoint(t=i / 63, v=1.0 - i / 63) for i in range(64)]

        start = time.perf_counter()
        for _ in range(100):
            multiply_curves(curve_a, curve_b, n_samples=64)
        elapsed_ms = (time.perf_counter() - start) * 1000 / 100

        assert elapsed_ms < 1.0, f"64-sample multiply took {elapsed_ms:.3f}ms (should be < 1ms)"
