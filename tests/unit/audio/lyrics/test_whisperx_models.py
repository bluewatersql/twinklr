"""Unit tests for WhisperX configuration and result models.

Tests cover:
- WhisperXConfig validation
- WhisperXAlignResult structure
- WhisperXTranscribeResult structure
- Field validation and defaults
"""

from twinklr.core.audio.lyrics.whisperx_models import (
    WhisperXAlignResult,
    WhisperXConfig,
    WhisperXTranscribeResult,
)
from twinklr.core.audio.models.lyrics import LyricWord


class TestWhisperXConfig:
    """Test WhisperXConfig model validation."""

    def test_minimal_config(self):
        """Config with only required fields should use defaults."""
        config = WhisperXConfig()

        assert config.device == "cpu"
        assert config.model == "base"
        assert config.batch_size == 16
        assert config.language is None
        assert config.return_char_alignments is False

    def test_custom_config(self):
        """Config with custom values should accept them."""
        config = WhisperXConfig(
            device="cuda",
            model="large",
            batch_size=32,
            language="en",
            return_char_alignments=True,
        )

        assert config.device == "cuda"
        assert config.model == "large"
        assert config.batch_size == 32
        assert config.language == "en"
        assert config.return_char_alignments is True


class TestWhisperXAlignResult:
    """Test WhisperXAlignResult model."""

    def test_successful_align(self):
        """Align result with words and no errors."""
        words = [
            LyricWord(text="hello", start_ms=0, end_ms=500),
            LyricWord(text="world", start_ms=500, end_ms=1000),
        ]

        result = WhisperXAlignResult(
            words=words,
            mismatch_ratio=0.1,
            metadata={"model": "base", "device": "cpu"},
        )

        assert len(result.words) == 2
        assert result.mismatch_ratio == 0.1
        assert result.metadata["model"] == "base"

    def test_align_with_high_mismatch(self):
        """Align result with high mismatch ratio."""
        words = [LyricWord(text="different", start_ms=0, end_ms=1000)]

        result = WhisperXAlignResult(
            words=words,
            mismatch_ratio=0.35,
            metadata={},
        )

        assert result.mismatch_ratio == 0.35
        assert result.mismatch_ratio > 0.25  # Above warning threshold

    def test_empty_words(self):
        """Align can produce empty words list if alignment fails."""
        result = WhisperXAlignResult(
            words=[],
            mismatch_ratio=1.0,
            metadata={"error": "alignment_failed"},
        )

        assert len(result.words) == 0
        assert result.mismatch_ratio == 1.0


class TestWhisperXTranscribeResult:
    """Test WhisperXTranscribeResult model."""

    def test_successful_transcribe(self):
        """Transcribe result with text and words."""
        words = [
            LyricWord(text="hello", start_ms=0, end_ms=500),
            LyricWord(text="world", start_ms=500, end_ms=1000),
        ]

        result = WhisperXTranscribeResult(
            text="hello world",
            words=words,
            metadata={"model": "base", "language": "en"},
        )

        assert result.text == "hello world"
        assert len(result.words) == 2
        assert result.metadata["language"] == "en"

    def test_empty_transcription(self):
        """Transcribe can produce empty result for silent audio."""
        result = WhisperXTranscribeResult(
            text="",
            words=[],
            metadata={"warning": "no_speech_detected"},
        )

        assert result.text == ""
        assert len(result.words) == 0

    def test_text_without_words(self):
        """Transcribe may have text but no word-level timing."""
        result = WhisperXTranscribeResult(
            text="some transcribed text",
            words=[],
            metadata={"note": "word_level_timing_disabled"},
        )

        assert result.text == "some transcribed text"
        assert len(result.words) == 0
