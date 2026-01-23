"""Tests for beat and rhythm detection."""

from __future__ import annotations

import numpy as np

from blinkb0t.core.audio.rhythm.beats import (
    compute_beats,
    detect_downbeats_phase_aligned,
    detect_time_signature,
)


class TestComputeBeats:
    """Tests for compute_beats function."""

    def test_returns_tempo_and_beat_frames(
        self,
        sample_onset_env: np.ndarray,
        sample_rate: int,
        hop_length: int,
    ) -> None:
        """Function returns a tempo and beat frames array."""
        tempo, beat_frames = compute_beats(
            onset_env=sample_onset_env,
            sr=sample_rate,
            hop_length=hop_length,
        )

        assert isinstance(tempo, float)
        assert isinstance(beat_frames, np.ndarray)
        assert tempo >= 0.0

    def test_tempo_in_reasonable_range(
        self,
        sample_onset_env: np.ndarray,
        sample_rate: int,
        hop_length: int,
    ) -> None:
        """Detected tempo is within reasonable BPM range."""
        tempo, _ = compute_beats(
            onset_env=sample_onset_env,
            sr=sample_rate,
            hop_length=hop_length,
        )

        # Librosa typically returns tempo in range 30-300 BPM
        assert 30 <= tempo <= 300 or tempo == 0.0

    def test_beat_frames_are_integers(
        self,
        sample_onset_env: np.ndarray,
        sample_rate: int,
        hop_length: int,
    ) -> None:
        """Beat frames should be integers."""
        _, beat_frames = compute_beats(
            onset_env=sample_onset_env,
            sr=sample_rate,
            hop_length=hop_length,
        )

        assert beat_frames.dtype == int or np.issubdtype(beat_frames.dtype, np.integer)

    def test_beat_frames_within_bounds(
        self,
        sample_onset_env: np.ndarray,
        sample_rate: int,
        hop_length: int,
    ) -> None:
        """Beat frames should be within onset_env length."""
        _, beat_frames = compute_beats(
            onset_env=sample_onset_env,
            sr=sample_rate,
            hop_length=hop_length,
        )

        if len(beat_frames) > 0:
            assert beat_frames.min() >= 0
            assert beat_frames.max() < len(sample_onset_env)

    def test_custom_start_bpm(
        self,
        sample_onset_env: np.ndarray,
        sample_rate: int,
        hop_length: int,
    ) -> None:
        """Start BPM parameter influences tempo detection."""
        # This tests the parameter is accepted; actual influence depends on librosa
        tempo, _ = compute_beats(
            onset_env=sample_onset_env,
            sr=sample_rate,
            hop_length=hop_length,
            start_bpm=90.0,
        )

        assert isinstance(tempo, float)

    def test_empty_onset_env(self, sample_rate: int, hop_length: int) -> None:
        """Empty onset envelope is handled."""
        empty_env = np.array([], dtype=np.float32)

        # Should not raise
        tempo, beat_frames = compute_beats(
            onset_env=empty_env,
            sr=sample_rate,
            hop_length=hop_length,
        )

        assert isinstance(tempo, float)
        assert isinstance(beat_frames, np.ndarray)


class TestDetectTimeSignature:
    """Tests for detect_time_signature function."""

    def test_returns_expected_structure(
        self,
        sample_beat_frames: np.ndarray,
        sample_onset_env: np.ndarray,
    ) -> None:
        """Function returns expected dictionary structure."""
        result = detect_time_signature(
            beat_frames=sample_beat_frames,
            onset_env=sample_onset_env,
        )

        assert "time_signature" in result
        assert "confidence" in result
        assert "method" in result

    def test_time_signature_is_valid(
        self,
        sample_beat_frames: np.ndarray,
        sample_onset_env: np.ndarray,
    ) -> None:
        """Detected time signature is one of expected values."""
        result = detect_time_signature(
            beat_frames=sample_beat_frames,
            onset_env=sample_onset_env,
        )

        valid_signatures = {"2/4", "3/4", "4/4", "6/8"}
        assert result["time_signature"] in valid_signatures

    def test_confidence_in_range(
        self,
        sample_beat_frames: np.ndarray,
        sample_onset_env: np.ndarray,
    ) -> None:
        """Confidence is in [0, 1] range."""
        result = detect_time_signature(
            beat_frames=sample_beat_frames,
            onset_env=sample_onset_env,
        )

        assert 0.0 <= result["confidence"] <= 1.0

    def test_few_beats_returns_default(
        self,
        sample_onset_env: np.ndarray,
    ) -> None:
        """Fewer than 8 beats returns default 4/4."""
        few_beats = np.array([10, 30, 50, 70], dtype=int)  # Only 4 beats

        result = detect_time_signature(
            beat_frames=few_beats,
            onset_env=sample_onset_env,
        )

        assert result["time_signature"] == "4/4"
        assert result["method"] == "default"

    def test_4_4_time_detection(self) -> None:
        """Test detection of 4/4 time signature with strong downbeats."""
        # Create an onset envelope with strong accents every 4 beats
        n_frames = 1000
        onset_env = np.zeros(n_frames, dtype=np.float32)

        # Beat frames every ~21 frames (120 BPM at sr=22050, hop=512)
        beat_frames = np.arange(10, 900, 21, dtype=int)

        # Make every 4th beat stronger (downbeat pattern)
        for i, bf in enumerate(beat_frames):
            if bf < n_frames:
                onset_env[bf] = 1.0 if i % 4 == 0 else 0.5

        result = detect_time_signature(
            beat_frames=beat_frames,
            onset_env=onset_env,
        )

        # 4/4 should be detected or at least have high score
        assert "all_scores" in result
        # 4/4 score should be competitive
        assert result["all_scores"]["4/4"] > 0.2

    def test_all_scores_included(
        self,
        sample_beat_frames: np.ndarray,
        sample_onset_env: np.ndarray,
    ) -> None:
        """All time signature scores are included when method is accent_pattern."""
        result = detect_time_signature(
            beat_frames=sample_beat_frames,
            onset_env=sample_onset_env,
        )

        if result["method"] == "accent_pattern":
            assert "all_scores" in result
            assert "2/4" in result["all_scores"]
            assert "3/4" in result["all_scores"]
            assert "4/4" in result["all_scores"]
            assert "6/8" in result["all_scores"]


class TestDetectDownbeatsPhaseAligned:
    """Tests for detect_downbeats_phase_aligned function."""

    def test_returns_expected_structure(
        self,
        sample_beat_frames: np.ndarray,
        sample_onset_env: np.ndarray,
        sample_chroma: np.ndarray,
        sample_rate: int,
        hop_length: int,
    ) -> None:
        """Function returns expected dictionary structure."""
        result = detect_downbeats_phase_aligned(
            beat_frames=sample_beat_frames,
            sr=sample_rate,
            hop_length=hop_length,
            onset_env=sample_onset_env,
            chroma_cqt=sample_chroma,
            beats_per_bar=4,
        )

        assert "downbeats" in result
        assert "phase" in result
        assert "phase_confidence" in result

    def test_downbeats_structure(
        self,
        sample_beat_frames: np.ndarray,
        sample_onset_env: np.ndarray,
        sample_chroma: np.ndarray,
        sample_rate: int,
        hop_length: int,
    ) -> None:
        """Each downbeat has required fields."""
        result = detect_downbeats_phase_aligned(
            beat_frames=sample_beat_frames,
            sr=sample_rate,
            hop_length=hop_length,
            onset_env=sample_onset_env,
            chroma_cqt=sample_chroma,
            beats_per_bar=4,
        )

        if result["downbeats"]:
            db = result["downbeats"][0]
            assert "beat_index" in db
            assert "time_s" in db
            assert "confidence" in db

    def test_phase_in_valid_range(
        self,
        sample_beat_frames: np.ndarray,
        sample_onset_env: np.ndarray,
        sample_chroma: np.ndarray,
        sample_rate: int,
        hop_length: int,
    ) -> None:
        """Phase offset is within beats_per_bar range."""
        beats_per_bar = 4
        result = detect_downbeats_phase_aligned(
            beat_frames=sample_beat_frames,
            sr=sample_rate,
            hop_length=hop_length,
            onset_env=sample_onset_env,
            chroma_cqt=sample_chroma,
            beats_per_bar=beats_per_bar,
        )

        assert 0 <= result["phase"] < beats_per_bar

    def test_phase_confidence_in_range(
        self,
        sample_beat_frames: np.ndarray,
        sample_onset_env: np.ndarray,
        sample_chroma: np.ndarray,
        sample_rate: int,
        hop_length: int,
    ) -> None:
        """Phase confidence is in [0, 1] range."""
        result = detect_downbeats_phase_aligned(
            beat_frames=sample_beat_frames,
            sr=sample_rate,
            hop_length=hop_length,
            onset_env=sample_onset_env,
            chroma_cqt=sample_chroma,
            beats_per_bar=4,
        )

        assert 0.0 <= result["phase_confidence"] <= 1.0

    def test_few_beats_returns_empty(
        self,
        sample_onset_env: np.ndarray,
        sample_chroma: np.ndarray,
        sample_rate: int,
        hop_length: int,
    ) -> None:
        """Fewer than 2*beats_per_bar returns empty downbeats."""
        few_beats = np.array([10, 30, 50], dtype=int)  # Only 3 beats

        result = detect_downbeats_phase_aligned(
            beat_frames=few_beats,
            sr=sample_rate,
            hop_length=hop_length,
            onset_env=sample_onset_env,
            chroma_cqt=sample_chroma,
            beats_per_bar=4,
        )

        assert result["downbeats"] == []
        assert result["phase_confidence"] == 0.0

    def test_downbeat_spacing(
        self,
        sample_beat_frames: np.ndarray,
        sample_onset_env: np.ndarray,
        sample_chroma: np.ndarray,
        sample_rate: int,
        hop_length: int,
    ) -> None:
        """Downbeats are spaced beats_per_bar apart."""
        beats_per_bar = 4
        result = detect_downbeats_phase_aligned(
            beat_frames=sample_beat_frames,
            sr=sample_rate,
            hop_length=hop_length,
            onset_env=sample_onset_env,
            chroma_cqt=sample_chroma,
            beats_per_bar=beats_per_bar,
        )

        downbeats = result["downbeats"]
        if len(downbeats) >= 2:
            # Check beat indices are spaced by beats_per_bar
            for i in range(1, len(downbeats)):
                diff = downbeats[i]["beat_index"] - downbeats[i - 1]["beat_index"]
                assert diff == beats_per_bar

    def test_invalid_beats_per_bar_handled(
        self,
        sample_beat_frames: np.ndarray,
        sample_onset_env: np.ndarray,
        sample_chroma: np.ndarray,
        sample_rate: int,
        hop_length: int,
    ) -> None:
        """Invalid beats_per_bar (< 2) is corrected to 4."""
        result = detect_downbeats_phase_aligned(
            beat_frames=sample_beat_frames,
            sr=sample_rate,
            hop_length=hop_length,
            onset_env=sample_onset_env,
            chroma_cqt=sample_chroma,
            beats_per_bar=1,  # Invalid, should be corrected to 4
        )

        # Should have processed without error
        assert isinstance(result["downbeats"], list)

    def test_low_phase_confidence_case(
        self,
        sample_rate: int,
        hop_length: int,
    ) -> None:
        """Test when phase scores are too low for confidence."""
        # Create uniform onset env - all phases will score similarly
        onset_env = np.ones(1000, dtype=np.float32) * 0.5
        beat_frames = np.arange(0, 900, 20, dtype=int)
        chroma = np.ones((12, 1000), dtype=np.float32) * 0.5

        result = detect_downbeats_phase_aligned(
            beat_frames=beat_frames,
            sr=sample_rate,
            hop_length=hop_length,
            onset_env=onset_env,
            chroma_cqt=chroma,
            beats_per_bar=4,
        )

        # Should return low or zero confidence when phases are similar
        assert result["phase_confidence"] >= 0.0
        assert result["phase_confidence"] <= 1.0


class TestDetectTempoChanges:
    """Tests for detect_tempo_changes function."""

    def test_returns_expected_structure(
        self,
        sine_wave_440hz: np.ndarray,
        sample_rate: int,
        hop_length: int,
    ) -> None:
        """Function returns expected dictionary structure."""
        from blinkb0t.core.audio.rhythm.beats import detect_tempo_changes

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
        sample_rate: int,
        hop_length: int,
    ) -> None:
        """Short audio (< 10s window) returns single tempo point."""
        from blinkb0t.core.audio.rhythm.beats import detect_tempo_changes

        # Create 5 second audio (shorter than 10s window)
        duration = 5.0
        t = np.linspace(0, duration, int(sample_rate * duration), dtype=np.float32)
        short_audio = np.sin(2 * np.pi * 440 * t).astype(np.float32)

        result = detect_tempo_changes(
            short_audio,
            sample_rate,
            hop_length=hop_length,
        )

        # Should have single tempo point
        assert len(result["tempo_curve"]) == 1
        assert result["tempo_changes"] == []
        assert result["is_stable"] is True

    def test_very_short_audio_fallback(
        self,
        sample_rate: int,
        hop_length: int,
    ) -> None:
        """Very short or silent audio uses fallback values."""
        from blinkb0t.core.audio.rhythm.beats import detect_tempo_changes

        # Create very short audio with some content (not silent)
        very_short = np.random.rand(int(sample_rate * 0.5)).astype(np.float32) * 0.5

        result = detect_tempo_changes(
            very_short,
            sample_rate,
            hop_length=hop_length,
        )

        # Should return valid structure with fallback
        assert "tempo_curve" in result
        assert isinstance(result["average_tempo_bpm"], float)
        # Tempo can be 0 for silent audio, or a valid value
        assert result["average_tempo_bpm"] >= 0

    def test_stable_tempo_detection(
        self,
        sample_rate: int,
        hop_length: int,
    ) -> None:
        """Stable tempo is correctly detected."""
        from blinkb0t.core.audio.rhythm.beats import detect_tempo_changes

        # Create click track with consistent tempo (120 BPM)
        duration = 15.0
        n_samples = int(sample_rate * duration)
        y = np.zeros(n_samples, dtype=np.float32)

        # Add clicks at 120 BPM (0.5s intervals)
        beat_interval_samples = int(0.5 * sample_rate)
        for i in range(0, n_samples, beat_interval_samples):
            end = min(i + int(0.01 * sample_rate), n_samples)
            y[i:end] = 0.8

        result = detect_tempo_changes(
            y,
            sample_rate,
            hop_length=hop_length,
        )

        # Should be stable
        assert result["tempo_std"] < 20.0  # Relatively stable

    def test_tempo_curve_structure(
        self,
        long_audio: np.ndarray,
        sample_rate: int,
        hop_length: int,
    ) -> None:
        """Tempo curve entries have correct structure."""
        from blinkb0t.core.audio.rhythm.beats import detect_tempo_changes

        result = detect_tempo_changes(
            long_audio,
            sample_rate,
            hop_length=hop_length,
        )

        if result["tempo_curve"]:
            entry = result["tempo_curve"][0]
            assert "time_s" in entry
            assert "tempo_bpm" in entry
            assert isinstance(entry["time_s"], float)
            assert isinstance(entry["tempo_bpm"], float)

    def test_tempo_changes_structure(
        self,
        sample_rate: int,
        hop_length: int,
    ) -> None:
        """Tempo changes have correct structure when detected."""
        from blinkb0t.core.audio.rhythm.beats import detect_tempo_changes

        # Create audio with tempo change
        duration = 20.0
        n_samples = int(sample_rate * duration)
        y = np.zeros(n_samples, dtype=np.float32)

        # First 10 seconds: 120 BPM
        for i in range(0, int(sample_rate * 10), int(0.5 * sample_rate)):
            end = min(i + int(0.01 * sample_rate), n_samples)
            y[i:end] = 0.8

        # Second 10 seconds: 180 BPM (much faster)
        for i in range(int(sample_rate * 10), n_samples, int(0.333 * sample_rate)):
            end = min(i + int(0.01 * sample_rate), n_samples)
            y[i:end] = 0.8

        result = detect_tempo_changes(
            y,
            sample_rate,
            hop_length=hop_length,
        )

        # If changes detected, check structure
        if result["tempo_changes"]:
            change = result["tempo_changes"][0]
            assert "time_s" in change
            assert "from_bpm" in change
            assert "to_bpm" in change
            assert "change_bpm" in change


class TestTimeSignatureEdgeCases:
    """Additional edge case tests for time signature detection."""

    def test_very_low_strength_beats(self) -> None:
        """Test with very low onset strength."""
        # Create onset envelope with very low values
        n_frames = 1000
        onset_env = np.full(n_frames, 0.001, dtype=np.float32)
        beat_frames = np.arange(10, 900, 20, dtype=int)

        result = detect_time_signature(
            beat_frames=beat_frames,
            onset_env=onset_env,
        )

        # Should handle gracefully
        assert "time_signature" in result
        assert result["time_signature"] in {"2/4", "3/4", "4/4", "6/8"}

    def test_insufficient_beats_for_grouping(self) -> None:
        """Test when beats are insufficient for proper grouping analysis."""
        n_frames = 200
        onset_env = np.random.rand(n_frames).astype(np.float32)
        beat_frames = np.array([10, 30, 50, 70, 90, 110, 130, 150, 170, 190], dtype=int)

        result = detect_time_signature(
            beat_frames=beat_frames,
            onset_env=onset_env,
        )

        # Should handle gracefully
        assert "time_signature" in result

    def test_uniform_onset_strengths(self) -> None:
        """Test with uniform onset strengths (no accent pattern)."""
        n_frames = 1000
        onset_env = np.ones(n_frames, dtype=np.float32)
        beat_frames = np.arange(10, 900, 20, dtype=int)

        result = detect_time_signature(
            beat_frames=beat_frames,
            onset_env=onset_env,
        )

        # Should default to 4/4 with low confidence
        assert result["time_signature"] == "4/4"
