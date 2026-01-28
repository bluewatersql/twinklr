"""Unit tests for WhisperX service protocol and implementation.

Tests cover:
- WhisperXService protocol compliance
- Align operation (with reference lyrics)
- Transcribe operation (without reference lyrics)
- Mismatch ratio computation
- Error handling and edge cases
- Mock-based testing (no real WhisperX calls)
"""


import pytest

from blinkb0t.core.audio.lyrics.whisperx_models import (
    WhisperXAlignResult,
    WhisperXConfig,
    WhisperXTranscribeResult,
)
from blinkb0t.core.audio.lyrics.whisperx_service import (
    WhisperXImpl,
    WhisperXService,
    compute_mismatch_ratio,
)
from blinkb0t.core.audio.models.lyrics import LyricWord


class TestComputeMismatchRatio:
    """Test mismatch ratio computation using Levenshtein distance."""

    def test_identical_text(self):
        """Identical text should have 0.0 mismatch."""
        ratio = compute_mismatch_ratio("hello world", "hello world")
        assert ratio == 0.0

    def test_completely_different(self):
        """Completely different text should have 1.0 mismatch."""
        ratio = compute_mismatch_ratio("hello", "12345")
        assert ratio == 1.0

    def test_partial_match(self):
        """Partially matching text should have ratio between 0 and 1."""
        ratio = compute_mismatch_ratio("hello world", "hello earth")
        assert 0.0 < ratio < 1.0

    def test_case_insensitive(self):
        """Mismatch should be case-insensitive."""
        ratio = compute_mismatch_ratio("Hello World", "hello world")
        assert ratio == 0.0

    def test_whitespace_normalized(self):
        """Whitespace should be normalized."""
        ratio = compute_mismatch_ratio("hello  world", "hello world")
        assert ratio == 0.0

    def test_empty_strings(self):
        """Empty strings should match."""
        ratio = compute_mismatch_ratio("", "")
        assert ratio == 0.0

    def test_one_empty(self):
        """One empty string should be complete mismatch."""
        ratio = compute_mismatch_ratio("hello", "")
        assert ratio == 1.0

        ratio = compute_mismatch_ratio("", "world")
        assert ratio == 1.0

    def test_punctuation_ignored(self):
        """Punctuation should be ignored in comparison."""
        ratio = compute_mismatch_ratio("hello, world!", "hello world")
        assert ratio == 0.0


class MockWhisperXService(WhisperXService):
    """Mock implementation for testing protocol compliance."""

    def align(
        self, audio_path: str, lyrics_text: str, config: WhisperXConfig
    ) -> WhisperXAlignResult:
        """Mock align implementation."""
        words = [
            LyricWord(text="hello", start_ms=0, end_ms=500),
            LyricWord(text="world", start_ms=500, end_ms=1000),
        ]
        return WhisperXAlignResult(
            words=words, mismatch_ratio=0.0, metadata={"mock": True}
        )

    def transcribe(
        self, audio_path: str, config: WhisperXConfig
    ) -> WhisperXTranscribeResult:
        """Mock transcribe implementation."""
        words = [
            LyricWord(text="hello", start_ms=0, end_ms=500),
            LyricWord(text="world", start_ms=500, end_ms=1000),
        ]
        return WhisperXTranscribeResult(
            text="hello world", words=words, metadata={"mock": True}
        )


class TestWhisperXServiceProtocol:
    """Test that protocol is correctly defined."""

    def test_protocol_compliance(self):
        """Mock service should comply with protocol."""
        service: WhisperXService = MockWhisperXService()

        # Protocol requires these methods
        assert hasattr(service, "align")
        assert hasattr(service, "transcribe")
        assert callable(service.align)
        assert callable(service.transcribe)

    def test_align_signature(self):
        """Align should accept correct parameters."""
        service = MockWhisperXService()
        config = WhisperXConfig()

        result = service.align("/path/to/audio.mp3", "hello world", config)

        assert isinstance(result, WhisperXAlignResult)
        assert len(result.words) == 2

    def test_transcribe_signature(self):
        """Transcribe should accept correct parameters."""
        service = MockWhisperXService()
        config = WhisperXConfig()

        result = service.transcribe("/path/to/audio.mp3", config)

        assert isinstance(result, WhisperXTranscribeResult)
        assert result.text == "hello world"


class TestWhisperXImpl:
    """Test WhisperXImpl behavior (without real WhisperX calls)."""

    def test_align_raises_import_error_when_whisperx_not_installed(self):
        """Align should raise ImportError if whisperx not installed."""
        config = WhisperXConfig(device="cpu", model="base")
        service = WhisperXImpl()

        # If whisperx is not installed, should raise ImportError
        # We can't test the actual implementation without installing whisperx
        # So this test documents the expected behavior
        try:
            import whisperx  # type: ignore  # noqa: F401

            # If whisperx IS installed, skip this test
            pytest.skip("whisperx is installed, cannot test import error")
        except ImportError:
            # Expected: should raise ImportError with helpful message
            with pytest.raises(ImportError) as exc_info:
                service.align("/path/to/audio.mp3", "hello world", config)

            assert "whisperx" in str(exc_info.value).lower()
            assert "uv sync --extra ml" in str(exc_info.value)

    def test_transcribe_raises_import_error_when_whisperx_not_installed(self):
        """Transcribe should raise ImportError if whisperx not installed."""
        config = WhisperXConfig(device="cpu", model="base")
        service = WhisperXImpl()

        # If whisperx is not installed, should raise ImportError
        try:
            import whisperx  # type: ignore  # noqa: F401

            # If whisperx IS installed, skip this test
            pytest.skip("whisperx is installed, cannot test import error")
        except ImportError:
            # Expected: should raise ImportError with helpful message
            with pytest.raises(ImportError) as exc_info:
                service.transcribe("/path/to/audio.mp3", config)

            assert "whisperx" in str(exc_info.value).lower()
            assert "uv sync --extra ml" in str(exc_info.value)
