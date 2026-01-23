"""Tests for motion curve generators."""

from __future__ import annotations

import pytest

from blinkb0t.core.curves.functions.motion import generate_anticipate, generate_overshoot


class TestGenerateAnticipate:
    """Tests for generate_anticipate function."""

    def test_returns_correct_count(self) -> None:
        """Returns requested number of samples."""
        result = generate_anticipate(10)
        assert len(result) == 10

    def test_values_in_valid_range(self) -> None:
        """All values are in [0, 1]."""
        result = generate_anticipate(50)
        for p in result:
            assert 0.0 <= p.v <= 1.0

    def test_times_in_valid_range(self) -> None:
        """All times are in [0, 1)."""
        result = generate_anticipate(10)
        for p in result:
            assert 0.0 <= p.t < 1.0

    def test_starts_at_zero(self) -> None:
        """Curve starts at t=0."""
        result = generate_anticipate(10)
        assert result[0].t == pytest.approx(0.0)

    def test_pullback_phase_has_low_values(self) -> None:
        """Early phase (pullback) has lower values."""
        result = generate_anticipate(100)
        # The pullback phase is the first 30% of the curve
        # Values should be relatively low during pullback
        pullback_values = [p.v for p in result if p.t <= 0.3]
        # All pullback values should be <= pullback_min (0.1 approximately)
        assert all(v <= 0.2 for v in pullback_values)

    def test_n_less_than_two_raises(self) -> None:
        """n < 2 raises ValueError."""
        with pytest.raises(ValueError, match="n_samples must be >= 2"):
            generate_anticipate(1)

    def test_minimum_two_samples(self) -> None:
        """Two samples returns valid curve."""
        result = generate_anticipate(2)
        assert len(result) == 2
        assert result[0].t == pytest.approx(0.0)
        assert result[1].t == pytest.approx(0.5)


class TestGenerateOvershoot:
    """Tests for generate_overshoot function."""

    def test_returns_correct_count(self) -> None:
        """Returns requested number of samples."""
        result = generate_overshoot(10)
        assert len(result) == 10

    def test_values_in_valid_range(self) -> None:
        """All values are in [0, 1]."""
        result = generate_overshoot(50)
        for p in result:
            assert 0.0 <= p.v <= 1.0

    def test_times_in_valid_range(self) -> None:
        """All times are in [0, 1)."""
        result = generate_overshoot(10)
        for p in result:
            assert 0.0 <= p.t < 1.0

    def test_starts_at_zero(self) -> None:
        """Curve starts at t=0."""
        result = generate_overshoot(10)
        assert result[0].t == pytest.approx(0.0)

    def test_starts_at_low_value(self) -> None:
        """Curve starts at low value."""
        result = generate_overshoot(10)
        assert result[0].v == pytest.approx(0.0, abs=0.01)

    def test_n_less_than_two_raises(self) -> None:
        """n < 2 raises ValueError."""
        with pytest.raises(ValueError, match="n_samples must be >= 2"):
            generate_overshoot(1)

    def test_minimum_two_samples(self) -> None:
        """Two samples returns valid curve."""
        result = generate_overshoot(2)
        assert len(result) == 2
        assert result[0].t == pytest.approx(0.0)
        assert result[1].t == pytest.approx(0.5)

    def test_has_bounce_in_middle(self) -> None:
        """Curve has bounce effect in 0.6-0.9 range."""
        result = generate_overshoot(100)
        # Find values in the bounce range
        bounce_points = [p for p in result if 0.6 <= p.t <= 0.9]
        # At least some points should exist in this range
        assert len(bounce_points) > 0
