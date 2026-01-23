"""Tests for audio utility functions."""

from __future__ import annotations

import numpy as np
import pytest

from blinkb0t.core.audio.utils import (
    align_to_length,
    as_float_list,
    cosine_similarity,
    frames_to_time,
    normalize_to_0_1,
    safe_divide,
    time_to_frames,
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

    def test_empty_array(self, empty_array: np.ndarray) -> None:
        """Empty array returns empty array."""
        result = normalize_to_0_1(empty_array)
        assert len(result) == 0

    def test_single_value(self, single_value_array: np.ndarray) -> None:
        """Single value returns zeros (no range to normalize)."""
        result = normalize_to_0_1(single_value_array)
        assert result[0] == 0.0

    def test_constant_array(self, constant_array: np.ndarray) -> None:
        """All same values returns zeros (no range)."""
        result = normalize_to_0_1(constant_array)
        assert np.all(result == 0.0)

    def test_output_range(self) -> None:
        """Output should always be in [0, 1] range."""
        rng = np.random.default_rng(42)
        arr = rng.uniform(-1000, 1000, 1000).astype(np.float32)
        result = normalize_to_0_1(arr)

        assert result.min() >= 0.0
        assert result.max() <= 1.0

    def test_negative_values(self) -> None:
        """Handles negative values correctly."""
        arr = np.array([-10, 0, 10], dtype=np.float32)
        result = normalize_to_0_1(arr)

        assert result[0] == pytest.approx(0.0)
        assert result[1] == pytest.approx(0.5)
        assert result[2] == pytest.approx(1.0)

    def test_float_dtype(self) -> None:
        """Output is float32."""
        arr = np.array([1, 2, 3], dtype=np.int32)
        result = normalize_to_0_1(arr)
        assert result.dtype == np.float32

    def test_list_input(self) -> None:
        """Handles list input by converting to array."""
        result = normalize_to_0_1([0, 50, 100])  # type: ignore[arg-type]
        assert result[0] == pytest.approx(0.0)
        assert result[2] == pytest.approx(1.0)


class TestFramesToTime:
    """Tests for frames_to_time function."""

    def test_basic_conversion(self, sample_rate: int, hop_length: int) -> None:
        """Test basic frame to time conversion."""
        frames = np.array([0, 43, 86], dtype=int)  # ~0, 1, 2 seconds at sr=22050, hop=512
        result = frames_to_time(frames, sr=sample_rate, hop_length=hop_length)

        assert result[0] == pytest.approx(0.0, abs=0.01)
        assert result[1] == pytest.approx(1.0, abs=0.05)  # ~1 second
        assert result[2] == pytest.approx(2.0, abs=0.05)  # ~2 seconds

    def test_empty_frames(self, sample_rate: int, hop_length: int) -> None:
        """Empty frames array returns empty times."""
        frames = np.array([], dtype=int)
        result = frames_to_time(frames, sr=sample_rate, hop_length=hop_length)
        assert len(result) == 0

    def test_output_dtype(self, sample_rate: int, hop_length: int) -> None:
        """Output is float32."""
        frames = np.array([0, 100, 200], dtype=int)
        result = frames_to_time(frames, sr=sample_rate, hop_length=hop_length)
        assert result.dtype == np.float32


class TestTimeToFrames:
    """Tests for time_to_frames function."""

    def test_basic_conversion(self, sample_rate: int, hop_length: int) -> None:
        """Test basic time to frame conversion."""
        times = np.array([0.0, 1.0, 2.0], dtype=np.float32)
        n_frames = 500
        result = time_to_frames(times, sr=sample_rate, hop_length=hop_length, n_frames=n_frames)

        assert result[0] == 0
        # At sr=22050, hop=512: 1 second = 22050/512 ≈ 43 frames
        assert result[1] == pytest.approx(43, abs=2)

    def test_clipping_to_n_frames(self, sample_rate: int, hop_length: int) -> None:
        """Times beyond n_frames are clipped."""
        times = np.array([0.0, 100.0, 1000.0], dtype=np.float32)  # Way beyond reasonable
        n_frames = 100
        result = time_to_frames(times, sr=sample_rate, hop_length=hop_length, n_frames=n_frames)

        assert result.max() <= n_frames - 1

    def test_negative_times_clipped(self, sample_rate: int, hop_length: int) -> None:
        """Negative times are clipped to 0."""
        times = np.array([-1.0, 0.0, 1.0], dtype=np.float32)
        n_frames = 500
        result = time_to_frames(times, sr=sample_rate, hop_length=hop_length, n_frames=n_frames)

        assert result[0] >= 0


class TestSafeDivide:
    """Tests for safe_divide function."""

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

    def test_custom_default(self) -> None:
        """Custom default value works."""
        a = np.array([10.0], dtype=np.float32)
        b = np.array([0.0], dtype=np.float32)
        result = safe_divide(a, b, default=-1.0)

        assert result[0] == pytest.approx(-1.0)

    def test_very_small_denominator_treated_as_zero(self) -> None:
        """Very small denominators (<1e-9) treated as zero."""
        a = np.array([10.0], dtype=np.float32)
        b = np.array([1e-12], dtype=np.float32)
        result = safe_divide(a, b, default=0.0)

        assert result[0] == pytest.approx(0.0)

    def test_output_dtype(self) -> None:
        """Output is float32."""
        a = np.array([1, 2, 3], dtype=np.int32)
        b = np.array([1, 2, 3], dtype=np.int32)
        result = safe_divide(a, b)
        assert result.dtype == np.float32


class TestAlignToLength:
    """Tests for align_to_length function."""

    def test_exact_length(self) -> None:
        """Array already at target length returned unchanged."""
        arr = np.array([1.0, 2.0, 3.0], dtype=np.float32)
        result = align_to_length(arr, 3)

        assert len(result) == 3
        np.testing.assert_array_equal(result, arr)

    def test_truncation(self) -> None:
        """Longer array is truncated."""
        arr = np.array([1.0, 2.0, 3.0, 4.0, 5.0], dtype=np.float32)
        result = align_to_length(arr, 3)

        assert len(result) == 3
        np.testing.assert_array_equal(result, [1.0, 2.0, 3.0])

    def test_padding(self) -> None:
        """Shorter array is padded with edge values."""
        arr = np.array([1.0, 2.0, 3.0], dtype=np.float32)
        result = align_to_length(arr, 5)

        assert len(result) == 5
        assert result[3] == 3.0  # Edge padding
        assert result[4] == 3.0

    def test_preserves_dtype(self) -> None:
        """Output preserves input dtype."""
        arr = np.array([1, 2, 3], dtype=np.int32)
        result = align_to_length(arr, 5)
        assert result.dtype == arr.dtype


class TestCosineSimilarity:
    """Tests for cosine_similarity function."""

    def test_identical_vectors(self) -> None:
        """Identical vectors have similarity 1.0."""
        a = np.array([1.0, 2.0, 3.0], dtype=np.float32)
        result = cosine_similarity(a, a)
        assert result == pytest.approx(1.0, abs=0.001)

    def test_orthogonal_vectors(self) -> None:
        """Orthogonal vectors have similarity 0.0."""
        a = np.array([1.0, 0.0], dtype=np.float32)
        b = np.array([0.0, 1.0], dtype=np.float32)
        result = cosine_similarity(a, b)
        assert result == pytest.approx(0.0, abs=0.001)

    def test_opposite_vectors(self) -> None:
        """Opposite vectors have similarity -1.0."""
        a = np.array([1.0, 0.0], dtype=np.float32)
        b = np.array([-1.0, 0.0], dtype=np.float32)
        result = cosine_similarity(a, b)
        assert result == pytest.approx(-1.0, abs=0.001)

    def test_zero_vector_returns_zero(self) -> None:
        """Zero vector returns 0 similarity."""
        a = np.array([0.0, 0.0, 0.0], dtype=np.float32)
        b = np.array([1.0, 2.0, 3.0], dtype=np.float32)
        result = cosine_similarity(a, b)
        assert result == 0.0

    def test_near_zero_norm_returns_zero(self) -> None:
        """Very small norm vectors return 0."""
        a = np.array([1e-12, 1e-12], dtype=np.float32)
        b = np.array([1.0, 1.0], dtype=np.float32)
        result = cosine_similarity(a, b)
        assert result == 0.0


class TestAsFloatList:
    """Tests for as_float_list function."""

    def test_basic_conversion(self) -> None:
        """Converts numpy array to rounded float list."""
        arr = np.array([1.1234, 2.5678, 3.9999], dtype=np.float32)
        result = as_float_list(arr, ndigits=2)

        # Use approx due to float32 precision limitations
        assert result[0] == pytest.approx(1.12, abs=0.001)
        assert result[1] == pytest.approx(2.57, abs=0.001)
        assert result[2] == pytest.approx(4.0, abs=0.001)

    def test_default_ndigits(self) -> None:
        """Default ndigits is 3."""
        arr = np.array([1.12345, 2.56789], dtype=np.float32)
        result = as_float_list(arr)

        assert result[0] == pytest.approx(1.123, abs=0.001)

    def test_empty_array(self) -> None:
        """Empty array returns empty list."""
        arr = np.array([], dtype=np.float32)
        result = as_float_list(arr)
        assert result == []

    def test_output_type(self) -> None:
        """Output is a Python list of floats."""
        arr = np.array([1.0, 2.0, 3.0], dtype=np.float32)
        result = as_float_list(arr)

        assert isinstance(result, list)
        assert all(isinstance(x, float) for x in result)
