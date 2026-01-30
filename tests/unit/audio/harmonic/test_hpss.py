"""Tests for harmonic-percussive source separation."""

from __future__ import annotations

import numpy as np

from twinklr.core.audio.harmonic.hpss import compute_hpss, compute_onset_env


class TestComputeHPSS:
    """Tests for compute_hpss function."""

    def test_returns_two_arrays(
        self,
        sine_wave_440hz: np.ndarray,
    ) -> None:
        """Function returns tuple of two arrays."""
        y_harm, y_perc = compute_hpss(sine_wave_440hz)

        assert isinstance(y_harm, np.ndarray)
        assert isinstance(y_perc, np.ndarray)

    def test_output_same_length_as_input(
        self,
        sine_wave_440hz: np.ndarray,
    ) -> None:
        """Harmonic and percussive components have same length as input."""
        y_harm, y_perc = compute_hpss(sine_wave_440hz)

        assert len(y_harm) == len(sine_wave_440hz)
        assert len(y_perc) == len(sine_wave_440hz)

    def test_output_dtype_float32(
        self,
        sine_wave_440hz: np.ndarray,
    ) -> None:
        """Output arrays are float32."""
        y_harm, y_perc = compute_hpss(sine_wave_440hz)

        assert y_harm.dtype == np.float32
        assert y_perc.dtype == np.float32

    def test_sine_wave_mostly_harmonic(
        self,
        sine_wave_440hz: np.ndarray,
    ) -> None:
        """Pure sine wave should be mostly harmonic."""
        y_harm, y_perc = compute_hpss(sine_wave_440hz)

        harm_energy = np.sum(y_harm**2)
        perc_energy = np.sum(y_perc**2)

        # Harmonic should dominate for pure tone
        assert harm_energy > perc_energy

    def test_click_track_has_percussive(
        self,
        click_track_120bpm: tuple[np.ndarray, list[float]],
    ) -> None:
        """Click track should have significant percussive content."""
        audio, _ = click_track_120bpm
        _, y_perc = compute_hpss(audio)

        # Should have some percussive energy
        perc_energy = np.sum(y_perc**2)
        assert perc_energy > 0

    def test_empty_audio_handled(self) -> None:
        """Empty audio is handled gracefully."""
        empty = np.array([], dtype=np.float32)
        y_harm, y_perc = compute_hpss(empty)

        # Should return empty arrays
        assert len(y_harm) == 0
        assert len(y_perc) == 0


class TestComputeOnsetEnv:
    """Tests for compute_onset_env function."""

    def test_returns_array(
        self,
        sine_wave_440hz: np.ndarray,
        sample_rate: int,
        hop_length: int,
    ) -> None:
        """Function returns numpy array."""
        # First get percussive component
        _, y_perc = compute_hpss(sine_wave_440hz)
        onset_env = compute_onset_env(y_perc, sample_rate, hop_length=hop_length)

        assert isinstance(onset_env, np.ndarray)

    def test_output_dtype_float32(
        self,
        sine_wave_440hz: np.ndarray,
        sample_rate: int,
        hop_length: int,
    ) -> None:
        """Output is float32."""
        _, y_perc = compute_hpss(sine_wave_440hz)
        onset_env = compute_onset_env(y_perc, sample_rate, hop_length=hop_length)

        assert onset_env.dtype == np.float32

    def test_click_track_has_peaks(
        self,
        click_track_120bpm: tuple[np.ndarray, list[float]],
        sample_rate: int,
        hop_length: int,
    ) -> None:
        """Click track onset envelope has peaks."""
        audio, _ = click_track_120bpm
        _, y_perc = compute_hpss(audio)
        onset_env = compute_onset_env(y_perc, sample_rate, hop_length=hop_length)

        # Should have variation (peaks at clicks)
        assert np.max(onset_env) > np.mean(onset_env)

    def test_output_non_negative(
        self,
        sine_wave_440hz: np.ndarray,
        sample_rate: int,
        hop_length: int,
    ) -> None:
        """Onset envelope values are non-negative."""
        _, y_perc = compute_hpss(sine_wave_440hz)
        onset_env = compute_onset_env(y_perc, sample_rate, hop_length=hop_length)

        assert np.all(onset_env >= 0)


class TestHPSSFallback:
    """Tests for HPSS fallback behavior when librosa fails."""

    def test_hpss_fallback_on_exception(self) -> None:
        """HPSS returns copies of input on exception."""
        from unittest.mock import patch

        test_audio = np.random.rand(1000).astype(np.float32)

        # Mock librosa.effects.hpss to raise an exception
        with patch("librosa.effects.hpss", side_effect=Exception("HPSS failed")):
            y_harm, y_perc = compute_hpss(test_audio)

            # Should return copies of input
            assert len(y_harm) == len(test_audio)
            assert len(y_perc) == len(test_audio)
            np.testing.assert_array_equal(y_harm, test_audio)
            np.testing.assert_array_equal(y_perc, test_audio)

    def test_hpss_fallback_returns_correct_dtype(self) -> None:
        """Fallback returns float32 arrays."""
        from unittest.mock import patch

        test_audio = np.random.rand(1000).astype(np.float32)

        with patch("librosa.effects.hpss", side_effect=Exception("HPSS failed")):
            y_harm, y_perc = compute_hpss(test_audio)

            assert y_harm.dtype == np.float32
            assert y_perc.dtype == np.float32

    def test_hpss_fallback_with_empty_array(self) -> None:
        """Fallback handles empty array on exception."""
        from unittest.mock import patch

        empty_audio = np.array([], dtype=np.float32)

        with patch("librosa.effects.hpss", side_effect=Exception("HPSS failed")):
            y_harm, y_perc = compute_hpss(empty_audio)

            assert len(y_harm) == 0
            assert len(y_perc) == 0
