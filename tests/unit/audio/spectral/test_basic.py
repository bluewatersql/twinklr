"""Tests for basic spectral feature extraction."""

from __future__ import annotations

import numpy as np

from twinklr.core.audio.spectral.basic import extract_spectral_features


class TestExtractSpectralFeatures:
    """Tests for extract_spectral_features function."""

    def test_returns_expected_structure(
        self,
        sine_wave_440hz: np.ndarray,
        sample_rate: int,
        hop_length: int,
        frame_length: int,
    ) -> None:
        """Function returns expected dictionary structure."""
        result = extract_spectral_features(
            sine_wave_440hz,
            sample_rate,
            hop_length=hop_length,
            frame_length=frame_length,
        )

        assert "times_s" in result
        assert "brightness" in result
        assert "fullness" in result
        assert "high_freq_energy" in result
        assert "spectral_flatness" in result
        assert "statistics" in result

    def test_has_numpy_arrays_in_np_dict(
        self,
        sine_wave_440hz: np.ndarray,
        sample_rate: int,
        hop_length: int,
        frame_length: int,
    ) -> None:
        """_np dict contains numpy arrays for further processing."""
        result = extract_spectral_features(
            sine_wave_440hz,
            sample_rate,
            hop_length=hop_length,
            frame_length=frame_length,
        )

        assert "_np" in result
        assert "centroid_norm" in result["_np"]
        assert "flatness_norm" in result["_np"]
        assert isinstance(result["_np"]["centroid_norm"], np.ndarray)

    def test_all_features_same_length(
        self,
        sine_wave_440hz: np.ndarray,
        sample_rate: int,
        hop_length: int,
        frame_length: int,
    ) -> None:
        """All spectral features have same length as times."""
        result = extract_spectral_features(
            sine_wave_440hz,
            sample_rate,
            hop_length=hop_length,
            frame_length=frame_length,
        )

        times_len = len(result["times_s"])
        assert len(result["brightness"]) == times_len
        assert len(result["fullness"]) == times_len
        assert len(result["high_freq_energy"]) == times_len
        assert len(result["spectral_flatness"]) == times_len

    def test_features_in_valid_range(
        self,
        sine_wave_440hz: np.ndarray,
        sample_rate: int,
        hop_length: int,
        frame_length: int,
    ) -> None:
        """Normalized features are in [0, 1] range."""
        result = extract_spectral_features(
            sine_wave_440hz,
            sample_rate,
            hop_length=hop_length,
            frame_length=frame_length,
        )

        for key in ["brightness", "fullness", "high_freq_energy", "spectral_flatness"]:
            values = result[key]
            if values:
                assert min(values) >= 0.0
                assert max(values) <= 1.0

    def test_statistics_structure(
        self,
        sine_wave_440hz: np.ndarray,
        sample_rate: int,
        hop_length: int,
        frame_length: int,
    ) -> None:
        """Statistics dict contains expected keys."""
        result = extract_spectral_features(
            sine_wave_440hz,
            sample_rate,
            hop_length=hop_length,
            frame_length=frame_length,
        )

        stats = result["statistics"]
        assert "avg_brightness" in stats
        assert "brightness_variance" in stats
        assert "avg_fullness" in stats
        assert "flatness_avg" in stats

    def test_pure_sine_has_low_flatness(
        self,
        sine_wave_440hz: np.ndarray,
        sample_rate: int,
        hop_length: int,
        frame_length: int,
    ) -> None:
        """Pure sine wave has low spectral flatness (tonal, not noisy)."""
        result = extract_spectral_features(
            sine_wave_440hz,
            sample_rate,
            hop_length=hop_length,
            frame_length=frame_length,
        )

        # Sine wave is very tonal, should have low flatness average
        # (raw flatness, not normalized)
        assert result["statistics"]["flatness_avg"] < 0.5

    def test_noise_has_high_flatness(
        self,
        noisy_audio: np.ndarray,
        sample_rate: int,
        hop_length: int,
        frame_length: int,
    ) -> None:
        """White noise has higher spectral flatness."""
        result = extract_spectral_features(
            noisy_audio,
            sample_rate,
            hop_length=hop_length,
            frame_length=frame_length,
        )

        # Noise has relatively flat spectrum
        assert result["statistics"]["flatness_avg"] > 0.1

    def test_output_lists_are_float_lists(
        self,
        sine_wave_440hz: np.ndarray,
        sample_rate: int,
        hop_length: int,
        frame_length: int,
    ) -> None:
        """Output lists are Python float lists (JSON serializable)."""
        result = extract_spectral_features(
            sine_wave_440hz,
            sample_rate,
            hop_length=hop_length,
            frame_length=frame_length,
        )

        assert isinstance(result["brightness"], list)
        if result["brightness"]:
            assert isinstance(result["brightness"][0], float)

    def test_times_are_increasing(
        self,
        sine_wave_440hz: np.ndarray,
        sample_rate: int,
        hop_length: int,
        frame_length: int,
    ) -> None:
        """Time values are monotonically increasing."""
        result = extract_spectral_features(
            sine_wave_440hz,
            sample_rate,
            hop_length=hop_length,
            frame_length=frame_length,
        )

        times = result["times_s"]
        for i in range(1, len(times)):
            assert times[i] > times[i - 1]
