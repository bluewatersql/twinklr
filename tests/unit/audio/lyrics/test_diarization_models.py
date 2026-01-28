"""Unit tests for diarization models (Phase 5 Milestone 3).

Tests cover:
- DiarizationConfig validation
- SpeakerSegment structure
- DiarizationResult structure
- Field validation and defaults
"""

from pydantic import ValidationError
import pytest

from blinkb0t.core.audio.lyrics.diarization_models import (
    DiarizationConfig,
    DiarizationResult,
    SpeakerSegment,
)


class TestDiarizationConfig:
    """Test DiarizationConfig model validation."""

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

    def test_threshold_validation(self):
        """Thresholds must be 0-1."""
        # Valid
        config = DiarizationConfig(suggest_threshold=0.0, auto_enable_threshold=1.0)
        assert config.suggest_threshold == 0.0

        # Invalid
        with pytest.raises(ValidationError) as exc_info:
            DiarizationConfig(suggest_threshold=-0.1)
        assert "greater than or equal to 0" in str(exc_info.value)

        with pytest.raises(ValidationError) as exc_info:
            DiarizationConfig(auto_enable_threshold=1.1)
        assert "less than or equal to 1" in str(exc_info.value)

    def test_speaker_count_validation(self):
        """Speaker counts must be positive if provided."""
        # Valid
        config = DiarizationConfig(min_speakers=1, max_speakers=10)
        assert config.min_speakers == 1

        # Invalid min
        with pytest.raises(ValidationError) as exc_info:
            DiarizationConfig(min_speakers=0)
        assert "greater than 0" in str(exc_info.value)

        # Invalid max
        with pytest.raises(ValidationError) as exc_info:
            DiarizationConfig(max_speakers=0)
        assert "greater than 0" in str(exc_info.value)

    def test_extra_fields_forbidden(self):
        """Extra fields should be rejected."""
        with pytest.raises(ValidationError) as exc_info:
            DiarizationConfig(extra_field="value")  # type: ignore
        assert "Extra inputs are not permitted" in str(exc_info.value)


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

    def test_timing_validation(self):
        """Start/end times must be non-negative."""
        # Valid
        segment = SpeakerSegment(speaker="SPEAKER_01", start_ms=0, end_ms=1000)
        assert segment.start_ms == 0

        # Invalid start
        with pytest.raises(ValidationError) as exc_info:
            SpeakerSegment(speaker="SPEAKER_01", start_ms=-100, end_ms=1000)
        assert "greater than or equal to 0" in str(exc_info.value)

        # Invalid end
        with pytest.raises(ValidationError) as exc_info:
            SpeakerSegment(speaker="SPEAKER_01", start_ms=0, end_ms=-1)
        assert "greater than or equal to 0" in str(exc_info.value)

    def test_confidence_validation(self):
        """Confidence must be 0-1."""
        # Valid
        segment = SpeakerSegment(speaker="SPEAKER_01", start_ms=0, end_ms=1000, confidence=0.5)
        assert segment.confidence == 0.5

        # Invalid
        with pytest.raises(ValidationError) as exc_info:
            SpeakerSegment(speaker="SPEAKER_01", start_ms=0, end_ms=1000, confidence=1.1)
        assert "less than or equal to 1" in str(exc_info.value)

    def test_extra_fields_forbidden(self):
        """Extra fields should be rejected."""
        with pytest.raises(ValidationError) as exc_info:
            SpeakerSegment(
                speaker="SPEAKER_01",
                start_ms=0,
                end_ms=1000,
                extra_field="value",  # type: ignore
            )
        assert "Extra inputs are not permitted" in str(exc_info.value)


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

    def test_metadata_optional(self):
        """Metadata defaults to empty dict."""
        result = DiarizationResult(segments=[], num_speakers=0)

        assert result.metadata == {}

    def test_num_speakers_validation(self):
        """Number of speakers must be non-negative."""
        # Valid
        result = DiarizationResult(segments=[], num_speakers=0)
        assert result.num_speakers == 0

        # Invalid
        with pytest.raises(ValidationError) as exc_info:
            DiarizationResult(segments=[], num_speakers=-1)
        assert "greater than or equal to 0" in str(exc_info.value)

    def test_extra_fields_forbidden(self):
        """Extra fields should be rejected."""
        with pytest.raises(ValidationError) as exc_info:
            DiarizationResult(
                segments=[],
                num_speakers=0,
                extra_field="value",  # type: ignore
            )
        assert "Extra inputs are not permitted" in str(exc_info.value)
