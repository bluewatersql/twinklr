"""Tests for multi-scale energy extraction."""

from __future__ import annotations

import numpy as np

from blinkb0t.core.audio.energy.multiscale import extract_smoothed_energy


class TestExtractSmoothedEnergy:
    """Tests for extract_smoothed_energy function."""

    def test_returns_expected_structure(
        self,
        sine_wave_440hz: np.ndarray,
        sample_rate: int,
        hop_length: int,
        frame_length: int,
    ) -> None:
        """Function returns expected dictionary structure."""
        result = extract_smoothed_energy(
            sine_wave_440hz,
            sample_rate,
            hop_length=hop_length,
            frame_length=frame_length,
        )

        assert "times_s" in result
        assert "raw" in result
        assert "beat_level" in result
        assert "phrase_level" in result
        assert "section_level" in result
        assert "statistics" in result

    def test_has_numpy_arrays_in_np_dict(
        self,
        sine_wave_440hz: np.ndarray,
        sample_rate: int,
        hop_length: int,
        frame_length: int,
    ) -> None:
        """_np dict contains numpy arrays for further processing."""
        result = extract_smoothed_energy(
            sine_wave_440hz,
            sample_rate,
            hop_length=hop_length,
            frame_length=frame_length,
        )

        assert "_np" in result
        assert "rms_norm" in result["_np"]
        assert "rms_raw" in result["_np"]
        assert isinstance(result["_np"]["rms_norm"], np.ndarray)

    def test_all_energy_levels_same_length(
        self,
        sine_wave_440hz: np.ndarray,
        sample_rate: int,
        hop_length: int,
        frame_length: int,
    ) -> None:
        """All energy levels have same length."""
        result = extract_smoothed_energy(
            sine_wave_440hz,
            sample_rate,
            hop_length=hop_length,
            frame_length=frame_length,
        )

        times_len = len(result["times_s"])
        assert len(result["raw"]) == times_len
        assert len(result["beat_level"]) == times_len
        assert len(result["phrase_level"]) == times_len
        assert len(result["section_level"]) == times_len

    def test_energy_in_valid_range(
        self,
        sine_wave_440hz: np.ndarray,
        sample_rate: int,
        hop_length: int,
        frame_length: int,
    ) -> None:
        """Normalized energy values are in [0, 1] range."""
        result = extract_smoothed_energy(
            sine_wave_440hz,
            sample_rate,
            hop_length=hop_length,
            frame_length=frame_length,
        )

        for key in ["raw", "beat_level", "phrase_level", "section_level"]:
            values = result[key]
            if values:
                assert min(values) >= 0.0
                assert max(values) <= 1.0

    def test_smoothing_reduces_variance(
        self,
        long_audio: np.ndarray,
        sample_rate: int,
        hop_length: int,
        frame_length: int,
    ) -> None:
        """Section level has lower variance than raw."""
        result = extract_smoothed_energy(
            long_audio,
            sample_rate,
            hop_length=hop_length,
            frame_length=frame_length,
        )

        raw_arr = np.array(result["raw"])
        section_arr = np.array(result["section_level"])

        # More smoothed data should have lower variance
        assert np.var(section_arr) <= np.var(raw_arr) + 1e-6

    def test_statistics_structure(
        self,
        sine_wave_440hz: np.ndarray,
        sample_rate: int,
        hop_length: int,
        frame_length: int,
    ) -> None:
        """Statistics dict contains expected keys."""
        result = extract_smoothed_energy(
            sine_wave_440hz,
            sample_rate,
            hop_length=hop_length,
            frame_length=frame_length,
        )

        stats = result["statistics"]
        assert "raw_variance" in stats
        assert "phrase_variance" in stats
        assert "smoothness_score" in stats

    def test_smoothness_score_non_negative(
        self,
        sine_wave_440hz: np.ndarray,
        sample_rate: int,
        hop_length: int,
        frame_length: int,
    ) -> None:
        """Smoothness score is non-negative."""
        result = extract_smoothed_energy(
            sine_wave_440hz,
            sample_rate,
            hop_length=hop_length,
            frame_length=frame_length,
        )

        assert result["statistics"]["smoothness_score"] >= 0.0

    def test_times_are_increasing(
        self,
        sine_wave_440hz: np.ndarray,
        sample_rate: int,
        hop_length: int,
        frame_length: int,
    ) -> None:
        """Time values are monotonically increasing."""
        result = extract_smoothed_energy(
            sine_wave_440hz,
            sample_rate,
            hop_length=hop_length,
            frame_length=frame_length,
        )

        times = result["times_s"]
        for i in range(1, len(times)):
            assert times[i] > times[i - 1]

    def test_output_lists_are_float_lists(
        self,
        sine_wave_440hz: np.ndarray,
        sample_rate: int,
        hop_length: int,
        frame_length: int,
    ) -> None:
        """Output lists are Python float lists (JSON serializable)."""
        result = extract_smoothed_energy(
            sine_wave_440hz,
            sample_rate,
            hop_length=hop_length,
            frame_length=frame_length,
        )

        assert isinstance(result["raw"], list)
        assert isinstance(result["times_s"], list)
        if result["raw"]:
            assert isinstance(result["raw"][0], float)

    def test_silent_audio_produces_zero_energy(
        self,
        silence_audio: np.ndarray,
        sample_rate: int,
        hop_length: int,
        frame_length: int,
    ) -> None:
        """Silent audio produces near-zero energy."""
        result = extract_smoothed_energy(
            silence_audio,
            sample_rate,
            hop_length=hop_length,
            frame_length=frame_length,
        )

        # All normalized values should be 0 (since constant)
        assert all(v == 0.0 for v in result["raw"])


class TestFallbackSmoothing:
    """Tests for fallback smoothing when scipy is not available."""

    def test_fallback_smoothing_produces_valid_output(
        self,
        sine_wave_440hz: np.ndarray,
        sample_rate: int,
        hop_length: int,
        frame_length: int,
    ) -> None:
        """Test that fallback smoothing works correctly."""
        from unittest.mock import patch

        # Patch HAS_SCIPY to False to test fallback path
        with patch("blinkb0t.core.audio.energy.multiscale.HAS_SCIPY", False):
            # Need to reimport the module to get the patched version
            import importlib

            import blinkb0t.core.audio.energy.multiscale as multiscale_module

            importlib.reload(multiscale_module)

            result = multiscale_module.extract_smoothed_energy(
                sine_wave_440hz,
                sample_rate,
                hop_length=hop_length,
                frame_length=frame_length,
            )

            # Should still return valid structure
            assert "raw" in result
            assert "beat_level" in result
            assert "phrase_level" in result
            assert "section_level" in result

            # All should have same length
            assert len(result["raw"]) == len(result["beat_level"])
            assert len(result["raw"]) == len(result["phrase_level"])
            assert len(result["raw"]) == len(result["section_level"])

            # Reload with scipy available again
            importlib.reload(multiscale_module)

    def test_fallback_smoothing_with_short_array(
        self,
        sample_rate: int,
        hop_length: int,
        frame_length: int,
    ) -> None:
        """Fallback smoothing handles short arrays."""
        from unittest.mock import patch

        # Very short audio
        short_audio = np.random.rand(sample_rate).astype(np.float32)

        with patch("blinkb0t.core.audio.energy.multiscale.HAS_SCIPY", False):
            import importlib

            import blinkb0t.core.audio.energy.multiscale as multiscale_module

            importlib.reload(multiscale_module)

            result = multiscale_module.extract_smoothed_energy(
                short_audio,
                sample_rate,
                hop_length=hop_length,
                frame_length=frame_length,
            )

            # Should handle short audio
            assert "raw" in result
            assert len(result["raw"]) > 0

            importlib.reload(multiscale_module)
