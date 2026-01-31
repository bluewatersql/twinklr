"""Integration tests for Lyrics agent with AsyncAgentRunner."""

import pytest

from twinklr.core.agents.audio.lyrics import get_lyrics_spec
from twinklr.core.agents.audio.lyrics.models import LyricContextModel


def test_lyrics_spec_can_be_created():
    """Test that Lyrics spec can be instantiated."""
    spec = get_lyrics_spec()
    assert spec.name == "lyrics"
    assert spec.response_model == LyricContextModel


def test_lyrics_spec_has_correct_defaults():
    """Test that Lyrics spec has correct default values."""
    spec = get_lyrics_spec()
    assert spec.model == "gpt-5.2"
    assert spec.temperature == 0.5
    assert spec.max_schema_repair_attempts == 2


@pytest.mark.skip(reason="Requires real SongBundle fixture with lyrics - to be implemented")
def test_context_shaping_with_real_lyrics():
    """Test context shaping with real lyrics (requires fixture with lyrics)."""
    # Will be implemented when SongBundle fixtures with lyrics are available


@pytest.mark.skip(reason="Requires OpenAI API key and live LLM call - to be implemented")
@pytest.mark.asyncio
async def test_run_lyrics_agent_end_to_end():
    """Test running Lyrics agent end-to-end (requires API key and lyrics fixture)."""
    # Will be implemented for end-to-end testing with real LLM calls
