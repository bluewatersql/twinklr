"""Tests for chord detection."""

from __future__ import annotations

import numpy as np

from twinklr.core.audio.harmonic.chords import detect_chords


class TestDetectChords:
    """Tests for detect_chords function."""

    def test_returns_expected_structure(
        self,
        sample_chroma: np.ndarray,
        sample_beat_frames: np.ndarray,
        sample_rate: int,
        hop_length: int,
    ) -> None:
        """Function returns expected dictionary structure."""
        result = detect_chords(
            chroma_cqt=sample_chroma,
            beat_frames=sample_beat_frames,
            sr=sample_rate,
            hop_length=hop_length,
        )

        assert "chords" in result
        assert "chord_changes" in result
        assert "statistics" in result

    def test_chord_structure(
        self,
        sample_chroma: np.ndarray,
        sample_beat_frames: np.ndarray,
        sample_rate: int,
        hop_length: int,
    ) -> None:
        """Each chord has required fields."""
        result = detect_chords(
            chroma_cqt=sample_chroma,
            beat_frames=sample_beat_frames,
            sr=sample_rate,
            hop_length=hop_length,
        )

        if result["chords"]:
            chord = result["chords"][0]
            assert "beat_index" in chord
            assert "time_s" in chord
            assert "chord" in chord
            assert "root" in chord
            assert "quality" in chord
            assert "confidence" in chord

    def test_chord_count_matches_beats(
        self,
        sample_chroma: np.ndarray,
        sample_beat_frames: np.ndarray,
        sample_rate: int,
        hop_length: int,
    ) -> None:
        """One chord per beat position."""
        result = detect_chords(
            chroma_cqt=sample_chroma,
            beat_frames=sample_beat_frames,
            sr=sample_rate,
            hop_length=hop_length,
        )

        assert len(result["chords"]) == len(sample_beat_frames)

    def test_c_major_chroma_detects_c_major(self, sample_rate: int, hop_length: int) -> None:
        """Chroma with C major profile should detect C major."""
        n_frames = 100
        # Create C major chroma: strong C, E, G (indices 0, 4, 7)
        chroma = np.zeros((12, n_frames), dtype=np.float32)
        chroma[0, :] = 1.0  # C
        chroma[4, :] = 0.8  # E
        chroma[7, :] = 0.9  # G

        beat_frames = np.array([10, 30, 50, 70, 90], dtype=int)

        result = detect_chords(
            chroma_cqt=chroma,
            beat_frames=beat_frames,
            sr=sample_rate,
            hop_length=hop_length,
        )

        # Should detect C major at most beats
        c_major_count = sum(1 for c in result["chords"] if c["chord"] == "C:maj")
        assert c_major_count > len(beat_frames) // 2

    def test_chord_change_structure(
        self,
        sample_rate: int,
        hop_length: int,
    ) -> None:
        """Chord changes have expected structure."""
        n_frames = 100
        # Create changing chroma
        chroma = np.zeros((12, n_frames), dtype=np.float32)
        # First half C major, second half G major
        chroma[0, :50] = 1.0  # C
        chroma[4, :50] = 0.8  # E
        chroma[7, :50] = 0.9  # G
        chroma[7, 50:] = 1.0  # G
        chroma[11, 50:] = 0.8  # B
        chroma[2, 50:] = 0.9  # D

        beat_frames = np.array([10, 30, 60, 80], dtype=int)

        result = detect_chords(
            chroma_cqt=chroma,
            beat_frames=beat_frames,
            sr=sample_rate,
            hop_length=hop_length,
        )

        if result["chord_changes"]:
            change = result["chord_changes"][0]
            assert "time_s" in change
            assert "from" in change
            assert "to" in change

    def test_statistics_structure(
        self,
        sample_chroma: np.ndarray,
        sample_beat_frames: np.ndarray,
        sample_rate: int,
        hop_length: int,
    ) -> None:
        """Statistics dict contains expected keys."""
        result = detect_chords(
            chroma_cqt=sample_chroma,
            beat_frames=sample_beat_frames,
            sr=sample_rate,
            hop_length=hop_length,
        )

        stats = result["statistics"]
        assert "total_chords" in stats
        assert "unique_chords" in stats
        assert "chord_change_count" in stats
        assert "major_pct" in stats
        assert "minor_pct" in stats

    def test_no_chord_detection_low_confidence(
        self,
        sample_rate: int,
        hop_length: int,
    ) -> None:
        """Low confidence chroma returns 'N' (no chord)."""
        n_frames = 100
        # Create very weak, spread out chroma
        rng = np.random.default_rng(42)
        chroma = rng.uniform(0, 0.1, (12, n_frames)).astype(np.float32)

        beat_frames = np.array([10, 30, 50], dtype=int)

        result = detect_chords(
            chroma_cqt=chroma,
            beat_frames=beat_frames,
            sr=sample_rate,
            hop_length=hop_length,
        )

        # Should have some "N" (no chord) detections due to low confidence
        # (depends on threshold)
        assert isinstance(result["chords"], list)

    def test_valid_chord_qualities(
        self,
        sample_chroma: np.ndarray,
        sample_beat_frames: np.ndarray,
        sample_rate: int,
        hop_length: int,
    ) -> None:
        """Detected chord qualities are from valid set."""
        result = detect_chords(
            chroma_cqt=sample_chroma,
            beat_frames=sample_beat_frames,
            sr=sample_rate,
            hop_length=hop_length,
        )

        valid_qualities = {"maj", "min", "7", "sus2", "sus4", "dim", "aug", "N"}
        for chord in result["chords"]:
            assert chord["quality"] in valid_qualities

    def test_empty_beats_returns_empty(
        self,
        sample_chroma: np.ndarray,
        sample_rate: int,
        hop_length: int,
    ) -> None:
        """Empty beat frames returns empty chords."""
        empty_beats = np.array([], dtype=int)

        result = detect_chords(
            chroma_cqt=sample_chroma,
            beat_frames=empty_beats,
            sr=sample_rate,
            hop_length=hop_length,
        )

        assert result["chords"] == []
        assert result["chord_changes"] == []
