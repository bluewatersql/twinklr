"""Tests for phase shift implementation."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from blinkb0t.core.curves.phase import apply_phase_shift_samples

if TYPE_CHECKING:
    from blinkb0t.core.curves.models import CurvePoint


class TestApplyPhaseShiftSamples:
    """Tests for apply_phase_shift_samples function."""

    def test_zero_offset_preserves_curve(self, ramp_up_points: list[CurvePoint]) -> None:
        """Zero offset returns same values at same times."""
        result = apply_phase_shift_samples(ramp_up_points, 0.0, 4)
        assert len(result) == 4
        # Values should match interpolated values at uniform grid
        assert result[0].v == pytest.approx(0.0)

    def test_positive_offset_reads_ahead(self, ramp_up_points: list[CurvePoint]) -> None:
        """Positive offset samples from later in the curve."""
        result = apply_phase_shift_samples(ramp_up_points, 0.25, 4, wrap=True)
        # At t=0 with offset 0.25, reads from t=0.25
        assert result[0].v == pytest.approx(0.25)

    def test_negative_offset_reads_behind(self, ramp_up_points: list[CurvePoint]) -> None:
        """Negative offset samples from earlier in the curve (wraps)."""
        result = apply_phase_shift_samples(ramp_up_points, -0.25, 4, wrap=True)
        # At t=0 with offset -0.25, wraps to t=0.75
        assert result[0].v == pytest.approx(0.75)

    def test_wrap_mode_wraps_around(self, ramp_up_points: list[CurvePoint]) -> None:
        """Wrap mode wraps offset around [0, 1)."""
        result = apply_phase_shift_samples(ramp_up_points, 1.5, 4, wrap=True)
        # Offset 1.5 wraps to 0.5
        assert result[0].v == pytest.approx(0.5)

    def test_no_wrap_mode_clamps(self, ramp_up_points: list[CurvePoint]) -> None:
        """Non-wrap mode clamps to [0, 1]."""
        result = apply_phase_shift_samples(ramp_up_points, 1.5, 4, wrap=False)
        # At t=0 with offset 1.5, clamps to t=1.0
        assert result[0].v == pytest.approx(1.0)

    def test_no_wrap_negative_clamps_to_zero(self, ramp_up_points: list[CurvePoint]) -> None:
        """Non-wrap mode clamps negative to 0."""
        result = apply_phase_shift_samples(ramp_up_points, -0.5, 4, wrap=False)
        # At t=0 with offset -0.5, clamps to t=0.0
        assert result[0].v == pytest.approx(0.0)

    def test_output_length_matches_n_samples(self, simple_linear_points: list[CurvePoint]) -> None:
        """Output has exactly n_samples points."""
        result = apply_phase_shift_samples(simple_linear_points, 0.1, 10)
        assert len(result) == 10

    def test_output_time_at_uniform_grid(self, simple_linear_points: list[CurvePoint]) -> None:
        """Output t values are at uniform grid."""
        result = apply_phase_shift_samples(simple_linear_points, 0.1, 4)
        expected_t = [0.0, 0.25, 0.5, 0.75]
        for p, expected in zip(result, expected_t, strict=True):
            assert p.t == pytest.approx(expected)

    def test_empty_points_raises(self) -> None:
        """Empty points raises ValueError."""
        with pytest.raises(ValueError, match="points cannot be empty"):
            apply_phase_shift_samples([], 0.0, 4)

    def test_n_samples_less_than_two_raises(self, simple_linear_points: list[CurvePoint]) -> None:
        """n_samples < 2 raises ValueError."""
        with pytest.raises(ValueError, match="n_samples must be >= 2"):
            apply_phase_shift_samples(simple_linear_points, 0.0, 1)

    def test_full_cycle_offset_returns_same(self, sine_wave_points: list[CurvePoint]) -> None:
        """Offset of 1.0 (full cycle) returns same values."""
        result_no_offset = apply_phase_shift_samples(sine_wave_points, 0.0, 8, wrap=True)
        result_full_cycle = apply_phase_shift_samples(sine_wave_points, 1.0, 8, wrap=True)
        for r1, r2 in zip(result_no_offset, result_full_cycle, strict=True):
            assert r1.v == pytest.approx(r2.v, abs=0.01)

    def test_half_cycle_offset(self, sine_wave_points: list[CurvePoint]) -> None:
        """Offset of 0.5 shifts curve by half cycle."""
        result = apply_phase_shift_samples(sine_wave_points, 0.5, 4, wrap=True)
        # At t=0 with offset 0.5, reads from t=0.5 which is v=0.5
        assert result[0].v == pytest.approx(0.5)
