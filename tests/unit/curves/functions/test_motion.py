"""Tests for motion curve generators."""

from __future__ import annotations

import pytest

from twinklr.core.curves.functions.motion import generate_anticipate, generate_overshoot


class TestGenerateAnticipate:
    """Tests for generate_anticipate function."""

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
