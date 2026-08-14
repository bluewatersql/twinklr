"""Lyrics stage cache-contract tests."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from twinklr.core.agents.audio.lyrics.stage import LYRICS_CACHE_VERSION, LyricsStage
from twinklr.core.config.models import AgentConfig


@pytest.mark.asyncio
async def test_execute_uses_t4_cache_version() -> None:
    """Cached v1 lyrics must not bypass T4 MomentCue validation."""
    song_bundle = MagicMock()
    song_bundle.lyrics.text = "A timed lyric"
    context = MagicMock()
    context.provider = MagicMock()
    context.llm_logger = MagicMock()
    context.job_config.agent.lyrics_agent = AgentConfig()

    with patch(
        "twinklr.core.pipeline.execution.execute_step",
        new=AsyncMock(return_value=MagicMock(success=True)),
    ) as execute_step:
        result = await LyricsStage().execute(song_bundle, context)

    assert result.success
    assert execute_step.await_args.kwargs["cache_version"] == LYRICS_CACHE_VERSION
