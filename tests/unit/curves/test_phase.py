"""Tests for phase shift implementation."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from twinklr.core.curves.phase import apply_phase_shift_samples

if TYPE_CHECKING:
    from twinklr.core.curves.models import CurvePoint


class TestApplyPhaseShiftSamples:
    """Tests for apply_phase_shift_samples function."""

    def test_empty_points_raises(self) -> None:
        """Empty points raises ValueError."""
        with pytest.raises(ValueError, match="points cannot be empty"):
            apply_phase_shift_samples([], 0.0, 4)

    def test_n_samples_less_than_two_raises(self, simple_linear_points: list[CurvePoint]) -> None:
        """n_samples < 2 raises ValueError."""
        with pytest.raises(ValueError, match="n_samples must be >= 2"):
            apply_phase_shift_samples(simple_linear_points, 0.0, 1)
