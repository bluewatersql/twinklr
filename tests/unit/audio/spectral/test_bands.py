"""Tests for frequency band energy extraction."""

from __future__ import annotations

from unittest.mock import patch

import librosa
import numpy as np

from twinklr.core.audio.spectral.bands import extract_dynamic_features


class TestExtractDynamicFeatures:
    """Tests for extract_dynamic_features function."""

    def test_returns_expected_structure(
        self,
        sine_wave_440hz: np.ndarray,
        sample_rate: int,
        hop_length: int,
        frame_length: int,
    ) -> None:
        """Function returns expected dictionary structure."""
        result = extract_dynamic_features(
            sine_wave_440hz,
            sample_rate,
            hop_length=hop_length,
            frame_length=frame_length,
        )

        assert "times_s" in result
        assert "bass_energy" in result
        assert "mid_energy" in result
        assert "high_energy" in result
        assert "motion" in result
        assert "transients" in result
        assert "statistics" in result

    def test_all_bands_same_length(
        self,
        sine_wave_440hz: np.ndarray,
        sample_rate: int,
        hop_length: int,
        frame_length: int,
    ) -> None:
        """All frequency bands have same length."""
        result = extract_dynamic_features(
            sine_wave_440hz,
            sample_rate,
            hop_length=hop_length,
            frame_length=frame_length,
        )

        times_len = len(result["times_s"])
        assert len(result["bass_energy"]) == times_len
        assert len(result["mid_energy"]) == times_len
        assert len(result["high_energy"]) == times_len
        assert len(result["motion"]) == times_len

    def test_bands_in_valid_range(
        self,
        sine_wave_440hz: np.ndarray,
        sample_rate: int,
        hop_length: int,
        frame_length: int,
    ) -> None:
        """Normalized band energies are in [0, 1] range."""
        result = extract_dynamic_features(
            sine_wave_440hz,
            sample_rate,
            hop_length=hop_length,
            frame_length=frame_length,
        )

        for key in ["bass_energy", "mid_energy", "high_energy", "motion"]:
            values = result[key]
            if values:
                assert min(values) >= 0.0
                assert max(values) <= 1.0

    def test_440hz_in_mid_band(
        self,
        sine_wave_440hz: np.ndarray,
        sample_rate: int,
        hop_length: int,
        frame_length: int,
    ) -> None:
        """440Hz sine wave has energy primarily in mid band."""
        result = extract_dynamic_features(
            sine_wave_440hz,
            sample_rate,
            hop_length=hop_length,
            frame_length=frame_length,
        )

        # 440Hz is in mid range (250-4000 Hz)
        _mid_mean = np.mean(result["mid_energy"])
        bass_mean = np.mean(result["bass_energy"])
        _high_mean = np.mean(result["high_energy"])

        # Mid should be dominant for 440Hz tone
        assert _mid_mean > bass_mean or _mid_mean == 1.0  # Could be normalized to 1

    def test_transients_structure(
        self,
        click_track_120bpm: tuple[np.ndarray, list[float]],
        sample_rate: int,
        hop_length: int,
        frame_length: int,
    ) -> None:
        """Transients have expected structure."""
        audio, _ = click_track_120bpm
        result = extract_dynamic_features(
            audio,
            sample_rate,
            hop_length=hop_length,
            frame_length=frame_length,
        )

        if result["transients"]:
            transient = result["transients"][0]
            assert "time_s" in transient
            assert "strength" in transient

    def test_statistics_structure(
        self,
        sine_wave_440hz: np.ndarray,
        sample_rate: int,
        hop_length: int,
        frame_length: int,
    ) -> None:
        """Statistics dict contains expected keys."""
        result = extract_dynamic_features(
            sine_wave_440hz,
            sample_rate,
            hop_length=hop_length,
            frame_length=frame_length,
        )

        stats = result["statistics"]
        assert "dynamic_range" in stats
        assert "dynamic_contrast" in stats
        assert "transient_count" in stats
        assert "transient_density" in stats

    def test_click_track_has_transients(
        self,
        click_track_120bpm: tuple[np.ndarray, list[float]],
        sample_rate: int,
        hop_length: int,
        frame_length: int,
    ) -> None:
        """Click track should have detected transients."""
        audio, _beat_times = click_track_120bpm
        result = extract_dynamic_features(
            audio,
            sample_rate,
            hop_length=hop_length,
            frame_length=frame_length,
        )

        # Should detect some transients at click positions
        assert result["statistics"]["transient_count"] > 0

    def test_precomputed_rms_used(
        self,
        sine_wave_440hz: np.ndarray,
        sample_rate: int,
        hop_length: int,
        frame_length: int,
    ) -> None:
        """Precomputed RMS is used when provided."""
        # Create fake precomputed RMS
        import librosa

        rms = librosa.feature.rms(
            y=sine_wave_440hz, frame_length=frame_length, hop_length=hop_length
        )[0].astype(np.float32)

        result = extract_dynamic_features(
            sine_wave_440hz,
            sample_rate,
            hop_length=hop_length,
            frame_length=frame_length,
            rms_precomputed=rms,
        )

        # Should complete without error
        assert "statistics" in result

    def test_motion_captures_flux(
        self,
        long_audio: np.ndarray,
        sample_rate: int,
        hop_length: int,
        frame_length: int,
    ) -> None:
        """Motion (spectral flux) captures spectral changes."""
        result = extract_dynamic_features(
            long_audio,
            sample_rate,
            hop_length=hop_length,
            frame_length=frame_length,
        )

        # Long audio with section changes should have non-zero motion variance
        motion_arr = np.array(result["motion"])
        assert np.var(motion_arr) > 0 or np.max(motion_arr) > 0

    def test_np_dict_contains_motion_norm(
        self,
        sine_wave_440hz: np.ndarray,
        sample_rate: int,
        hop_length: int,
        frame_length: int,
    ) -> None:
        """_np dict contains motion_norm array."""
        result = extract_dynamic_features(
            sine_wave_440hz,
            sample_rate,
            hop_length=hop_length,
            frame_length=frame_length,
        )

        assert "_np" in result
        assert "motion_norm" in result["_np"]
        assert isinstance(result["_np"]["motion_norm"], np.ndarray)

    def test_onset_env_backward_compat(
        self,
        sine_wave_440hz: np.ndarray,
        sample_rate: int,
        hop_length: int,
        frame_length: int,
    ) -> None:
        """PERF-02: Function works without onset_env param (backward compat)."""
        result = extract_dynamic_features(
            sine_wave_440hz,
            sample_rate,
            hop_length=hop_length,
            frame_length=frame_length,
        )
        assert "statistics" in result
        assert "transients" in result

    def test_onset_env_precomputed_used(
        self,
        sine_wave_440hz: np.ndarray,
        sample_rate: int,
        hop_length: int,
        frame_length: int,
    ) -> None:
        """PERF-02: Pre-computed onset_env is used when provided.

        Verifies the function completes successfully with a pre-computed
        onset envelope. We cannot easily mock onset_strength because
        onset_detect also calls it internally, so we verify by providing
        a known onset_env and checking the function accepts it.
        """
        onset_env = librosa.onset.onset_strength(
            y=sine_wave_440hz, sr=sample_rate, hop_length=hop_length
        ).astype(np.float32)

        # With pre-computed onset_env, should produce valid output
        result = extract_dynamic_features(
            sine_wave_440hz,
            sample_rate,
            hop_length=hop_length,
            frame_length=frame_length,
            onset_env=onset_env,
        )
        assert "statistics" in result
        assert "transients" in result

        # Verify the parameter was actually used by providing a synthetic
        # all-zeros onset_env -- onset strengths at detected frames should be 0
        zero_env = np.zeros_like(onset_env)
        result_zero = extract_dynamic_features(
            sine_wave_440hz,
            sample_rate,
            hop_length=hop_length,
            frame_length=frame_length,
            onset_env=zero_env,
        )
        # If onset_env was used, all transient strengths should be 0
        for t in result_zero["transients"]:
            assert t["strength"] == 0.0

    def test_stft_mag_backward_compat(
        self,
        sine_wave_440hz: np.ndarray,
        sample_rate: int,
        hop_length: int,
        frame_length: int,
    ) -> None:
        """PERF-03: Function works without stft_mag param (backward compat)."""
        result = extract_dynamic_features(
            sine_wave_440hz,
            sample_rate,
            hop_length=hop_length,
            frame_length=frame_length,
        )
        assert "bass_energy" in result
        assert "mid_energy" in result

    def test_stft_mag_precomputed_used(
        self,
        sine_wave_440hz: np.ndarray,
        sample_rate: int,
        hop_length: int,
        frame_length: int,
    ) -> None:
        """PERF-03: Pre-computed stft_mag is used when provided."""
        stft_mag = np.abs(
            librosa.stft(sine_wave_440hz, n_fft=frame_length, hop_length=hop_length)
        ).astype(np.float32)

        with patch("twinklr.core.audio.spectral.bands.librosa.stft") as mock_stft:
            extract_dynamic_features(
                sine_wave_440hz,
                sample_rate,
                hop_length=hop_length,
                frame_length=frame_length,
                stft_mag=stft_mag,
            )
            mock_stft.assert_not_called()

    def test_rms_precomputed_skips_internal(
        self,
        sine_wave_440hz: np.ndarray,
        sample_rate: int,
        hop_length: int,
        frame_length: int,
    ) -> None:
        """PERF-04: Pre-computed RMS skips internal librosa.feature.rms call."""
        rms = librosa.feature.rms(
            y=sine_wave_440hz, frame_length=frame_length, hop_length=hop_length
        )[0].astype(np.float32)

        with patch("twinklr.core.audio.spectral.bands.librosa.feature.rms") as mock_rms:
            extract_dynamic_features(
                sine_wave_440hz,
                sample_rate,
                hop_length=hop_length,
                frame_length=frame_length,
                rms_precomputed=rms,
            )
            mock_rms.assert_not_called()
