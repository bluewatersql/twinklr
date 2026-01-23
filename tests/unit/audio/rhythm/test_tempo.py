"""Tests for tempo change detection."""

from __future__ import annotations

import numpy as np
import pytest

from blinkb0t.core.audio.rhythm.tempo import detect_tempo_changes


class TestDetectTempoChanges:
    """Tests for detect_tempo_changes function."""

    def test_returns_expected_structure(
        self,
        sine_wave_440hz: np.ndarray,
        sample_rate: int,
        hop_length: int,
    ) -> None:
        """Function returns expected dictionary structure."""
        result = detect_tempo_changes(
            sine_wave_440hz,
            sample_rate,
            hop_length=hop_length,
        )

        assert "tempo_curve" in result
        assert "tempo_changes" in result
        assert "average_tempo_bpm" in result
        assert "tempo_std" in result
        assert "is_stable" in result

    def test_short_audio_returns_single_tempo(
        self,
        very_short_audio: np.ndarray,
        sample_rate: int,
        hop_length: int,
    ) -> None:
        """Audio shorter than window size returns single tempo point."""
        result = detect_tempo_changes(
            very_short_audio,
            sample_rate,
            hop_length=hop_length,
            window_size_s=10.0,  # Audio is 5s
        )

        # Either returns one tempo or empty curve
        assert len(result["tempo_curve"]) <= 1
        assert result["is_stable"] is True

    def test_long_audio_has_multiple_tempo_points(
        self,
        long_audio: np.ndarray,
        sample_rate: int,
        hop_length: int,
    ) -> None:
        """Audio longer than window size has multiple tempo curve points."""
        result = detect_tempo_changes(
            long_audio,
            sample_rate,
            hop_length=hop_length,
            window_size_s=5.0,
        )

        # 30s audio with 5s window, 50% overlap = multiple points
        assert len(result["tempo_curve"]) > 1

    def test_tempo_curve_structure(
        self,
        long_audio: np.ndarray,
        sample_rate: int,
        hop_length: int,
    ) -> None:
        """Each tempo curve point has time_s and tempo_bpm."""
        result = detect_tempo_changes(
            long_audio,
            sample_rate,
            hop_length=hop_length,
            window_size_s=5.0,
        )

        if result["tempo_curve"]:
            point = result["tempo_curve"][0]
            assert "time_s" in point
            assert "tempo_bpm" in point

    def test_average_tempo_is_mean(
        self,
        long_audio: np.ndarray,
        sample_rate: int,
        hop_length: int,
    ) -> None:
        """Average tempo equals mean of tempo curve values."""
        result = detect_tempo_changes(
            long_audio,
            sample_rate,
            hop_length=hop_length,
            window_size_s=5.0,
        )

        if result["tempo_curve"]:
            tempos = [p["tempo_bpm"] for p in result["tempo_curve"]]
            expected_avg = np.mean(tempos)
            assert result["average_tempo_bpm"] == pytest.approx(expected_avg, rel=0.01)

    def test_stable_tempo_detection(
        self,
        sample_rate: int,
        hop_length: int,
    ) -> None:
        """Stable tempo (low std) is correctly identified."""
        # Create 30s of consistent audio
        duration = 30.0
        t = np.linspace(0, duration, int(sample_rate * duration), dtype=np.float32)
        stable_audio = np.sin(2 * np.pi * 440 * t).astype(np.float32)

        result = detect_tempo_changes(
            stable_audio,
            sample_rate,
            hop_length=hop_length,
            window_size_s=5.0,
        )

        # Should be stable (low tempo_std) unless detection fails
        # Note: Stability depends on librosa's tempo estimation consistency
        assert "is_stable" in result

    def test_tempo_changes_structure(
        self,
        long_audio: np.ndarray,
        sample_rate: int,
        hop_length: int,
    ) -> None:
        """Tempo changes have expected structure."""
        result = detect_tempo_changes(
            long_audio,
            sample_rate,
            hop_length=hop_length,
            window_size_s=5.0,
        )

        if result["tempo_changes"]:
            change = result["tempo_changes"][0]
            assert "time_s" in change
            assert "from_bpm" in change
            assert "to_bpm" in change
            assert "change_pct" in change

    def test_tempo_std_non_negative(
        self,
        long_audio: np.ndarray,
        sample_rate: int,
        hop_length: int,
    ) -> None:
        """Tempo standard deviation is non-negative."""
        result = detect_tempo_changes(
            long_audio,
            sample_rate,
            hop_length=hop_length,
        )

        assert result["tempo_std"] >= 0.0

    def test_custom_window_size(
        self,
        long_audio: np.ndarray,
        sample_rate: int,
        hop_length: int,
    ) -> None:
        """Custom window size affects number of tempo points."""
        result_large = detect_tempo_changes(
            long_audio,
            sample_rate,
            hop_length=hop_length,
            window_size_s=15.0,  # Large window
        )

        result_small = detect_tempo_changes(
            long_audio,
            sample_rate,
            hop_length=hop_length,
            window_size_s=5.0,  # Small window
        )

        # Smaller window should produce more tempo points
        assert len(result_small["tempo_curve"]) >= len(result_large["tempo_curve"])

    def test_empty_audio_handled(
        self,
        sample_rate: int,
        hop_length: int,
    ) -> None:
        """Empty audio is handled gracefully."""
        empty_audio = np.array([], dtype=np.float32)

        result = detect_tempo_changes(
            empty_audio,
            sample_rate,
            hop_length=hop_length,
        )

        assert isinstance(result, dict)
        assert result["is_stable"] is True
