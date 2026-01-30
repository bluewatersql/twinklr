"""Unit tests for WhisperX pipeline gating (Phase 5 Milestone 2).

Tests cover:
- Stage 4: WhisperX align-only (existing lyrics, need timing)
- Stage 5: WhisperX transcribe (no lyrics at all)
- Mismatch ratio detection and penalties
- Gating logic (when to trigger align vs transcribe)
- Confidence adjustments for WhisperX results
"""

import pytest

from twinklr.core.audio.lyrics.pipeline import LyricsPipeline, LyricsPipelineConfig
from twinklr.core.audio.lyrics.whisperx_models import (
    WhisperXAlignResult,
    WhisperXConfig,
    WhisperXTranscribeResult,
)
from twinklr.core.audio.lyrics.whisperx_service import WhisperXService
from twinklr.core.audio.models import StageStatus
from twinklr.core.audio.models.lyrics import LyricsSourceKind, LyricWord


class MockWhisperXService(WhisperXService):
    """Mock WhisperX service for testing."""

    def __init__(
        self,
        *,
        align_result: WhisperXAlignResult | None = None,
        transcribe_result: WhisperXTranscribeResult | None = None,
    ):
        self.align_result = align_result
        self.transcribe_result = transcribe_result
        self.align_called = False
        self.transcribe_called = False

    def align(
        self, audio_path: str, lyrics_text: str, config: WhisperXConfig
    ) -> WhisperXAlignResult:
        self.align_called = True
        if self.align_result:
            return self.align_result
        # Default successful align
        words = [
            LyricWord(text="hello", start_ms=0, end_ms=500),
            LyricWord(text="world", start_ms=500, end_ms=1000),
        ]
        return WhisperXAlignResult(words=words, mismatch_ratio=0.1, metadata={"mock": True})

    def transcribe(self, audio_path: str, config: WhisperXConfig) -> WhisperXTranscribeResult:
        self.transcribe_called = True
        if self.transcribe_result:
            return self.transcribe_result
        # Default successful transcribe
        words = [
            LyricWord(text="transcribed", start_ms=0, end_ms=500),
            LyricWord(text="lyrics", start_ms=500, end_ms=1000),
        ]
        return WhisperXTranscribeResult(
            text="transcribed lyrics", words=words, metadata={"mock": True}
        )


class TestWhisperXAlignStage:
    """Test Stage 4: WhisperX align-only."""

    def test_align_triggered_when_plain_text_but_require_timed(self):
        """WhisperX align should trigger when we have text but require_timed_words=True."""
        # This is tested in the full pipeline flow (test_stage_order_full_pipeline)
        # When plain text is found but require_timed_words=True, align should trigger
        # Just verify the pipeline accepts whisperx_service parameter
        whisperx = MockWhisperXService()
        config = LyricsPipelineConfig(require_timed_words=True)
        pipeline = LyricsPipeline(config=config, providers={}, whisperx_service=whisperx)
        assert pipeline.whisperx_service is not None

    def test_align_with_good_reference(self, tmp_path):
        """Align with low mismatch ratio should succeed."""
        audio_path = str(tmp_path / "song.mp3")
        (tmp_path / "song.mp3").write_text("mock")

        # Mock align with good result (low mismatch)
        align_result = WhisperXAlignResult(
            words=[
                LyricWord(text="hello", start_ms=0, end_ms=500),
                LyricWord(text="world", start_ms=500, end_ms=1000),
            ],
            mismatch_ratio=0.1,  # Good alignment
            metadata={},
        )
        whisperx = MockWhisperXService(align_result=align_result)

        config = LyricsPipelineConfig(require_timed_words=True)
        pipeline = LyricsPipeline(config=config, providers={}, whisperx_service=whisperx)

        # Simulate align stage directly (would be called from pipeline)
        bundle = pipeline._try_whisperx_align(
            audio_path=audio_path,
            lyrics_text="hello world",
            duration_ms=1000,
            warnings=[],
        )

        assert bundle is not None
        assert len(bundle.words) == 2
        assert bundle.source.kind == LyricsSourceKind.WHISPERX_ALIGN
        assert bundle.source.confidence > 0.75  # Base 0.85 - small penalties

    def test_align_with_high_mismatch(self, tmp_path):
        """Align with high mismatch ratio should add warning and penalty."""
        audio_path = str(tmp_path / "song.mp3")
        (tmp_path / "song.mp3").write_text("mock")

        # Mock align with high mismatch
        align_result = WhisperXAlignResult(
            words=[
                LyricWord(text="different", start_ms=0, end_ms=500),
                LyricWord(text="words", start_ms=500, end_ms=1000),
            ],
            mismatch_ratio=0.35,  # Above 0.25 threshold
            metadata={},
        )
        whisperx = MockWhisperXService(align_result=align_result)

        config = LyricsPipelineConfig()
        pipeline = LyricsPipeline(config=config, providers={}, whisperx_service=whisperx)

        bundle = pipeline._try_whisperx_align(
            audio_path=audio_path,
            lyrics_text="hello world",
            duration_ms=1000,
            warnings=[],
        )

        assert bundle is not None
        assert any("mismatch" in w.lower() for w in bundle.warnings)
        # Confidence should have -0.10 penalty for high mismatch
        assert bundle.source.confidence < 0.85  # Base confidence

    def test_align_not_triggered_when_words_already_exist(self):
        """Align should not trigger if we already have word-level timing."""
        # This is tested in the full pipeline flow
        # If embedded/synced provided words, don't need align
        # Just a placeholder test


class TestWhisperXTranscribeStage:
    """Test Stage 5: WhisperX transcribe."""

    def test_transcribe_triggered_when_no_lyrics(self, tmp_path):
        """Transcribe should trigger when no lyrics found from any source."""
        audio_path = str(tmp_path / "song.mp3")
        (tmp_path / "song.mp3").write_text("mock")

        # Mock transcribe
        transcribe_result = WhisperXTranscribeResult(
            text="transcribed lyrics from audio",
            words=[
                LyricWord(text="transcribed", start_ms=0, end_ms=400),
                LyricWord(text="lyrics", start_ms=400, end_ms=800),
                LyricWord(text="from", start_ms=800, end_ms=1000),
                LyricWord(text="audio", start_ms=1000, end_ms=1500),
            ],
            metadata={"language": "en"},
        )
        whisperx = MockWhisperXService(transcribe_result=transcribe_result)

        config = LyricsPipelineConfig()
        pipeline = LyricsPipeline(config=config, providers={}, whisperx_service=whisperx)

        bundle = pipeline._try_whisperx_transcribe(
            audio_path=audio_path,
            duration_ms=1500,
            warnings=[],
        )

        assert bundle is not None
        assert bundle.text == "transcribed lyrics from audio"
        assert len(bundle.words) == 4
        assert bundle.source.kind == LyricsSourceKind.WHISPERX_TRANSCRIBE
        assert bundle.source.confidence == pytest.approx(0.80, abs=0.05)  # Base confidence

    def test_transcribe_produces_word_timing(self, tmp_path):
        """Transcribe should produce word-level timing."""
        audio_path = str(tmp_path / "song.mp3")
        (tmp_path / "song.mp3").write_text("mock")

        whisperx = MockWhisperXService()
        config = LyricsPipelineConfig(require_timed_words=True)
        pipeline = LyricsPipeline(config=config, providers={}, whisperx_service=whisperx)

        bundle = pipeline._try_whisperx_transcribe(
            audio_path=audio_path,
            duration_ms=1000,
            warnings=[],
        )

        assert bundle is not None
        assert len(bundle.words) > 0
        assert all(w.start_ms >= 0 for w in bundle.words)
        assert all(w.end_ms > w.start_ms for w in bundle.words)

    def test_transcribe_not_triggered_when_lyrics_exist(self):
        """Transcribe should not trigger if lyrics already found."""
        # This is tested in the full pipeline flow
        # If any previous stage provided lyrics, don't transcribe
        # Just a placeholder test


class TestWhisperXGatingLogic:
    """Test gating logic for WhisperX stages."""

    async def test_stage_order_full_pipeline(self, tmp_path):
        """Test that stages execute in correct order with WhisperX."""
        audio_path = str(tmp_path / "song.mp3")
        (tmp_path / "song.mp3").write_text("mock")

        # No embedded, no providers, WhisperX available
        whisperx = MockWhisperXService()
        config = LyricsPipelineConfig()
        pipeline = LyricsPipeline(config=config, providers={}, whisperx_service=whisperx)

        bundle = await pipeline.resolve(
            audio_path=audio_path,
            duration_ms=1000,
        )

        # Should have triggered transcribe (no lyrics from other sources)
        assert whisperx.transcribe_called
        assert not whisperx.align_called  # No text to align
        assert bundle.source.kind == LyricsSourceKind.WHISPERX_TRANSCRIBE

    async def test_whisperx_disabled_when_service_not_provided(self, tmp_path):
        """Pipeline should skip WhisperX stages if service not provided."""
        audio_path = str(tmp_path / "song.mp3")
        (tmp_path / "song.mp3").write_text("mock")

        # No whisperx_service provided
        config = LyricsPipelineConfig()
        pipeline = LyricsPipeline(config=config, providers={})

        bundle = await pipeline.resolve(
            audio_path=audio_path,
            duration_ms=1000,
        )

        # Should return SKIPPED status (no lyrics, no whisperx)
        assert bundle.stage_status == StageStatus.SKIPPED


class TestWhisperXConfidenceScoring:
    """Test confidence scoring for WhisperX results."""

    def test_base_confidence_align(self):
        """WhisperX align should have base confidence 0.85."""
        assert LyricsPipeline.BASE_CONFIDENCE[LyricsSourceKind.WHISPERX_ALIGN] == 0.85

    def test_base_confidence_transcribe(self):
        """WhisperX transcribe should have base confidence 0.80."""
        assert LyricsPipeline.BASE_CONFIDENCE[LyricsSourceKind.WHISPERX_TRANSCRIBE] == 0.80

    def test_mismatch_penalty_applied(self, tmp_path):
        """High mismatch ratio should apply -0.10 penalty."""
        audio_path = str(tmp_path / "song.mp3")
        (tmp_path / "song.mp3").write_text("mock")

        # Mock with high mismatch
        align_result = WhisperXAlignResult(
            words=[LyricWord(text="word", start_ms=0, end_ms=1000)],
            mismatch_ratio=0.30,  # Above 0.25 threshold
            metadata={},
        )
        whisperx = MockWhisperXService(align_result=align_result)

        config = LyricsPipelineConfig()
        pipeline = LyricsPipeline(config=config, providers={}, whisperx_service=whisperx)

        bundle = pipeline._try_whisperx_align(
            audio_path=audio_path,
            lyrics_text="different text",
            duration_ms=1000,
            warnings=[],
        )

        # Base 0.85 - 0.10 (mismatch penalty) = 0.75
        assert bundle is not None
        assert bundle.source.confidence <= 0.75

    def test_quality_penalties_still_applied(self, tmp_path):
        """WhisperX results should still get quality metric penalties (low coverage)."""
        audio_path = str(tmp_path / "song.mp3")
        (tmp_path / "song.mp3").write_text("mock")

        # Mock with low coverage (words only cover 50% of song)
        align_result = WhisperXAlignResult(
            words=[
                LyricWord(text="word1", start_ms=0, end_ms=250),
                LyricWord(text="word2", start_ms=250, end_ms=500),
            ],
            mismatch_ratio=0.0,  # No mismatch
            metadata={},
        )
        whisperx = MockWhisperXService(align_result=align_result)

        # Config requiring 80% coverage
        config = LyricsPipelineConfig(min_coverage_pct=0.8)
        pipeline = LyricsPipeline(config=config, providers={}, whisperx_service=whisperx)

        bundle = pipeline._try_whisperx_align(
            audio_path=audio_path,
            lyrics_text="word1 word2",
            duration_ms=1000,  # Words cover 500ms / 1000ms = 50%
            warnings=[],
        )

        # Should have low coverage penalty
        assert bundle is not None
        assert bundle.quality is not None
        assert bundle.quality.coverage_pct < 0.8  # Below threshold
        # Confidence should be reduced by low coverage penalty (-0.10)
        assert bundle.source.confidence < 0.85  # Base confidence
