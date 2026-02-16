"""Unit tests for audio analysis pipeline stage."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from twinklr.core.agents.audio.stages.analysis import AudioAnalysisStage
from twinklr.core.agents.logging import NullLLMCallLogger
from twinklr.core.agents.providers.base import LLMProvider
from twinklr.core.audio.models.enums import StageStatus
from twinklr.core.audio.models.lyrics import LyricsBundle, LyricWord
from twinklr.core.caching.backends.null import NullCache
from twinklr.core.config.models import AppConfig, JobConfig
from twinklr.core.pipeline.context import PipelineContext


class MockProvider(LLMProvider):
    """Mock LLM provider."""

    async def generate_json_async(self, *args, **kwargs):
        return {}


@pytest.fixture
def mock_context():
    """Create mock pipeline context with mocked session."""
    app_config = AppConfig.model_validate(
        {
            "cache": {"base_dir": "cache", "enabled": False},
            "logging": {"level": "INFO", "format": "json"},
        }
    )
    job_config = JobConfig.model_validate(
        {
            "agent": {
                "max_iterations": 3,
                "plan_agent": {"model": "gpt-5.2"},
                "validate_agent": {"model": "gpt-5.2"},
                "judge_agent": {"model": "gpt-5.2"},
                "llm_logging": {"enabled": False},
            }
        }
    )

    # Create a mock session with required properties
    mock_session = MagicMock()
    mock_session.app_config = app_config
    mock_session.job_config = job_config
    mock_session.session_id = "test_session_123"
    mock_session.llm_provider = MockProvider()
    mock_session.agent_cache = NullCache()
    mock_session.llm_logger = NullLLMCallLogger()

    return PipelineContext(session=mock_session)


@pytest.mark.asyncio
async def test_audio_analysis_stage_name():
    """Test stage name property."""
    stage = AudioAnalysisStage()
    assert stage.name == "audio_analysis"


@pytest.mark.asyncio
async def test_audio_analysis_failure(mock_context):
    """Test audio analysis failure handling."""
    with patch("twinklr.core.audio.analyzer.AudioAnalyzer") as mock_analyzer_cls:
        # Setup mock to raise exception
        mock_analyzer = AsyncMock()
        mock_analyzer.analyze.side_effect = RuntimeError("File not found")
        mock_analyzer_cls.return_value = mock_analyzer

        stage = AudioAnalysisStage()
        result = await stage.execute("/invalid/path.mp3", mock_context)

        assert result.success is False
        assert "File not found" in result.error
        assert result.stage_name == "audio_analysis"


@pytest.mark.asyncio
async def test_audio_analysis_fails_for_non_meaningful_features(mock_context):
    """Stage fails when analysis does not produce meaningful timing features."""
    with patch("twinklr.core.audio.analyzer.AudioAnalyzer") as mock_analyzer_cls:
        mock_analyzer = AsyncMock()
        mock_analyzer.analyze.return_value = SimpleNamespace(
            features={"tempo_bpm": 0.0, "beats_s": [], "warnings": ["Audio too short"]},
            timing=SimpleNamespace(duration_ms=3200),
            lyrics=None,
        )
        mock_analyzer_cls.return_value = mock_analyzer

        stage = AudioAnalysisStage()
        result = await stage.execute("/tmp/short.wav", mock_context)

        assert result.success is False
        assert "meaningful timing features" in (result.error or "")


@pytest.mark.asyncio
async def test_audio_analysis_succeeds_for_meaningful_features(mock_context):
    """Stage succeeds when tempo and beats are available."""
    with patch("twinklr.core.audio.analyzer.AudioAnalyzer") as mock_analyzer_cls:
        mock_analyzer = AsyncMock()
        mock_analyzer.analyze.return_value = SimpleNamespace(
            features={"tempo_bpm": 120.0, "beats_s": [0.5, 1.0], "warnings": []},
            timing=SimpleNamespace(duration_ms=10000),
            lyrics=None,
        )
        mock_analyzer_cls.return_value = mock_analyzer

        stage = AudioAnalysisStage()
        result = await stage.execute("/tmp/song.wav", mock_context)

        assert result.success is True
        assert result.output is not None


@pytest.mark.asyncio
async def test_audio_analysis_sets_has_lyrics_for_timing_only_payload(mock_context):
    """has_lyrics should be true when words/phrases exist even if text is None."""
    with patch("twinklr.core.audio.analyzer.AudioAnalyzer") as mock_analyzer_cls:
        mock_analyzer = AsyncMock()
        mock_analyzer.analyze.return_value = SimpleNamespace(
            features={"tempo_bpm": 120.0, "beats_s": [0.5, 1.0], "warnings": []},
            timing=SimpleNamespace(duration_ms=10000),
            lyrics=LyricsBundle(
                schema_version="3.0.0",
                stage_status=StageStatus.OK,
                text=None,
                words=[LyricWord(text="hello", start_ms=0, end_ms=500)],
            ),
        )
        mock_analyzer_cls.return_value = mock_analyzer

        stage = AudioAnalysisStage()
        result = await stage.execute("/tmp/song.wav", mock_context)

        assert result.success is True
        assert mock_context.get_state("has_lyrics") is True
