"""Tests for AudioProfile agent specification."""

from pydantic import ValidationError
import pytest

from twinklr.core.agents.audio.profile.models import AudioProfileModel
from twinklr.core.agents.audio.profile.spec import get_audio_profile_spec
from twinklr.core.agents.spec import AgentMode, AgentSpec


def test_audio_profile_spec_returns_agent_spec():
    """Test that get_audio_profile_spec returns an AgentSpec instance."""
    spec = get_audio_profile_spec()
    assert isinstance(spec, AgentSpec)


def test_audio_profile_spec_has_correct_name():
    """Test that spec has correct agent name."""
    spec = get_audio_profile_spec()
    assert spec.name == "audio_profile"


def test_audio_profile_spec_has_correct_prompt_pack():
    """Test that spec references correct prompt pack."""
    spec = get_audio_profile_spec()
    assert spec.prompt_pack == "audio_profile"


def test_audio_profile_spec_has_correct_response_model():
    """Test that spec uses AudioProfileModel as response model."""
    spec = get_audio_profile_spec()
    assert spec.response_model == AudioProfileModel


def test_audio_profile_spec_uses_oneshot_mode():
    """Test that spec uses ONESHOT mode (no iteration, no judge)."""
    spec = get_audio_profile_spec()
    assert spec.mode == AgentMode.ONESHOT


def test_audio_profile_spec_uses_low_temperature():
    """Test that spec uses moderate temperature for balanced output."""
    spec = get_audio_profile_spec()
    assert spec.temperature == 0.4


def test_audio_profile_spec_uses_gpt5_2():
    """Test that spec uses gpt-5.2 model."""
    spec = get_audio_profile_spec()
    assert spec.model == "gpt-5.2"


def test_audio_profile_spec_has_schema_repair():
    """Test that spec has schema repair configured."""
    spec = get_audio_profile_spec()
    assert spec.max_schema_repair_attempts >= 2


def test_audio_profile_spec_allows_custom_model():
    """Test that model can be overridden."""
    spec = get_audio_profile_spec(model="gpt-4o")
    assert spec.model == "gpt-4o"


def test_audio_profile_spec_allows_custom_temperature():
    """Test that temperature can be overridden."""
    spec = get_audio_profile_spec(temperature=0.5)
    assert spec.temperature == 0.5


def test_audio_profile_spec_allows_token_budget():
    """Test that token budget can be set."""
    spec = get_audio_profile_spec(token_budget=15000)
    assert spec.token_budget == 15000


def test_audio_profile_spec_token_budget_defaults_to_none():
    """Test that token budget defaults to None."""
    spec = get_audio_profile_spec()
    assert spec.token_budget is None


def test_audio_profile_spec_is_immutable():
    """Test that spec is frozen (immutable)."""
    spec = get_audio_profile_spec()
    with pytest.raises((ValidationError, TypeError, AttributeError)):
        spec.temperature = 0.9
