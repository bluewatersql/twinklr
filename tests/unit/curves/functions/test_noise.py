"""Tests for noise curve generators."""

from __future__ import annotations

import pytest

from blinkb0t.core.curves.functions.noise import (
    _normalize_noise,
    generate_perlin_noise,
)


class TestNormalizeNoise:
    """Tests for _normalize_noise helper function."""

    def test_negative_one_maps_to_zero(self) -> None:
        """Value of -1.0 maps to 0.0."""
        assert _normalize_noise(-1.0) == pytest.approx(0.0)

    def test_positive_one_maps_to_one(self) -> None:
        """Value of 1.0 maps to 1.0."""
        assert _normalize_noise(1.0) == pytest.approx(1.0)

    def test_zero_maps_to_half(self) -> None:
        """Value of 0.0 maps to 0.5."""
        assert _normalize_noise(0.0) == pytest.approx(0.5)

    def test_clamps_below_negative_one(self) -> None:
        """Values below -1.0 are clamped to 0.0."""
        assert _normalize_noise(-2.0) == pytest.approx(0.0)

    def test_clamps_above_positive_one(self) -> None:
        """Values above 1.0 are clamped to 1.0."""
        assert _normalize_noise(2.0) == pytest.approx(1.0)


class TestGeneratePerlinNoise:
    """Tests for generate_perlin_noise function."""

    def test_returns_correct_count(self) -> None:
        """Returns requested number of samples."""
        result = generate_perlin_noise(10)
        assert len(result) == 10

    def test_values_in_valid_range(self) -> None:
        """All values are in [0, 1]."""
        result = generate_perlin_noise(50)
        for p in result:
            assert 0.0 <= p.v <= 1.0

    def test_times_in_valid_range(self) -> None:
        """All times are in [0, 1)."""
        result = generate_perlin_noise(10)
        for p in result:
            assert 0.0 <= p.t < 1.0

    def test_n_less_than_two_raises(self) -> None:
        """n < 2 raises ValueError."""
        with pytest.raises(ValueError, match="n_samples must be >= 2"):
            generate_perlin_noise(1)

    def test_custom_scale(self) -> None:
        """Custom scale parameter works."""
        result = generate_perlin_noise(20, scale=8.0)
        assert len(result) == 20

    def test_custom_octaves(self) -> None:
        """Custom octaves parameter works."""
        result = generate_perlin_noise(20, octaves=2)
        assert len(result) == 20

    def test_custom_repeat(self) -> None:
        """Custom repeat parameter works."""
        result = generate_perlin_noise(20, repeat=512)
        assert len(result) == 20

    def test_custom_base(self) -> None:
        """Custom base parameter works."""
        result = generate_perlin_noise(20, base=42)
        assert len(result) == 20

    def test_different_bases_produce_different_curves(self) -> None:
        """Different base values produce different curves."""
        result_base0 = generate_perlin_noise(20, base=0)
        result_base1 = generate_perlin_noise(20, base=1)
        # At least some values should differ
        differences = [abs(a.v - b.v) for a, b in zip(result_base0, result_base1, strict=True)]
        assert any(d > 0.01 for d in differences)
