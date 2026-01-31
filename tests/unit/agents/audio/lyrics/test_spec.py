"""Unit tests for Lyrics agent spec."""

from twinklr.core.agents.audio.lyrics.models import LyricContextModel
from twinklr.core.agents.audio.lyrics.spec import get_lyrics_spec
from twinklr.core.agents.spec import AgentMode


class TestGetLyricsSpec:
    """Test get_lyrics_spec function."""

    def test_default_spec(self):
        """Test default spec creation."""
        spec = get_lyrics_spec()

        assert spec.name == "lyrics"
        assert spec.prompt_pack == "lyrics"
        assert spec.response_model == LyricContextModel
        assert spec.mode == AgentMode.ONESHOT
        assert spec.model == "gpt-5.2"
        assert spec.temperature == 0.5
        assert spec.max_schema_repair_attempts == 2
        assert spec.token_budget is None
        assert spec.default_variables == {}

    def test_custom_model(self):
        """Test spec with custom model."""
        spec = get_lyrics_spec(model="gpt-4")

        assert spec.model == "gpt-4"

    def test_custom_temperature(self):
        """Test spec with custom temperature."""
        spec = get_lyrics_spec(temperature=0.7)

        assert spec.temperature == 0.7

    def test_custom_token_budget(self):
        """Test spec with custom token budget."""
        spec = get_lyrics_spec(token_budget=5000)

        assert spec.token_budget == 5000

    def test_all_custom_params(self):
        """Test spec with all custom parameters."""
        spec = get_lyrics_spec(
            model="gpt-5-mini",
            temperature=0.6,
            token_budget=10000,
        )

        assert spec.name == "lyrics"
        assert spec.model == "gpt-5-mini"
        assert spec.temperature == 0.6
        assert spec.token_budget == 10000
