"""Tests for Phase Shift Implementation.

Tests apply_phase_shift_samples function.
All 10 test cases per implementation plan Task 1.2.
"""

import math
import time

import pytest

from blinkb0t.core.curves.models import CurvePoint
from blinkb0t.core.curves.phase import apply_phase_shift_samples


class TestPhaseShiftZeroOffset:
    """Tests for zero offset (identity operation)."""

    def test_zero_offset_preserves_curve(self) -> None:
        """Test zero offset returns equivalent curve."""
        points = [
            CurvePoint(t=0.0, v=0.0),
            CurvePoint(t=0.5, v=0.5),
            CurvePoint(t=1.0, v=1.0),
        ]
        result = apply_phase_shift_samples(points, offset_norm=0.0, n_samples=4)

        # Result should be sampled at t=0.0, 0.25, 0.5, 0.75
        assert len(result) == 4
        assert result[0].t == 0.0
        assert result[0].v == 0.0  # Linear interpolation at t=0
        assert result[1].t == 0.25
        assert abs(result[1].v - 0.25) < 1e-10
        assert result[2].t == 0.5
        assert abs(result[2].v - 0.5) < 1e-10


class TestPhaseShiftLinearRamp:
    """Tests for phase shift on linear ramp."""

    def test_offset_quarter_on_linear_ramp(self) -> None:
        """Test offset=0.25 on linear 0→1 ramp."""
        # Linear ramp: v = t
        points = [
            CurvePoint(t=0.0, v=0.0),
            CurvePoint(t=1.0, v=1.0),
        ]
        result = apply_phase_shift_samples(points, offset_norm=0.25, n_samples=4, wrap=True)

        # At t=0, we sample from original t=0.25 → v=0.25
        # At t=0.25, we sample from original t=0.5 → v=0.5
        # At t=0.5, we sample from original t=0.75 → v=0.75
        # At t=0.75, we sample from original t=0.0 (wrapped) → v=0.0
        assert len(result) == 4
        assert abs(result[0].v - 0.25) < 1e-10
        assert abs(result[1].v - 0.5) < 1e-10
        assert abs(result[2].v - 0.75) < 1e-10
        assert abs(result[3].v - 0.0) < 1e-10  # Wrapped

    def test_offset_half_cycle(self) -> None:
        """Test offset=0.5 (half cycle)."""
        points = [
            CurvePoint(t=0.0, v=0.0),
            CurvePoint(t=1.0, v=1.0),
        ]
        result = apply_phase_shift_samples(points, offset_norm=0.5, n_samples=4, wrap=True)

        # At t=0, sample from t=0.5 → v=0.5
        # At t=0.25, sample from t=0.75 → v=0.75
        # At t=0.5, sample from t=0.0 (wrapped) → v=0.0
        # At t=0.75, sample from t=0.25 (wrapped) → v=0.25
        assert abs(result[0].v - 0.5) < 1e-10
        assert abs(result[1].v - 0.75) < 1e-10
        assert abs(result[2].v - 0.0) < 1e-10
        assert abs(result[3].v - 0.25) < 1e-10


class TestPhaseShiftWrap:
    """Tests for wrap behavior."""

    def test_offset_greater_than_1_wraps(self) -> None:
        """Test offset > 1.0 wraps correctly."""
        points = [
            CurvePoint(t=0.0, v=0.0),
            CurvePoint(t=1.0, v=1.0),
        ]
        # offset=1.25 should be equivalent to offset=0.25
        result = apply_phase_shift_samples(points, offset_norm=1.25, n_samples=4, wrap=True)

        assert abs(result[0].v - 0.25) < 1e-10
        assert abs(result[1].v - 0.5) < 1e-10

    def test_negative_offset_wraps(self) -> None:
        """Test negative offset wraps correctly."""
        points = [
            CurvePoint(t=0.0, v=0.0),
            CurvePoint(t=1.0, v=1.0),
        ]
        # offset=-0.25 should wrap: at t=0, sample from t=-0.25 → t=0.75
        result = apply_phase_shift_samples(points, offset_norm=-0.25, n_samples=4, wrap=True)

        # At t=0, sample from t=-0.25 % 1.0 = 0.75 → v=0.75
        assert abs(result[0].v - 0.75) < 1e-10


class TestPhaseShiftNoWrap:
    """Tests for wrap=False (clamp mode)."""

    def test_wrap_false_clamps_at_boundaries(self) -> None:
        """Test wrap=False clamps at boundaries."""
        points = [
            CurvePoint(t=0.0, v=0.0),
            CurvePoint(t=1.0, v=1.0),
        ]
        result = apply_phase_shift_samples(points, offset_norm=0.5, n_samples=4, wrap=False)

        # At t=0, sample from min(1.0, max(0.0, 0.5)) = 0.5 → v=0.5
        # At t=0.25, sample from min(1.0, max(0.0, 0.75)) = 0.75 → v=0.75
        # At t=0.5, sample from min(1.0, max(0.0, 1.0)) = 1.0 → v=1.0
        # At t=0.75, sample from min(1.0, max(0.0, 1.25)) = 1.0 → v=1.0 (clamped)
        assert abs(result[0].v - 0.5) < 1e-10
        assert abs(result[1].v - 0.75) < 1e-10
        assert abs(result[2].v - 1.0) < 1e-10
        assert abs(result[3].v - 1.0) < 1e-10  # Clamped to end


class TestPhaseShiftIntegerSample:
    """Tests for exact integer sample offsets."""

    def test_exact_integer_sample_offset(self) -> None:
        """Test exact integer sample offset (n=4, offset=0.25 → 1 sample shift)."""
        # Create a curve with distinct values at each sample point
        points = [
            CurvePoint(t=0.0, v=0.1),
            CurvePoint(t=0.25, v=0.2),
            CurvePoint(t=0.5, v=0.3),
            CurvePoint(t=0.75, v=0.4),
        ]
        result = apply_phase_shift_samples(points, offset_norm=0.25, n_samples=4, wrap=True)

        # Values should shift by one position with wrap
        # Original: [0.1, 0.2, 0.3, 0.4] at [0, 0.25, 0.5, 0.75]
        # After shift: at t=0, sample t=0.25 → v=0.2
        # at t=0.25, sample t=0.5 → v=0.3
        # at t=0.5, sample t=0.75 → v=0.4
        # at t=0.75, sample t=0.0 → v=0.1
        assert abs(result[0].v - 0.2) < 1e-10
        assert abs(result[1].v - 0.3) < 1e-10
        assert abs(result[2].v - 0.4) < 1e-10
        assert abs(result[3].v - 0.1) < 1e-10


class TestPhaseShiftSineWave:
    """Tests for phase shift on sine wave."""

    def test_sine_wave_phase_shift(self) -> None:
        """Test on sine wave (visual phase shift)."""
        # Create a sine wave (one full cycle)
        n_points = 32
        points = [
            CurvePoint(
                t=i / (n_points - 1), v=0.5 + 0.5 * math.sin(2 * math.pi * i / (n_points - 1))
            )
            for i in range(n_points)
        ]

        # Phase shift by 0.25 (90 degrees)
        result = apply_phase_shift_samples(points, offset_norm=0.25, n_samples=16, wrap=True)

        # At t=0, we should get value from t=0.25 of original sine
        # sin(2π * 0.25) = sin(π/2) = 1.0 → v = 0.5 + 0.5 * 1.0 = 1.0
        assert abs(result[0].v - 1.0) < 0.05  # Allow some interpolation error


class TestPhaseShiftMinimalCase:
    """Tests for minimal sample counts."""

    def test_n_samples_2_minimal(self) -> None:
        """Test n_samples=2 (minimal case)."""
        points = [
            CurvePoint(t=0.0, v=0.0),
            CurvePoint(t=1.0, v=1.0),
        ]
        result = apply_phase_shift_samples(points, offset_norm=0.0, n_samples=2)

        assert len(result) == 2
        assert result[0].t == 0.0
        assert result[1].t == 0.5


class TestPhaseShiftEdgeCases:
    """Tests for edge cases."""

    def test_empty_points_raises_error(self) -> None:
        """Test empty points raises ValueError."""
        with pytest.raises(ValueError, match="points cannot be empty"):
            apply_phase_shift_samples([], offset_norm=0.0, n_samples=4)

    def test_n_samples_1_raises_error(self) -> None:
        """Test n_samples=1 raises ValueError."""
        points = [CurvePoint(t=0.0, v=0.0), CurvePoint(t=1.0, v=1.0)]
        with pytest.raises(ValueError, match="n_samples must be >= 2"):
            apply_phase_shift_samples(points, offset_norm=0.0, n_samples=1)


class TestPhaseShiftPerformance:
    """Performance benchmarks."""

    def test_64_sample_shift_under_1ms(self) -> None:
        """Benchmark: 64-sample curve shift < 1ms."""
        points = [CurvePoint(t=i / 63, v=(i / 63) ** 2) for i in range(64)]

        start = time.perf_counter()
        for _ in range(100):
            apply_phase_shift_samples(points, offset_norm=0.25, n_samples=64)
        elapsed_ms = (time.perf_counter() - start) * 1000 / 100

        assert elapsed_ms < 1.0, f"64-sample shift took {elapsed_ms:.3f}ms (should be < 1ms)"
