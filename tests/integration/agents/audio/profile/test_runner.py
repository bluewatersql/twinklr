"""Integration tests for AudioProfile agent with AsyncAgentRunner."""

import pytest

from twinklr.core.agents.audio.profile import get_audio_profile_spec
from twinklr.core.agents.audio.profile.models import AudioProfileModel


def test_audio_profile_spec_can_be_created():
    """Test that AudioProfile spec can be instantiated."""
    spec = get_audio_profile_spec()
    assert spec.name == "audio_profile"
    assert spec.response_model == AudioProfileModel


@pytest.mark.skip(reason="Requires real SongBundle fixture - to be implemented in P1.6.x")
def test_context_shaping_with_real_song_bundle():
    """Test context shaping with real SongBundle (requires fixture)."""
    # Will be implemented in P1.6.1 (Golden Fixtures)


@pytest.mark.skip(reason="Requires OpenAI API key and live LLM call - to be implemented in P1.6.x")
@pytest.mark.asyncio
async def test_run_audio_profile_end_to_end():
    """Test running AudioProfile agent end-to-end (requires API key and fixture)."""
    # Will be implemented in P1.6.3 (End-to-End Tests)
