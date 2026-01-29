"""Tests for lyrics pipeline orchestration (Phase 4).

Testing stage gating, confidence scoring, and sufficiency decisions.
"""

import pytest

from blinkb0t.core.audio.lyrics.pipeline import LyricsPipeline, LyricsPipelineConfig
from blinkb0t.core.audio.models import StageStatus
from blinkb0t.core.audio.models.lyrics import LyricsSourceKind


class TestLyricsPipeline:
    """Test lyrics pipeline orchestration."""

    @pytest.fixture
    def mock_providers(self):
        """Mock async provider clients."""
        from unittest.mock import AsyncMock

        return {
            "lrclib": AsyncMock(),
            "genius": AsyncMock(),
        }

    @pytest.fixture
    def config(self):
        """Default pipeline config."""
        return LyricsPipelineConfig(
            require_timed_words=False,
            min_coverage_pct=0.8,
        )

    async def test_embedded_success(self, mock_providers, config, tmp_path):
        """Pipeline returns embedded lyrics if found."""
        # Create audio file with embedded lyrics
        audio_file = tmp_path / "song.mp3"
        audio_file.touch()
        lrc_file = tmp_path / "song.lrc"
        lrc_file.write_text("[00:10.00]First line\n[00:15.00]Second line")

        pipeline = LyricsPipeline(config=config, providers=mock_providers)
        bundle = await pipeline.resolve(audio_path=str(audio_file), duration_ms=30000)

        assert bundle.stage_status == StageStatus.OK
        assert bundle.text == "First line\nSecond line"
        assert len(bundle.phrases) == 2
        assert bundle.source.kind == LyricsSourceKind.EMBEDDED

        # Should not call external providers
        mock_providers["lrclib"].search.assert_not_called()
        mock_providers["genius"].search.assert_not_called()

    async def test_synced_lookup_fallback(self, mock_providers, config, tmp_path):
        """Pipeline falls back to synced lookup if no embedded lyrics."""
        audio_file = tmp_path / "song.mp3"
        audio_file.touch()

        # Mock synced candidate from LRCLib
        from blinkb0t.core.audio.lyrics.providers.models import LyricsCandidate

        mock_providers["lrclib"].search.return_value = [
            LyricsCandidate(
                provider="lrclib",
                kind="SYNCED",
                text="Line 1\nLine 2",
                lrc="[00:10.00]Line 1\n[00:15.00]Line 2",
                confidence=0.9,
            ),
        ]

        pipeline = LyricsPipeline(config=config, providers=mock_providers)
        bundle = await pipeline.resolve(
            audio_path=str(audio_file),
            duration_ms=30000,
            artist="Artist",
            title="Title",
        )

        assert bundle.stage_status == StageStatus.OK
        assert bundle.text == "Line 1\nLine 2"
        assert len(bundle.phrases) == 2
        assert bundle.source.kind == LyricsSourceKind.LOOKUP_SYNCED

        # Should have called LRCLib but not Genius
        mock_providers["lrclib"].search.assert_called_once()
        mock_providers["genius"].search.assert_not_called()

    async def test_plain_lookup_fallback(self, mock_providers, config, tmp_path):
        """Pipeline falls back to plain lookup if no synced."""
        audio_file = tmp_path / "song.mp3"
        audio_file.touch()

        from blinkb0t.core.audio.lyrics.providers.models import LyricsCandidate

        # No synced results
        mock_providers["lrclib"].search.return_value = []

        # Plain result from Genius
        mock_providers["genius"].search.return_value = [
            LyricsCandidate(
                provider="genius",
                kind="PLAIN",
                text="Line 1\nLine 2\nLine 3",
                confidence=0.8,
            ),
        ]

        pipeline = LyricsPipeline(config=config, providers=mock_providers)
        bundle = await pipeline.resolve(
            audio_path=str(audio_file),
            duration_ms=30000,
            artist="Artist",
            title="Title",
        )

        assert bundle.stage_status == StageStatus.OK
        assert bundle.text == "Line 1\nLine 2\nLine 3"
        assert len(bundle.phrases) == 0  # No timing for plain
        assert bundle.source.kind == LyricsSourceKind.LOOKUP_PLAIN

        # Should have called both providers
        mock_providers["lrclib"].search.assert_called_once()
        mock_providers["genius"].search.assert_called_once()

    async def test_no_lyrics_found(self, mock_providers, config, tmp_path):
        """Pipeline returns NOT_AVAILABLE if no lyrics found."""
        audio_file = tmp_path / "song.mp3"
        audio_file.touch()

        # No results from any provider
        mock_providers["lrclib"].search.return_value = []
        mock_providers["genius"].search.return_value = []

        pipeline = LyricsPipeline(config=config, providers=mock_providers)
        bundle = await pipeline.resolve(
            audio_path=str(audio_file),
            duration_ms=30000,
            artist="Artist",
            title="Title",
        )

        assert bundle.stage_status == StageStatus.SKIPPED
        assert bundle.text is None
        assert len(bundle.phrases) == 0

    async def test_require_timed_words_insufficient(self, mock_providers, config, tmp_path):
        """Pipeline marks INSUFFICIENT if require_timed_words but only plain available."""
        audio_file = tmp_path / "song.mp3"
        audio_file.touch()

        from blinkb0t.core.audio.lyrics.providers.models import LyricsCandidate

        # Only plain lyrics available
        mock_providers["lrclib"].search.return_value = []
        mock_providers["genius"].search.return_value = [
            LyricsCandidate(
                provider="genius",
                kind="PLAIN",
                text="Line 1",
                confidence=0.8,
            ),
        ]

        config.require_timed_words = True
        pipeline = LyricsPipeline(config=config, providers=mock_providers)
        bundle = await pipeline.resolve(
            audio_path=str(audio_file),
            duration_ms=30000,
            artist="Artist",
            title="Title",
        )

        # Should return the plain lyrics with warning about insufficiency
        assert bundle.stage_status == StageStatus.OK
        assert bundle.text == "Line 1"
        assert len(bundle.phrases) == 0
        assert any("sufficiency" in w.lower() for w in bundle.warnings)

    async def test_confidence_adjustment(self, mock_providers, config, tmp_path):
        """Pipeline sets base confidence for embedded lyrics."""
        audio_file = tmp_path / "song.mp3"
        audio_file.touch()
        lrc_file = tmp_path / "song.lrc"

        # Create basic LRC file
        lrc_content = "[00:01.00]Line 1\n[00:02.00]Line 2\n[00:03.00]Line 3"
        lrc_file.write_text(lrc_content)

        pipeline = LyricsPipeline(config=config, providers=mock_providers)
        bundle = await pipeline.resolve(audio_path=str(audio_file), duration_ms=100000)

        assert bundle.stage_status == StageStatus.OK
        assert bundle.source is not None

        # Quality metrics require word-level timing, not phrase-level (LRC)
        # Phase 4 only has phrase-level from LRC, so quality is None
        assert bundle.quality is None

        # Base confidence for EMBEDDED should be 0.70
        assert bundle.source.confidence == 0.70

    async def test_best_candidate_selection(self, mock_providers, config, tmp_path):
        """Pipeline selects candidate with highest confidence."""
        audio_file = tmp_path / "song.mp3"
        audio_file.touch()

        from blinkb0t.core.audio.lyrics.providers.models import LyricsCandidate

        # Multiple synced candidates with different confidences
        mock_providers["lrclib"].search.return_value = [
            LyricsCandidate(
                provider="lrclib",
                kind="SYNCED",
                text="Low confidence",
                lrc="[00:10.00]Low confidence",
                confidence=0.5,
            ),
            LyricsCandidate(
                provider="lrclib",
                kind="SYNCED",
                text="High confidence",
                lrc="[00:10.00]High confidence",
                confidence=0.95,
            ),
        ]

        pipeline = LyricsPipeline(config=config, providers=mock_providers)
        bundle = await pipeline.resolve(
            audio_path=str(audio_file),
            duration_ms=30000,
            artist="Artist",
            title="Title",
        )

        # Should select high confidence candidate
        assert "High confidence" in bundle.text

    async def test_missing_metadata_skips_providers(self, mock_providers, config, tmp_path):
        """Pipeline skips providers if artist/title missing."""
        audio_file = tmp_path / "song.mp3"
        audio_file.touch()

        pipeline = LyricsPipeline(config=config, providers=mock_providers)
        bundle = await pipeline.resolve(
            audio_path=str(audio_file),
            duration_ms=30000,
            # No artist or title
        )

        assert bundle.stage_status == StageStatus.SKIPPED

        # Should not call providers without metadata
        mock_providers["lrclib"].search.assert_not_called()
        mock_providers["genius"].search.assert_not_called()

    async def test_provider_errors_graceful(self, mock_providers, config, tmp_path):
        """Pipeline handles provider errors gracefully."""
        audio_file = tmp_path / "song.mp3"
        audio_file.touch()

        # LRCLib raises error, Genius returns result
        from blinkb0t.core.audio.lyrics.providers.models import LyricsCandidate

        mock_providers["lrclib"].search.side_effect = Exception("API error")
        mock_providers["genius"].search.return_value = [
            LyricsCandidate(
                provider="genius",
                kind="PLAIN",
                text="Fallback lyrics",
                confidence=0.8,
            ),
        ]

        pipeline = LyricsPipeline(config=config, providers=mock_providers)
        bundle = await pipeline.resolve(
            audio_path=str(audio_file),
            duration_ms=30000,
            artist="Artist",
            title="Title",
        )

        # Should still succeed with Genius results
        assert bundle.stage_status == StageStatus.OK
        assert bundle.text == "Fallback lyrics"
        assert len(bundle.warnings) > 0  # Should have warning about LRCLib

    async def test_empty_providers_dict(self, config, tmp_path):
        """Pipeline works with no external providers."""
        audio_file = tmp_path / "song.mp3"
        audio_file.touch()
        lrc_file = tmp_path / "song.lrc"
        lrc_file.write_text("[00:10.00]Embedded line")

        pipeline = LyricsPipeline(config=config, providers={})
        bundle = await pipeline.resolve(audio_path=str(audio_file), duration_ms=30000)

        # Should still get embedded lyrics
        assert bundle.stage_status == StageStatus.OK
        assert "Embedded line" in bundle.text
