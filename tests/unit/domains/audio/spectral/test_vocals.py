"""Tests for vocal detection.

CRITICAL REGRESSION TESTS:
These tests specifically address the TypeError bug where spectral_centroid
and spectral_flatness were being passed as Python lists instead of numpy
arrays, causing "unsupported operand type(s) for -: 'float' and 'list'".

The bug was in extract_spectral_features() calling as_float_list() before
passing to detect_vocals(), which expects numpy arrays for arithmetic ops.
"""

from __future__ import annotations

import numpy as np

from blinkb0t.core.domains.audio.spectral.vocals import detect_vocals


class TestDetectVocalsRegression:
    """Regression tests for detect_vocals() TypeError bugs."""

    def test_detect_vocals_with_numpy_arrays(
        self,
        mock_audio_signal: np.ndarray,
        mock_spectral_centroid: np.ndarray,
        mock_spectral_flatness: np.ndarray,
        mock_times_s: np.ndarray,
        sample_rate: int,
    ):
        """Test that detect_vocals works with numpy arrays (not lists).

        REGRESSION TEST for TypeError: unsupported operand type(s) for -: 'float' and 'list'

        This test verifies that when spectral_centroid and spectral_flatness
        are passed as numpy arrays (as they should be), the function performs
        arithmetic operations correctly.

        The bug occurred when these were converted to lists via as_float_list()
        before being passed to detect_vocals().
        """
        # Split audio into harmonic and percussive (mock)
        y_harm = mock_audio_signal * 0.7  # Harmonic component
        y_perc = mock_audio_signal * 0.3  # Percussive component

        # Verify inputs are numpy arrays (not lists)
        assert isinstance(mock_spectral_centroid, np.ndarray), (
            "spectral_centroid must be numpy array"
        )
        assert isinstance(mock_spectral_flatness, np.ndarray), (
            "spectral_flatness must be numpy array"
        )

        # Call detect_vocals - should NOT raise TypeError
        result = detect_vocals(
            y_harm=y_harm,
            y_perc=y_perc,
            spectral_centroid=mock_spectral_centroid,
            spectral_flatness=mock_spectral_flatness,
            times_s=mock_times_s,
            sr=sample_rate,
        )

        # Verify result structure
        assert isinstance(result, dict)
        assert "is_vocal" in result
        assert "vocal_probability" in result
        assert "vocal_segments" in result
        assert "statistics" in result
        assert isinstance(result["is_vocal"], (list, np.ndarray))
        assert isinstance(result["vocal_probability"], (list, np.ndarray))
        assert isinstance(result["vocal_segments"], list)
        assert isinstance(result["statistics"], dict)

    def test_detect_vocals_arithmetic_operations(
        self,
        mock_spectral_centroid: np.ndarray,
        mock_spectral_flatness: np.ndarray,
        sample_rate: int,
    ):
        """Test that arithmetic operations work correctly with numpy arrays.

        REGRESSION TEST: Verify that flatness_inv = 1.0 - flatness works
        when flatness is a numpy array (not a list).
        """
        # Mock harmonic/percussive components
        n_samples = len(mock_spectral_centroid) * 512  # Approximate
        y_harm = np.random.randn(n_samples).astype(np.float32)
        y_perc = np.random.randn(n_samples).astype(np.float32)
        times_s = np.arange(len(mock_spectral_centroid)) * 512 / sample_rate

        # This should NOT raise: TypeError: unsupported operand type(s) for -: 'float' and 'list'
        result = detect_vocals(
            y_harm=y_harm,
            y_perc=y_perc,
            spectral_centroid=mock_spectral_centroid,
            spectral_flatness=mock_spectral_flatness,
            times_s=times_s,
            sr=sample_rate,
        )

        # If we got here, arithmetic operations succeeded
        assert isinstance(result, dict)

    def test_detect_vocals_fails_with_list_input(self):
        """Test that detect_vocals would fail if given list inputs (anti-regression).

        This test documents what WOULD happen if the bug reoccurs
        (spectral features passed as lists instead of numpy arrays).

        We intentionally pass lists to verify the function now handles this
        by converting to numpy arrays internally.
        """
        # Create list inputs (simulating the bug)
        spectral_centroid_list = [2000.0, 2100.0, 1900.0, 2050.0]
        spectral_flatness_list = [0.2, 0.25, 0.18, 0.22]

        # Create minimal valid inputs
        n_samples = len(spectral_centroid_list) * 512
        y_harm = np.random.randn(n_samples).astype(np.float32)
        y_perc = np.random.randn(n_samples).astype(np.float32)
        times_s = np.array([0.0, 0.023, 0.046, 0.069], dtype=np.float32)
        sr = 22050

        # The function now converts to numpy arrays internally, so this should work
        result = detect_vocals(
            y_harm=y_harm,
            y_perc=y_perc,
            spectral_centroid=spectral_centroid_list,
            spectral_flatness=spectral_flatness_list,
            times_s=times_s,
            sr=sr,
        )

        # Should succeed because function converts lists to arrays
        assert isinstance(result, dict)


class TestDetectVocalsLogic:
    """Tests for detect_vocals() business logic."""

    def test_detect_vocals_returns_expected_structure(
        self,
        mock_audio_signal: np.ndarray,
        mock_spectral_centroid: np.ndarray,
        mock_spectral_flatness: np.ndarray,
        mock_times_s: np.ndarray,
        sample_rate: int,
    ):
        """Test that detect_vocals returns expected structure."""
        y_harm = mock_audio_signal * 0.7
        y_perc = mock_audio_signal * 0.3

        result = detect_vocals(
            y_harm=y_harm,
            y_perc=y_perc,
            spectral_centroid=mock_spectral_centroid,
            spectral_flatness=mock_spectral_flatness,
            times_s=mock_times_s,
            sr=sample_rate,
        )

        # Check all expected keys
        assert "is_vocal" in result
        assert "vocal_probability" in result
        assert "vocal_segments" in result
        assert "statistics" in result

        # Check types
        assert isinstance(result["is_vocal"], (list, np.ndarray))
        assert isinstance(result["vocal_probability"], (list, np.ndarray))
        assert isinstance(result["vocal_segments"], list)
        assert isinstance(result["statistics"], dict)

        # Check statistics structure
        stats = result["statistics"]
        assert "vocal_segment_count" in stats
        assert "total_vocal_duration_s" in stats
        assert "vocal_coverage_pct" in stats
        assert "avg_segment_duration_s" in stats

    def test_detect_vocals_probability_bounds(
        self,
        mock_audio_signal: np.ndarray,
        mock_spectral_centroid: np.ndarray,
        mock_spectral_flatness: np.ndarray,
        mock_times_s: np.ndarray,
        sample_rate: int,
    ):
        """Test that vocal probabilities are bounded [0, 1]."""
        y_harm = mock_audio_signal * 0.7
        y_perc = mock_audio_signal * 0.3

        result = detect_vocals(
            y_harm=y_harm,
            y_perc=y_perc,
            spectral_centroid=mock_spectral_centroid,
            spectral_flatness=mock_spectral_flatness,
            times_s=mock_times_s,
            sr=sample_rate,
        )

        probabilities = result["vocal_probability"]
        probabilities_array = np.asarray(probabilities)
        assert np.all(probabilities_array >= 0.0), "Some probabilities < 0"
        assert np.all(probabilities_array <= 1.0), "Some probabilities > 1"

    def test_detect_vocals_with_high_centroid_suggests_vocals(
        self,
        sample_rate: int,
    ):
        """Test that high spectral centroid suggests potential vocals."""
        # Create synthetic data with high centroid (typical for vocals: 2000-4000 Hz)
        n_frames = 100
        high_centroid = np.full(n_frames, 3000.0, dtype=np.float32)  # High = vocals
        low_flatness = np.full(n_frames, 0.1, dtype=np.float32)  # Low flatness = tonal

        n_samples = n_frames * 512
        y_harm = np.random.randn(n_samples).astype(np.float32) * 0.5
        y_perc = np.random.randn(n_samples).astype(np.float32) * 0.1
        times_s = np.arange(n_frames) * 512 / sample_rate

        result = detect_vocals(
            y_harm=y_harm,
            y_perc=y_perc,
            spectral_centroid=high_centroid,
            spectral_flatness=low_flatness,
            times_s=times_s,
            sr=sample_rate,
        )

        # With high centroid and low flatness, should suggest vocals
        # (Note: actual detection depends on full algorithm, this is a heuristic test)
        probabilities = np.asarray(result["vocal_probability"])
        assert np.all(probabilities >= 0.0)  # At minimum, should be valid
        # High centroid + low flatness typically indicates higher vocal probability
        assert np.mean(probabilities) > 0.5  # Should be above chance
