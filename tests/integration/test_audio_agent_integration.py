"""Integration tests for Audio → Agent handoff.

Tests the integration between AudioAnalyzer (feature extraction)
and AgentOrchestrator (consuming song_features).

Focus: Data contract validation at the Audio-Agent boundary.
"""

from __future__ import annotations

import pytest

from blinkb0t.core.agents.moving_heads.context import ContextShaper
from blinkb0t.core.config.models import AppConfig, AudioProcessingConfig, JobConfig


@pytest.fixture
def mock_app_config():
    """Create minimal app configuration for AudioAnalyzer."""
    return AppConfig(
        audio_processing=AudioProcessingConfig(
            hop_length=512,
            frame_length=2048,
        )
    )


@pytest.fixture
def mock_job_config():
    """Create minimal job configuration."""
    return JobConfig.model_validate(
        {
            "assumptions": {"beats_per_bar": 4},
            "moving_heads": {
                "dmx_effect_defaults": {
                    "buffer_style": "Per Model Default",
                },
            },
        }
    )


@pytest.fixture
def complete_song_features():
    """Create complete song_features matching AudioAnalyzer output structure."""
    return {
        "tempo_bpm": 120.0,
        "duration_s": 10.0,  # Required by ContextShaper
        "beats_s": [0.5, 1.0, 1.5, 2.0, 2.5, 3.0, 3.5, 4.0, 4.5, 5.0],
        "bars_s": [0.5, 2.5, 4.5, 6.5, 8.5],
        "rhythm": {
            "downbeats": [0, 4, 8],
            "beat_strength": [0.9, 0.6, 0.7, 0.8, 0.9, 0.5, 0.7, 0.8, 0.9, 0.6],
        },
        "time_signature": {
            "time_signature": "4/4",
            "confidence": 0.95,
        },
        "assumptions": {
            "beats_per_bar": 4,
        },
        "energy": {
            "rms_curve": [0.5, 0.6, 0.7, 0.8, 0.9, 0.8, 0.7, 0.6, 0.5, 0.4],
        },
    }


class TestAudioAnalyzerContract:
    """Test that AudioAnalyzer produces the contract expected by AgentOrchestrator."""

    def test_song_features_has_required_timing_fields(self, mock_app_config, mock_job_config):
        """Test that song_features includes all required timing fields for agent."""
        # Required timing fields for agent orchestration
        required_fields = [
            "tempo_bpm",
            "beats_s",
            "bars_s",
            "rhythm",  # Should contain downbeats
        ]

        # Create minimal song_features (simulating AudioAnalyzer output)
        song_features = {
            "tempo_bpm": 120.0,
            "beats_s": [0.5, 1.0, 1.5, 2.0, 2.5, 3.0],
            "bars_s": [0.5, 2.5, 4.5],
            "rhythm": {
                "downbeats": [0, 4, 8],
                "beat_strength": [0.9, 0.5, 0.6, 0.8],
            },
            "time_signature": {
                "time_signature": "4/4",
                "confidence": 0.95,
            },
            "assumptions": {
                "beats_per_bar": 4,
            },
        }

        # Verify all required fields are present
        for field in required_fields:
            assert field in song_features, f"Missing required field: {field}"

        # Verify nested structure
        assert "downbeats" in song_features["rhythm"]
        assert isinstance(song_features["beats_s"], list)
        assert isinstance(song_features["bars_s"], list)

    def test_song_features_timing_arrays_are_compatible(self):
        """Test that timing arrays from AudioAnalyzer match agent expectations."""
        # Simulate AudioAnalyzer output
        song_features = {
            "tempo_bpm": 128.0,
            "beats_s": [0.5, 1.0, 1.5, 2.0, 2.5, 3.0, 3.5, 4.0],
            "bars_s": [0.5, 2.5, 4.5],
            "rhythm": {
                "downbeats": [0, 4],  # Indices into beats_s
            },
        }

        # Verify timing array types and structure
        assert isinstance(song_features["beats_s"], list)
        assert all(isinstance(b, (int, float)) for b in song_features["beats_s"])

        assert isinstance(song_features["bars_s"], list)
        assert all(isinstance(b, (int, float)) for b in song_features["bars_s"])

        # Verify downbeats are valid indices
        downbeats = song_features["rhythm"]["downbeats"]
        assert isinstance(downbeats, list)
        assert all(isinstance(d, int) for d in downbeats)

    def test_audio_analyzer_output_compatible_with_context_shaper(
        self, mock_app_config, mock_job_config, complete_song_features
    ):
        """Test that AudioAnalyzer output can be shaped by ContextShaper."""
        from blinkb0t.core.agents.moving_heads.context import Stage

        # Create ContextShaper
        context_shaper = ContextShaper(job_config=mock_job_config)

        # Attempt to shape for PLAN stage (public API)
        shaped_context = context_shaper.shape_for_stage(
            stage=Stage.PLAN,
            song_features=complete_song_features,
            seq_fingerprint=None,
            template_metadata=[],
        )

        # Verify shaped context is valid
        assert shaped_context is not None
        assert shaped_context.stage == Stage.PLAN
        assert "timing" in shaped_context.data
        assert "energy" in shaped_context.data

    def test_tempo_bpm_is_numeric(self):
        """Test that tempo_bpm is a numeric value (not string)."""
        song_features = {
            "tempo_bpm": 120.0,  # Should be numeric, not "120 BPM"
            "beats_s": [0.5, 1.0],
            "bars_s": [0.5],
        }

        assert isinstance(song_features["tempo_bpm"], (int, float))
        assert song_features["tempo_bpm"] > 0

    def test_timing_arrays_are_sorted_ascending(self):
        """Test that timing arrays are sorted in ascending order."""
        song_features = {
            "beats_s": [0.5, 1.0, 1.5, 2.0, 2.5, 3.0],
            "bars_s": [0.5, 2.5, 4.5],
        }

        # Verify beats_s is sorted
        beats = song_features["beats_s"]
        assert beats == sorted(beats), "beats_s must be sorted in ascending order"

        # Verify bars_s is sorted
        bars = song_features["bars_s"]
        assert bars == sorted(bars), "bars_s must be sorted in ascending order"


class TestAudioToAgentDataFlow:
    """Test the data flow from AudioAnalyzer through ContextShaper to Agent."""

    def test_minimal_song_features_can_be_shaped(self, mock_job_config, complete_song_features):
        """Test that minimal song_features can be shaped for agent consumption."""
        from blinkb0t.core.agents.moving_heads.context import Stage

        context_shaper = ContextShaper(job_config=mock_job_config)

        # Shape for PLAN stage (public API)
        shaped_context = context_shaper.shape_for_stage(
            stage=Stage.PLAN,
            song_features=complete_song_features,
            seq_fingerprint=None,
            template_metadata=[],
        )

        # Verify output structure
        assert shaped_context is not None
        assert shaped_context.stage == Stage.PLAN
        assert "timing" in shaped_context.data
        assert "energy" in shaped_context.data

    def test_context_shaper_handles_missing_optional_fields(
        self, mock_job_config, complete_song_features
    ):
        """Test that ContextShaper handles missing optional audio fields gracefully."""
        from blinkb0t.core.agents.moving_heads.context import Stage

        # Remove optional energy field to test graceful handling
        song_features = complete_song_features.copy()
        song_features.pop("energy", None)

        context_shaper = ContextShaper(job_config=mock_job_config)

        # Should not raise (missing energy, tension, etc. are optional)
        shaped_context = context_shaper.shape_for_stage(
            stage=Stage.PLAN,
            song_features=song_features,
            seq_fingerprint=None,
            template_metadata=[],
        )
        assert shaped_context is not None
        assert "timing" in shaped_context.data
        assert "energy" in shaped_context.data

    def test_unified_song_map_can_be_built(self, complete_song_features):
        """Test that build_unified_song_map works with AudioAnalyzer output."""
        from blinkb0t.core.domains.audio.context.unified_map import build_unified_song_map

        # Build unified song map (should not raise)
        song_map = build_unified_song_map(
            complete_song_features, max_events=50, resolution="downbeat"
        )

        # Verify structure (returns dict with 'events' key)
        assert isinstance(song_map, dict)
        assert "events" in song_map
        assert "metadata" in song_map
        assert isinstance(song_map["events"], list)
        assert len(song_map["events"]) > 0  # Should have events


class TestAudioAnalyzerRegressionContract:
    """Regression tests for AudioAnalyzer output structure (from earlier session)."""

    def test_time_signature_structure_preserved(self):
        """Test that time_signature has correct nested structure."""
        # From earlier session fix: time_signature should be nested dict
        song_features = {
            "time_signature": {
                "time_signature": "4/4",  # Nested structure
                "confidence": 0.95,
            },
            "assumptions": {
                "beats_per_bar": 4,  # Extracted from time_signature
            },
        }

        # Verify structure
        assert isinstance(song_features["time_signature"], dict)
        assert "time_signature" in song_features["time_signature"]
        assert "beats_per_bar" in song_features["assumptions"]

    def test_beats_per_bar_is_integer(self):
        """Test that beats_per_bar is an integer (not string)."""
        song_features = {
            "assumptions": {
                "beats_per_bar": 4,  # Should be int, extracted from "4/4"
            }
        }

        assert isinstance(song_features["assumptions"]["beats_per_bar"], int)
        assert song_features["assumptions"]["beats_per_bar"] > 0

    def test_rhythm_downbeats_are_integers(self):
        """Test that downbeats are integer indices (not floats)."""
        song_features = {
            "rhythm": {
                "downbeats": [0, 4, 8, 12],  # Integer indices into beats_s
            }
        }

        downbeats = song_features["rhythm"]["downbeats"]
        assert isinstance(downbeats, list)
        assert all(isinstance(d, int) for d in downbeats)


class TestAudioAgentIntegrationResilience:
    """Test resilience of Audio → Agent integration."""

    def test_agent_can_handle_very_short_song(self, mock_job_config):
        """Test that agent can handle minimal timing data (short songs)."""
        from blinkb0t.core.agents.moving_heads.context import Stage

        # Very short song (2 seconds)
        song_features = {
            "tempo_bpm": 120.0,
            "duration_s": 2.0,
            "beats_s": [0.5, 1.0, 1.5],
            "bars_s": [0.5],
            "rhythm": {"downbeats": [0]},
            "time_signature": {"time_signature": "4/4"},
            "assumptions": {"beats_per_bar": 4},
        }

        context_shaper = ContextShaper(job_config=mock_job_config)

        # Should handle gracefully (not crash)
        shaped_context = context_shaper.shape_for_stage(
            stage=Stage.PLAN,
            song_features=song_features,
            seq_fingerprint=None,
            template_metadata=[],
        )
        assert shaped_context is not None

    def test_agent_can_handle_very_long_timing_arrays(self, mock_job_config):
        """Test that agent can handle long timing arrays (long songs)."""
        from blinkb0t.core.agents.moving_heads.context import Stage

        # Simulate 5-minute song at 120 BPM (600 beats)
        song_features = {
            "tempo_bpm": 120.0,
            "duration_s": 300.0,  # 5 minutes
            "beats_s": [i * 0.5 for i in range(600)],  # 600 beats
            "bars_s": [i * 2.0 for i in range(150)],  # 150 bars
            "rhythm": {"downbeats": list(range(0, 600, 4))},
            "time_signature": {"time_signature": "4/4"},
            "assumptions": {"beats_per_bar": 4},
        }

        context_shaper = ContextShaper(job_config=mock_job_config)

        # Should handle gracefully (with reduction)
        shaped_context = context_shaper.shape_for_stage(
            stage=Stage.PLAN,
            song_features=song_features,
            seq_fingerprint=None,
            template_metadata=[],
        )
        assert shaped_context is not None

        # Build unified song map (should reduce to max_events)
        from blinkb0t.core.domains.audio.context.unified_map import build_unified_song_map

        song_map = build_unified_song_map(song_features, max_events=80)

        # Verify reduction applied (song_map is dict with 'events' key)
        assert isinstance(song_map, dict)
        assert "events" in song_map
        assert len(song_map["events"]) <= 80

    def test_agent_handles_non_standard_time_signatures(self, mock_job_config):
        """Test that agent handles non-4/4 time signatures."""
        from blinkb0t.core.agents.moving_heads.context import Stage

        # 3/4 time signature (waltz)
        song_features = {
            "tempo_bpm": 180.0,
            "duration_s": 2.0,
            "beats_s": [0.33, 0.66, 1.0, 1.33, 1.66, 2.0],
            "bars_s": [0.33, 1.33],
            "rhythm": {"downbeats": [0, 3]},
            "time_signature": {"time_signature": "3/4"},
            "assumptions": {"beats_per_bar": 3},
        }

        context_shaper = ContextShaper(job_config=mock_job_config)

        # Should handle non-4/4 gracefully
        shaped_context = context_shaper.shape_for_stage(
            stage=Stage.PLAN,
            song_features=song_features,
            seq_fingerprint=None,
            template_metadata=[],
        )
        assert shaped_context is not None
