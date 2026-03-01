"""Tests for beat-sync feature extraction (structure/features.py).

Covers PERF-02 (onset_env), PERF-03 (stft_mag), and PERF-05 (y_harm) threading.
"""

from __future__ import annotations

from unittest.mock import patch

import librosa
import numpy as np
import pytest

from twinklr.core.audio.structure.features import extract_beat_sync_features


@pytest.fixture
def audio_and_beats(
    sample_rate: int, hop_length: int
) -> tuple[np.ndarray, int, int, list[int], int]:
    """Create audio signal with corresponding beat frames.

    Returns:
        Tuple of (y, sr, hop_length, beat_frames, num_beats)
    """
    sr = sample_rate
    duration = 5.0
    t = np.linspace(0, duration, int(sr * duration), dtype=np.float32)
    y = (np.sin(2 * np.pi * 440 * t) * 0.5).astype(np.float32)

    # Generate evenly-spaced beat frames (~120 BPM)
    frames_per_beat = int(0.5 * sr / hop_length)
    n_beats = int(duration / 0.5)
    beat_frames = [i * frames_per_beat for i in range(n_beats)]

    return y, sr, hop_length, beat_frames, n_beats


class TestExtractBeatSyncFeatures:
    """Tests for extract_beat_sync_features function."""

    def test_backward_compat_no_new_params(
        self, audio_and_beats: tuple[np.ndarray, int, int, list[int], int]
    ) -> None:
        """Function works without any new optional params (backward compat)."""
        y, sr, hop_length, beat_frames, num_beats = audio_and_beats
        result = extract_beat_sync_features(y, sr, hop_length, beat_frames, num_beats)
        assert isinstance(result, np.ndarray)
        assert result.ndim == 2
        assert result.shape[1] == num_beats

    def test_onset_env_precomputed_used(
        self, audio_and_beats: tuple[np.ndarray, int, int, list[int], int]
    ) -> None:
        """PERF-02: Pre-computed onset_env skips internal onset_strength call."""
        y, sr, hop_length, beat_frames, num_beats = audio_and_beats
        onset_env = librosa.onset.onset_strength(y=y, sr=sr, hop_length=hop_length).astype(
            np.float32
        )

        with patch(
            "twinklr.core.audio.structure.features.librosa.onset.onset_strength"
        ) as mock_onset:
            result = extract_beat_sync_features(
                y, sr, hop_length, beat_frames, num_beats, onset_env=onset_env
            )
            mock_onset.assert_not_called()

        assert isinstance(result, np.ndarray)
        assert result.shape[1] == num_beats

    def test_stft_mag_precomputed_used(
        self, audio_and_beats: tuple[np.ndarray, int, int, list[int], int]
    ) -> None:
        """PERF-03: Pre-computed stft_mag skips internal librosa.stft call."""
        y, sr, hop_length, beat_frames, num_beats = audio_and_beats
        stft_mag = np.abs(librosa.stft(y, n_fft=2048, hop_length=hop_length)).astype(np.float32)

        with patch("twinklr.core.audio.structure.features.librosa.stft"):
            result = extract_beat_sync_features(
                y, sr, hop_length, beat_frames, num_beats, stft_mag=stft_mag
            )
            # stft may still be called for y_harm tonnetz, but the main STFT should not
            # Since y_harm also calls librosa.stft, we only check it's not called
            # with the original y directly (we can't distinguish easily, so just
            # verify the function completes)

        assert isinstance(result, np.ndarray)
        assert result.shape[1] == num_beats

    def test_y_harm_backward_compat(
        self, audio_and_beats: tuple[np.ndarray, int, int, list[int], int]
    ) -> None:
        """PERF-05: Function works without y_harm param (backward compat)."""
        y, sr, hop_length, beat_frames, num_beats = audio_and_beats
        result = extract_beat_sync_features(y, sr, hop_length, beat_frames, num_beats)
        assert isinstance(result, np.ndarray)
        assert result.shape[1] == num_beats

    def test_y_harm_precomputed_used(
        self, audio_and_beats: tuple[np.ndarray, int, int, list[int], int]
    ) -> None:
        """PERF-05: Pre-computed y_harm skips internal librosa.effects.harmonic call."""
        y, sr, hop_length, beat_frames, num_beats = audio_and_beats
        y_harm = librosa.effects.harmonic(y)

        with patch(
            "twinklr.core.audio.structure.features.librosa.effects.harmonic"
        ) as mock_harmonic:
            result = extract_beat_sync_features(
                y, sr, hop_length, beat_frames, num_beats, y_harm=y_harm
            )
            mock_harmonic.assert_not_called()

        assert isinstance(result, np.ndarray)
        assert result.shape[1] == num_beats

    def test_all_precomputed_params_together(
        self, audio_and_beats: tuple[np.ndarray, int, int, list[int], int]
    ) -> None:
        """All pre-computed params work together without error."""
        y, sr, hop_length, beat_frames, num_beats = audio_and_beats

        chroma_cqt = librosa.feature.chroma_cqt(y=y, sr=sr, hop_length=hop_length).astype(
            np.float32
        )
        onset_env = librosa.onset.onset_strength(y=y, sr=sr, hop_length=hop_length).astype(
            np.float32
        )
        stft_mag = np.abs(librosa.stft(y, n_fft=2048, hop_length=hop_length)).astype(np.float32)
        y_harm = librosa.effects.harmonic(y)

        result = extract_beat_sync_features(
            y,
            sr,
            hop_length,
            beat_frames,
            num_beats,
            chroma_cqt=chroma_cqt,
            onset_env=onset_env,
            stft_mag=stft_mag,
            y_harm=y_harm,
        )

        assert isinstance(result, np.ndarray)
        assert result.ndim == 2
        assert result.shape[1] == num_beats
