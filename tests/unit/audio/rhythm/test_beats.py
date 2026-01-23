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
