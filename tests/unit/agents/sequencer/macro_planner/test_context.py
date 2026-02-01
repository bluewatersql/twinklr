"""Unit tests for PlanningContext model."""

import json
from pathlib import Path

import pytest

from twinklr.core.agents.audio.lyrics.models import LyricContextModel
from twinklr.core.agents.audio.profile.models import AudioProfileModel
from twinklr.core.agents.sequencer.macro_planner.context import PlanningContext


class TestPlanningContext:
    """Test PlanningContext model."""

    def test_valid_planning_context_without_lyrics(self, audio_profile_fixture):
        """Test valid planning context without lyric context."""
        ctx = PlanningContext(
            audio_profile=audio_profile_fixture,
            lyric_context=None,
            display_groups=[{"role_key": "OUTLINE", "model_count": 10}],
        )

        assert ctx.audio_profile == audio_profile_fixture
        assert ctx.lyric_context is None
        assert len(ctx.display_groups) == 1
        assert ctx.has_lyrics is False

    def test_valid_planning_context_with_lyrics(self, audio_profile_fixture, lyric_context_fixture):
        """Test valid planning context with lyric context."""
        ctx = PlanningContext(
            audio_profile=audio_profile_fixture,
            lyric_context=lyric_context_fixture,
            display_groups=[{"role_key": "OUTLINE", "model_count": 10}],
        )

        assert ctx.audio_profile == audio_profile_fixture
        assert ctx.lyric_context == lyric_context_fixture
        assert len(ctx.display_groups) == 1
        assert ctx.has_lyrics is True

    def test_planning_context_properties(self, audio_profile_fixture):
        """Test planning context convenience properties."""
        ctx = PlanningContext(
            audio_profile=audio_profile_fixture,
            lyric_context=None,
            display_groups=[],
        )

        # Properties from audio profile fixture
        assert ctx.song_title is not None
        assert ctx.song_duration_ms > 0
        assert ctx.has_lyrics is False


# Fixtures


@pytest.fixture
def audio_profile_fixture():
    """Load real AudioProfile fixture."""
    fixture_path = (
        Path(__file__).parent.parent.parent.parent.parent
        / "fixtures"
        / "audio_profile"
        / "audio_profile_model.json"
    )
    with fixture_path.open() as f:
        data = json.load(f)
    return AudioProfileModel(**data)


@pytest.fixture
def lyric_context_fixture():
    """Minimal LyricContextModel for testing."""
    from twinklr.core.agents.audio.lyrics.models import KeyPhrase, Provenance

    return LyricContextModel(
        run_id="test-lyric-run",
        has_lyrics=True,
        themes=["celebration", "joy"],
        mood_arc="happy throughout",
        vocal_coverage_pct=0.75,
        key_phrases=[
            KeyPhrase(
                text=f"Phrase {i}",
                timestamp_ms=1000 * i,
                section_id="verse",
                visual_hint=f"Visual hint {i}",
            )
            for i in range(5)
        ],
        recommended_visual_themes=["bright", "festive", "joyful"],
        provenance=Provenance(
            provider_id="openai",
            model_id="gpt-5.2",
            prompt_pack="lyrics",
            prompt_pack_version="2.0",
            framework_version="twinklr-agents-2.0",
            temperature=0.5,
        ),
    )
