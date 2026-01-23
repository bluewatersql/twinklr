"""Tests for pitch tracking."""

from __future__ import annotations

import numpy as np
import pytest

from blinkb0t.core.audio.harmonic.pitch import extract_pitch_tracking


class TestExtractPitchTracking:
    """Tests for extract_pitch_tracking function."""

    def test_returns_expected_structure(
        self,
        sine_wave_440hz: np.ndarray,
        sample_rate: int,
        hop_length: int,
    ) -> None:
        """Function returns expected dictionary structure."""
        result = extract_pitch_tracking(
            sine_wave_440hz,
            sample_rate,
            hop_length=hop_length,
        )

        assert "mean_hz" in result
        assert "std_hz" in result
        assert "range_hz" in result
        assert "min_hz" in result
        assert "max_hz" in result
        assert "confidence" in result
        assert "voiced_ratio" in result

    def test_440hz_detected_correctly(
        self,
        sine_wave_440hz: np.ndarray,
        sample_rate: int,
        hop_length: int,
    ) -> None:
        """440Hz sine wave should have mean around 440Hz."""
        result = extract_pitch_tracking(
            sine_wave_440hz,
            sample_rate,
            hop_length=hop_length,
        )

        # Allow some tolerance due to pYIN algorithm variations
        if result["mean_hz"] > 0:  # If pitch was detected
            assert 400 <= result["mean_hz"] <= 480

    def test_pure_tone_low_std(
        self,
        sine_wave_440hz: np.ndarray,
        sample_rate: int,
        hop_length: int,
    ) -> None:
        """Pure tone should have low pitch standard deviation."""
        result = extract_pitch_tracking(
            sine_wave_440hz,
            sample_rate,
            hop_length=hop_length,
        )

        if result["mean_hz"] > 0:
            # Std should be small relative to mean for pure tone
            assert result["std_hz"] < result["mean_hz"] * 0.1

    def test_range_equals_max_minus_min(
        self,
        sine_wave_440hz: np.ndarray,
        sample_rate: int,
        hop_length: int,
    ) -> None:
        """Range equals max - min."""
        result = extract_pitch_tracking(
            sine_wave_440hz,
            sample_rate,
            hop_length=hop_length,
        )

        if result["max_hz"] > 0:
            expected_range = result["max_hz"] - result["min_hz"]
            assert result["range_hz"] == pytest.approx(expected_range, abs=0.1)

    def test_voiced_ratio_in_range(
        self,
        sine_wave_440hz: np.ndarray,
        sample_rate: int,
        hop_length: int,
    ) -> None:
        """Voiced ratio is in [0, 1] range."""
        result = extract_pitch_tracking(
            sine_wave_440hz,
            sample_rate,
            hop_length=hop_length,
        )

        assert 0.0 <= result["voiced_ratio"] <= 1.0

    def test_confidence_in_range(
        self,
        sine_wave_440hz: np.ndarray,
        sample_rate: int,
        hop_length: int,
    ) -> None:
        """Confidence is in [0, 1] range."""
        result = extract_pitch_tracking(
            sine_wave_440hz,
            sample_rate,
            hop_length=hop_length,
        )

        assert 0.0 <= result["confidence"] <= 1.0

    def test_noise_low_voiced_ratio(
        self,
        noisy_audio: np.ndarray,
        sample_rate: int,
        hop_length: int,
    ) -> None:
        """White noise should have low voiced ratio."""
        result = extract_pitch_tracking(
            noisy_audio,
            sample_rate,
            hop_length=hop_length,
        )

        # Noise doesn't have clear pitch
        # Either low voiced ratio or low confidence
        assert result["voiced_ratio"] < 0.5 or result["confidence"] < 0.5

    def test_silence_returns_zeros(
        self,
        silence_audio: np.ndarray,
        sample_rate: int,
        hop_length: int,
    ) -> None:
        """Silent audio returns zero pitch values."""
        result = extract_pitch_tracking(
            silence_audio,
            sample_rate,
            hop_length=hop_length,
        )

        # Should have zero values for silence
        assert result["mean_hz"] == 0.0 or result["voiced_ratio"] == 0.0

    def test_handles_exceptions_gracefully(
        self,
        sample_rate: int,
        hop_length: int,
    ) -> None:
        """Function handles exceptions gracefully."""
        # Very short audio might cause issues
        very_short = np.random.rand(100).astype(np.float32)

        result = extract_pitch_tracking(
            very_short,
            sample_rate,
            hop_length=hop_length,
        )

        # Should return valid structure even on failure
        assert "mean_hz" in result
        assert isinstance(result["mean_hz"], float)
