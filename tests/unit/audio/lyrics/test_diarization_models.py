"""Unit tests for diarization models (Phase 5 Milestone 3).

Tests cover:
- DiarizationConfig structure
- SpeakerSegment structure
- DiarizationResult structure
"""

from twinklr.core.audio.lyrics.diarization_models import (
    DiarizationConfig,
    DiarizationResult,
    SpeakerSegment,
)


class TestDiarizationConfig:
    """Test DiarizationConfig model."""

    def test_minimal_config(self):
        """Config with defaults should work."""
        config = DiarizationConfig()

        assert config.min_speakers is None  # Auto-detect
        assert config.max_speakers is None  # Auto-detect
        assert config.suggest_threshold == 0.85
        assert config.auto_enable_threshold == 0.90

    def test_custom_config(self):
        """Config with custom values should accept them."""
        config = DiarizationConfig(
            min_speakers=2,
            max_speakers=4,
            suggest_threshold=0.80,
            auto_enable_threshold=0.95,
        )

        assert config.min_speakers == 2
        assert config.max_speakers == 4
        assert config.suggest_threshold == 0.80
        assert config.auto_enable_threshold == 0.95


class TestSpeakerSegment:
    """Test SpeakerSegment model."""

    def test_valid_segment(self):
        """Valid speaker segment should work."""
        segment = SpeakerSegment(
            speaker="SPEAKER_01",
            start_ms=0,
            end_ms=5000,
            confidence=0.95,
        )

        assert segment.speaker == "SPEAKER_01"
        assert segment.start_ms == 0
        assert segment.end_ms == 5000
        assert segment.confidence == 0.95


class TestDiarizationResult:
    """Test DiarizationResult model."""

    def test_successful_diarization(self):
        """Diarization with speaker segments."""
        segments = [
            SpeakerSegment(speaker="SPEAKER_01", start_ms=0, end_ms=5000, confidence=0.95),
            SpeakerSegment(speaker="SPEAKER_02", start_ms=5000, end_ms=10000, confidence=0.92),
        ]

        result = DiarizationResult(
            segments=segments,
            num_speakers=2,
            metadata={"model": "pyannote", "device": "cpu"},
        )

        assert len(result.segments) == 2
        assert result.num_speakers == 2
        assert result.metadata["model"] == "pyannote"

    def test_empty_segments(self):
        """Diarization can have no segments (e.g., silent audio)."""
        result = DiarizationResult(
            segments=[],
            num_speakers=0,
            metadata={"warning": "no_speech_detected"},
        )

        assert len(result.segments) == 0
        assert result.num_speakers == 0
