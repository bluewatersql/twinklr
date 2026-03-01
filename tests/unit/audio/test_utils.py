"""Tests for audio utility functions."""

from __future__ import annotations

import numpy as np
import pytest

from twinklr.core.audio.utils import (
    align_to_length,
    as_float_list,
    frames_to_time,
    normalize_to_0_1,
    safe_divide,
)


class TestNormalizeTo01:
    """Tests for normalize_to_0_1 function."""

    def test_basic_normalization(self) -> None:
        """Test basic array normalization."""
        arr = np.array([0, 50, 100], dtype=np.float32)
        result = normalize_to_0_1(arr)

        assert result[0] == pytest.approx(0.0)
        assert result[1] == pytest.approx(0.5)
        assert result[2] == pytest.approx(1.0)

    def test_negative_values(self) -> None:
        """Handles negative values correctly."""
        arr = np.array([-10, 0, 10], dtype=np.float32)
        result = normalize_to_0_1(arr)

        assert result[0] == pytest.approx(0.0)
        assert result[1] == pytest.approx(0.5)
        assert result[2] == pytest.approx(1.0)

    def test_basic_conversion(self, sample_rate: int, hop_length: int) -> None:
        """Test basic frame to time conversion."""
        frames = np.array([0, 43, 86], dtype=int)  # ~0, 1, 2 seconds at sr=22050, hop=512
        result = frames_to_time(frames, sr=sample_rate, hop_length=hop_length)

        assert result[0] == pytest.approx(0.0, abs=0.01)
        assert result[1] == pytest.approx(1.0, abs=0.05)  # ~1 second
        assert result[2] == pytest.approx(2.0, abs=0.05)  # ~2 seconds

    def test_normal_division(self) -> None:
        """Normal division works correctly."""
        a = np.array([10.0, 20.0, 30.0], dtype=np.float32)
        b = np.array([2.0, 4.0, 5.0], dtype=np.float32)
        result = safe_divide(a, b)

        assert result[0] == pytest.approx(5.0)
        assert result[1] == pytest.approx(5.0)
        assert result[2] == pytest.approx(6.0)

    def test_division_by_zero_returns_default(self) -> None:
        """Division by zero returns default value."""
        a = np.array([10.0, 20.0, 30.0], dtype=np.float32)
        b = np.array([2.0, 0.0, 5.0], dtype=np.float32)
        result = safe_divide(a, b, default=0.0)

        assert result[0] == pytest.approx(5.0)
        assert result[1] == pytest.approx(0.0)  # Default
        assert result[2] == pytest.approx(6.0)

    def test_padding(self) -> None:
        """Shorter array is padded with edge values."""
        arr = np.array([1.0, 2.0, 3.0], dtype=np.float32)
        result = align_to_length(arr, 5)

        assert len(result) == 5
        assert result[3] == 3.0  # Edge padding
        assert result[4] == 3.0


class TestAsFloatList:
    """Tests for as_float_list function (PERF-13)."""

    def test_output_equivalence_with_original(self) -> None:
        """Optimized implementation produces values consistent with rounding.

        The original implementation used float32 intermediate precision, which
        could introduce small rounding artifacts. The new float64 path is
        *more* precise. We verify that each output value equals ``round(x, 3)``
        computed at full float64 precision.
        """
        rng = np.random.default_rng(42)
        x = rng.standard_normal(1000).astype(np.float64) * 100

        optimized = as_float_list(x, ndigits=3)
        expected = [round(float(v), 3) for v in x]

        assert len(optimized) == len(expected)
        for exp, opt in zip(expected, optimized, strict=True):
            assert opt == pytest.approx(exp, abs=1e-9)

    def test_output_is_list_of_python_floats(self) -> None:
        """Result is a plain list of native Python float objects."""
        x = np.array([1.1234, 2.5678, 3.9012], dtype=np.float64)
        result = as_float_list(x)

        assert isinstance(result, list)
        assert all(isinstance(v, float) for v in result)

    def test_rounding_default_3_decimal_places(self) -> None:
        """Default ndigits=3 rounds to 3 decimal places."""
        x = np.array([1.23456, 2.78901, 0.00049])
        result = as_float_list(x)

        assert result[0] == pytest.approx(1.235)
        assert result[1] == pytest.approx(2.789)
        assert result[2] == pytest.approx(0.0)

    def test_rounding_custom_ndigits(self) -> None:
        """Custom ndigits parameter is respected."""
        x = np.array([1.23456, 2.78901])
        result = as_float_list(x, ndigits=1)

        assert result[0] == pytest.approx(1.2)
        assert result[1] == pytest.approx(2.8)

    def test_empty_array(self) -> None:
        """Empty input returns empty list."""
        x = np.array([], dtype=np.float64)
        result = as_float_list(x)

        assert result == []
        assert isinstance(result, list)
