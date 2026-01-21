"""Unit tests for context shaper withchannel extensions."""

import pytest

from blinkb0t.core.agents.moving_heads.context import (
    ContextShaper,
    Stage,
    build_channel_library_context,
)
from blinkb0t.core.config.models import JobConfig


class TestBuildChannelLibraryContext:
    """Test building channel library context for LLM."""

    def test_builds_complete_context(self):
        """Test building complete channel library context."""
        context = build_channel_library_context()

        assert "shutter" in context
        assert "color" in context
        assert "gobo" in context
        assert isinstance(context["shutter"], list)
        assert isinstance(context["color"], list)
        assert isinstance(context["gobo"], list)

    def test_shutter_library_includes_required_fields(self):
        """Test shutter library has all required fields."""
        context = build_channel_library_context()

        for pattern in context["shutter"]:
            assert "pattern_id" in pattern
            assert "name" in pattern
            assert "description" in pattern
            assert "energy_level" in pattern
            assert isinstance(pattern["energy_level"], int)

    def test_color_library_includes_required_fields(self):
        """Test color library has all required fields."""
        context = build_channel_library_context()

        for preset in context["color"]:
            assert "color_id" in preset
            assert "name" in preset
            assert "description" in preset
            assert "category" in preset
            assert "mood" in preset

    def test_gobo_library_includes_required_fields(self):
        """Test gobo library has all required fields."""
        context = build_channel_library_context()

        for pattern in context["gobo"]:
            assert "gobo_id" in pattern
            assert "name" in pattern
            assert "description" in pattern
            assert "category" in pattern
            assert "visual_density" in pattern
            assert isinstance(pattern["visual_density"], int)

    def test_has_open_shutter_pattern(self):
        """Test context includes open shutter pattern."""
        context = build_channel_library_context()

        pattern_ids = [p["pattern_id"] for p in context["shutter"]]
        assert "open" in pattern_ids

    def test_has_strobe_patterns(self):
        """Test context includes strobe patterns."""
        context = build_channel_library_context()

        pattern_ids = [p["pattern_id"] for p in context["shutter"]]
        # Should have some strobe variants
        assert any("strobe" in pid for pid in pattern_ids)

    def test_has_basic_colors(self):
        """Test context includes basic color presets."""
        context = build_channel_library_context()

        color_ids = [c["color_id"] for c in context["color"]]
        # Should have basic colors
        for basic_color in ["white", "red", "blue"]:
            assert basic_color in color_ids


class TestContextShaperWithChannels:
    """Test context shaper withchannel support."""

    @pytest.fixture
    def shaper(self):
        """Create context shaper instance."""
        return ContextShaper(job_config=JobConfig())

    @pytest.fixture
    def mock_song_features(self):
        """Mock song features."""
        return {
            "duration_s": 10.0,
            "tempo_bpm": 120.0,
            "bars_s": [0.0, 2.0, 4.0, 6.0, 8.0],
            "beats_s": list(range(0, 20, 1)),
            "time_signature": {"time_signature": "4/4"},
            "energy": {
                "times_s": [0.0, 2.0, 4.0, 6.0, 8.0],
                "phrase_level": [0.3, 0.5, 0.7, 0.9, 0.5],
                "peaks": [{"time_s": 6.0, "energy": 0.9}],
                "stats": {"mean": 0.58, "max": 0.9},
            },
        }

    @pytest.fixture
    def mock_template_metadata(self):
        """Mock template metadata."""
        return [
            {
                "template_id": "gentle_sweep",
                "name": "Gentle Sweep",
                "category": "low_energy",
                "metadata": {
                    "description": "Slow gentle sweep",
                    "energy_range": [0, 40],
                    "recommended_sections": ["intro", "verse"],
                    "tags": ["slow", "gentle", "sweep"],
                },
                "step_count": 1,
            }
        ]

    def test_shape_for_plan_includes_channels(
        self, shaper, mock_song_features, mock_template_metadata
    ):
        """Test planning context includes channel libraries."""
        channel_libraries = build_channel_library_context()

        shaped = shaper.shape_for_stage(
            stage=Stage.PLAN,
            song_features=mock_song_features,
            template_metadata=mock_template_metadata,
            channel_libraries=channel_libraries,
        )

        assert "channels" in shaped.data
        assert "shutter" in shaped.data["channels"]
        assert "color" in shaped.data["channels"]
        assert "gobo" in shaped.data["channels"]

    def test_channel_libraries_compacted(self, shaper, mock_song_features, mock_template_metadata):
        """Test channel libraries are compacted for token efficiency."""
        channel_libraries = build_channel_library_context()

        shaped = shaper.shape_for_stage(
            stage=Stage.PLAN,
            song_features=mock_song_features,
            template_metadata=mock_template_metadata,
            channel_libraries=channel_libraries,
        )

        # Should be compacted
        channels = shaped.data["channels"]
        for shutter_pattern in channels["shutter"]:
            # Description should be truncated to 80 chars
            assert len(shutter_pattern["description"]) <= 80
            # Should have essential fields
            assert "pattern_id" in shutter_pattern
            assert "energy_level" in shutter_pattern

    def test_shape_without_channels_backward_compatible(
        self, shaper, mock_song_features, mock_template_metadata
    ):
        """Test shaping without channel libraries is backward compatible."""
        shaped = shaper.shape_for_stage(
            stage=Stage.PLAN,
            song_features=mock_song_features,
            template_metadata=mock_template_metadata,
            # No channel_libraries parameter
        )

        # Should not have channels key if not provided
        assert "channels" not in shaped.data

    def test_token_estimate_includes_channels(
        self, shaper, mock_song_features, mock_template_metadata
    ):
        """Test token estimate includes channel library overhead."""
        # Without channels
        shaped_without = shaper.shape_for_stage(
            stage=Stage.PLAN,
            song_features=mock_song_features,
            template_metadata=mock_template_metadata,
        )

        # With channels
        channel_libraries = build_channel_library_context()
        shaped_with = shaper.shape_for_stage(
            stage=Stage.PLAN,
            song_features=mock_song_features,
            template_metadata=mock_template_metadata,
            channel_libraries=channel_libraries,
        )

        # With channels should have more tokens
        assert shaped_with.token_estimate > shaped_without.token_estimate
        # But should still be reasonable (<10k)
        assert shaped_with.token_estimate < 10000

    def test_channel_context_has_expected_patterns(self):
        """Test channel context has expected number of patterns."""
        context = build_channel_library_context()

        # Should have multiple shutters (at least 5)
        assert len(context["shutter"]) >= 5
        # Should have multiple colors (at least 10)
        assert len(context["color"]) >= 10
        # Should have multiple gobos (at least 10)
        assert len(context["gobo"]) >= 10
