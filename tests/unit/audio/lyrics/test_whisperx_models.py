"""Unit tests for WhisperX configuration and result models.

Tests cover:
- WhisperXConfig validation
- WhisperXAlignResult structure
- WhisperXTranscribeResult structure
- Field validation and defaults
"""

from pydantic import ValidationError
import pytest

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

    def test_device_validation(self):
        """Device must be cpu, cuda, or mps."""
        # Valid devices
        for device in ["cpu", "cuda", "mps"]:
            config = WhisperXConfig(device=device)
            assert config.device == device

        # Invalid device (should still accept but may fail at runtime)
        # Pydantic allows any string, validation happens at WhisperX level
        config = WhisperXConfig(device="invalid")
        assert config.device == "invalid"

    def test_model_validation(self):
        """Model must be one of the supported WhisperX models."""
        valid_models = ["tiny", "base", "small", "medium", "large"]
        for model in valid_models:
            config = WhisperXConfig(model=model)
            assert config.model == model

    def test_batch_size_validation(self):
        """Batch size must be positive."""
        # Valid batch sizes
        config = WhisperXConfig(batch_size=1)
        assert config.batch_size == 1

        config = WhisperXConfig(batch_size=64)
        assert config.batch_size == 64

        # Invalid batch size
        with pytest.raises(ValidationError) as exc_info:
            WhisperXConfig(batch_size=0)
        assert "greater than 0" in str(exc_info.value)

        with pytest.raises(ValidationError) as exc_info:
            WhisperXConfig(batch_size=-1)
        assert "greater than 0" in str(exc_info.value)

    def test_language_validation(self):
        """Language should accept ISO language codes or None."""
        # None (auto-detect)
        config = WhisperXConfig(language=None)
        assert config.language is None

        # ISO codes
        for lang in ["en", "es", "fr", "de", "ja", "zh"]:
            config = WhisperXConfig(language=lang)
            assert config.language == lang

    def test_extra_fields_forbidden(self):
        """Extra fields should be rejected."""
        with pytest.raises(ValidationError) as exc_info:
            WhisperXConfig(extra_field="value")  # type: ignore
        assert "Extra inputs are not permitted" in str(exc_info.value)


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

    def test_mismatch_ratio_range(self):
        """Mismatch ratio should be 0.0-1.0."""
        # Valid range
        result = WhisperXAlignResult(words=[], mismatch_ratio=0.0, metadata={})
        assert result.mismatch_ratio == 0.0

        result = WhisperXAlignResult(words=[], mismatch_ratio=1.0, metadata={})
        assert result.mismatch_ratio == 1.0

        result = WhisperXAlignResult(words=[], mismatch_ratio=0.5, metadata={})
        assert result.mismatch_ratio == 0.5

        # Out of range (should be caught by validation)
        with pytest.raises(ValidationError):
            WhisperXAlignResult(words=[], mismatch_ratio=-0.1, metadata={})

        with pytest.raises(ValidationError):
            WhisperXAlignResult(words=[], mismatch_ratio=1.1, metadata={})

    def test_extra_fields_forbidden(self):
        """Extra fields should be rejected."""
        with pytest.raises(ValidationError) as exc_info:
            WhisperXAlignResult(
                words=[],
                mismatch_ratio=0.0,
                metadata={},
                extra_field="value",  # type: ignore
            )
        assert "Extra inputs are not permitted" in str(exc_info.value)


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

    def test_metadata_optional(self):
        """Metadata is optional and defaults to empty dict."""
        result = WhisperXTranscribeResult(text="test", words=[])

        assert result.metadata == {}

    def test_extra_fields_forbidden(self):
        """Extra fields should be rejected."""
        with pytest.raises(ValidationError) as exc_info:
            WhisperXTranscribeResult(
                text="test",
                words=[],
                metadata={},
                extra_field="value",  # type: ignore
            )
        assert "Extra inputs are not permitted" in str(exc_info.value)
