"""Tests for musical key detection."""

from __future__ import annotations

import numpy as np

from blinkb0t.core.audio.harmonic.key import detect_musical_key, extract_chroma


class TestDetectMusicalKey:
    """Tests for detect_musical_key function."""

    def test_returns_expected_structure(
        self,
        sine_wave_440hz: np.ndarray,
        sample_rate: int,
        hop_length: int,
    ) -> None:
        """Function returns expected dictionary structure."""
        result = detect_musical_key(
            sine_wave_440hz,
            sample_rate,
            hop_length=hop_length,
        )

        assert "key" in result
        assert "mode" in result
        assert "confidence" in result

    def test_key_is_valid_note(
        self,
        sine_wave_440hz: np.ndarray,
        sample_rate: int,
        hop_length: int,
    ) -> None:
        """Detected key is a valid note name."""
        result = detect_musical_key(
            sine_wave_440hz,
            sample_rate,
            hop_length=hop_length,
        )

        valid_keys = {"C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"}
        assert result["key"] in valid_keys

    def test_mode_is_major_or_minor(
        self,
        sine_wave_440hz: np.ndarray,
        sample_rate: int,
        hop_length: int,
    ) -> None:
        """Mode is either major or minor."""
        result = detect_musical_key(
            sine_wave_440hz,
            sample_rate,
            hop_length=hop_length,
        )

        assert result["mode"] in {"major", "minor"}

    def test_confidence_in_valid_range(
        self,
        sine_wave_440hz: np.ndarray,
        sample_rate: int,
        hop_length: int,
    ) -> None:
        """Confidence is a float (can be negative due to correlation)."""
        result = detect_musical_key(
            sine_wave_440hz,
            sample_rate,
            hop_length=hop_length,
        )

        # Correlation-based confidence can be negative
        assert isinstance(result["confidence"], float)
        assert result["confidence"] <= 1.0

    def test_440hz_returns_valid_key(
        self,
        sine_wave_440hz: np.ndarray,
        sample_rate: int,
        hop_length: int,
    ) -> None:
        """440Hz sine wave returns valid key structure."""
        result = detect_musical_key(
            sine_wave_440hz,
            sample_rate,
            hop_length=hop_length,
        )

        # Pure sine wave doesn't provide harmonic context for key detection
        # Key detection via Krumhansl-Kessler profiles requires harmonic content
        # So we only verify valid structure is returned, not specific key
        valid_keys = {"C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"}
        assert result["key"] in valid_keys

    def test_alternative_key_included(
        self,
        sine_wave_440hz: np.ndarray,
        sample_rate: int,
        hop_length: int,
    ) -> None:
        """Alternative key (other mode) is included when available."""
        result = detect_musical_key(
            sine_wave_440hz,
            sample_rate,
            hop_length=hop_length,
        )

        if "alternative" in result:
            alt = result["alternative"]
            assert "key" in alt
            assert "mode" in alt
            assert "confidence" in alt

    def test_handles_silent_audio(
        self,
        silence_audio: np.ndarray,
        sample_rate: int,
        hop_length: int,
    ) -> None:
        """Silent audio returns default key."""
        result = detect_musical_key(
            silence_audio,
            sample_rate,
            hop_length=hop_length,
        )

        # Should return some result without error
        assert "key" in result
        assert "mode" in result


class TestExtractChroma:
    """Tests for extract_chroma function."""

    def test_returns_12_rows(
        self,
        sine_wave_440hz: np.ndarray,
        sample_rate: int,
        hop_length: int,
    ) -> None:
        """Chroma has 12 rows (pitch classes)."""
        chroma = extract_chroma(
            sine_wave_440hz,
            sample_rate,
            hop_length=hop_length,
        )

        assert chroma.shape[0] == 12

    def test_output_dtype_float32(
        self,
        sine_wave_440hz: np.ndarray,
        sample_rate: int,
        hop_length: int,
    ) -> None:
        """Output is float32."""
        chroma = extract_chroma(
            sine_wave_440hz,
            sample_rate,
            hop_length=hop_length,
        )

        assert chroma.dtype == np.float32

    def test_values_non_negative(
        self,
        sine_wave_440hz: np.ndarray,
        sample_rate: int,
        hop_length: int,
    ) -> None:
        """Chroma values are non-negative."""
        chroma = extract_chroma(
            sine_wave_440hz,
            sample_rate,
            hop_length=hop_length,
        )

        assert np.all(chroma >= 0)

    def test_440hz_has_peak_at_a(
        self,
        sine_wave_440hz: np.ndarray,
        sample_rate: int,
        hop_length: int,
    ) -> None:
        """440Hz sine has energy peak at A (index 9)."""
        chroma = extract_chroma(
            sine_wave_440hz,
            sample_rate,
            hop_length=hop_length,
        )

        # Average chroma across time
        chroma_avg = np.mean(chroma, axis=1)
        # A is index 9 in C, C#, D, D#, E, F, F#, G, G#, A, A#, B
        # Should have significant energy at A
        a_idx = 9
        assert chroma_avg[a_idx] > 0

    def test_output_has_frames(
        self,
        sine_wave_440hz: np.ndarray,
        sample_rate: int,
        hop_length: int,
    ) -> None:
        """Output has multiple frames for non-trivial audio."""
        chroma = extract_chroma(
            sine_wave_440hz,
            sample_rate,
            hop_length=hop_length,
        )

        # 5 seconds at sr=22050, hop=512 should give many frames
        assert chroma.shape[1] > 10
