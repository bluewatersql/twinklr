"""Test module setup and imports for AudioProfile agent."""

import pytest


def test_audio_agents_module_importable():
    """Verify audio agents module can be imported."""
    try:
        import twinklr.core.agents.audio

        assert hasattr(twinklr.core.agents, "audio")
    except ImportError as e:
        pytest.fail(f"Failed to import twinklr.core.agents.audio: {e}")


def test_audio_profile_module_importable():
    """Verify audio_profile module can be imported."""
    try:
        import twinklr.core.agents.audio.profile

        assert hasattr(twinklr.core.agents.audio, "profile")
    except ImportError as e:
        pytest.fail(f"Failed to import twinklr.core.agents.audio.profile: {e}")


def test_audio_profile_has_version():
    """Verify audio_profile module has version attribute."""
    from twinklr.core.agents.audio import profile

    assert hasattr(profile, "__version__")
    assert isinstance(profile.__version__, str)
    assert profile.__version__ == "1.0.0"


def test_audio_profile_module_docstring():
    """Verify audio_profile module has proper docstring."""
    from twinklr.core.agents.audio import profile

    assert profile.__doc__ is not None
    assert "AudioProfile" in profile.__doc__
