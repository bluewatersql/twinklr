"""Tests for lighting hints generation."""

from __future__ import annotations

from typing import Any

from twinklr.core.audio.context.hints import build_lighting_hints


class TestBuildLightingHints:
    """Tests for build_lighting_hints function."""

    def test_returns_expected_structure(
        self,
        sample_song_features: dict[str, Any],
    ) -> None:
        """Function returns expected dictionary structure."""
        result = build_lighting_hints(sample_song_features)

        assert "movement_speed" in result
        assert "tempo_category" in result
        assert "tempo_stability" in result
        assert "energy_profile" in result
        assert "complexity_hints" in result
        assert "dynamic_hints" in result
        assert "structure_hints" in result
        assert "musical_context" in result
        assert "vocal_hints" in result
        assert "harmonic_hints" in result
        assert "build_drop_hints" in result
        assert "tension_hints" in result

    def test_movement_speed_categories(
        self,
        sample_song_features: dict[str, Any],
    ) -> None:
        """Movement speed is one of valid categories."""
        # Test slow tempo
        slow_features = sample_song_features.copy()
        slow_features["tempo_bpm"] = 70
        slow_features["tempo_analysis"] = {"average_tempo_bpm": 70, "is_stable": True}
        result_slow = build_lighting_hints(slow_features)
        assert result_slow["movement_speed"] == "slow"

        # Test medium tempo
        medium_features = sample_song_features.copy()
        medium_features["tempo_bpm"] = 100
        medium_features["tempo_analysis"] = {"average_tempo_bpm": 100, "is_stable": True}
        result_medium = build_lighting_hints(medium_features)
        assert result_medium["movement_speed"] == "medium"

        # Test fast tempo
        fast_features = sample_song_features.copy()
        fast_features["tempo_bpm"] = 140
        fast_features["tempo_analysis"] = {"average_tempo_bpm": 140, "is_stable": True}
        result_fast = build_lighting_hints(fast_features)
        assert result_fast["movement_speed"] == "fast"

        # Test very fast tempo
        very_fast_features = sample_song_features.copy()
        very_fast_features["tempo_bpm"] = 180
        very_fast_features["tempo_analysis"] = {"average_tempo_bpm": 180, "is_stable": True}
        result_very_fast = build_lighting_hints(very_fast_features)
        assert result_very_fast["movement_speed"] == "very_fast"

    def test_energy_profile_structure(
        self,
        sample_song_features: dict[str, Any],
    ) -> None:
        """Energy profile contains expected keys."""
        result = build_lighting_hints(sample_song_features)

        energy_profile = result["energy_profile"]
        assert "average" in energy_profile
        assert "variance" in energy_profile
        assert "recommendation" in energy_profile

    def test_complexity_hints_structure(
        self,
        sample_song_features: dict[str, Any],
    ) -> None:
        """Complexity hints contains expected keys."""
        result = build_lighting_hints(sample_song_features)

        complexity = result["complexity_hints"]
        assert "spectral_complexity" in complexity
        assert "percussive_content" in complexity
        assert "suggested_pattern_complexity" in complexity

    def test_structure_hints_structure(
        self,
        sample_song_features: dict[str, Any],
    ) -> None:
        """Structure hints contains expected keys."""
        result = build_lighting_hints(sample_song_features)

        structure = result["structure_hints"]
        assert "num_sections" in structure
        assert "has_chorus" in structure
        assert "has_verse" in structure
        assert "has_bridge" in structure
        assert "recommend_section_changes" in structure

    def test_musical_context_structure(
        self,
        sample_song_features: dict[str, Any],
    ) -> None:
        """Musical context contains expected keys."""
        result = build_lighting_hints(sample_song_features)

        context = result["musical_context"]
        assert "key" in context
        assert "mode" in context
        assert "tonal_character" in context
        assert "suggested_color_palette" in context

    def test_color_palette_by_mode(
        self,
        sample_song_features: dict[str, Any],
    ) -> None:
        """Color palette suggestion depends on mode."""
        # Major mode -> warm
        major_features = sample_song_features.copy()
        major_features["key"] = {"key": "C", "mode": "major", "confidence": 0.8}
        result_major = build_lighting_hints(major_features)
        assert result_major["musical_context"]["suggested_color_palette"] == "warm"

        # Minor mode -> cool
        minor_features = sample_song_features.copy()
        minor_features["key"] = {"key": "A", "mode": "minor", "confidence": 0.8}
        result_minor = build_lighting_hints(minor_features)
        assert result_minor["musical_context"]["suggested_color_palette"] == "cool"

    def test_vocal_hints_structure(
        self,
        sample_song_features: dict[str, Any],
    ) -> None:
        """Vocal hints contains expected keys."""
        result = build_lighting_hints(sample_song_features)

        vocal_hints = result["vocal_hints"]
        assert "has_vocals" in vocal_hints
        assert "vocal_coverage_pct" in vocal_hints
        assert "recommendation" in vocal_hints

    def test_build_drop_hints_structure(
        self,
        sample_song_features: dict[str, Any],
    ) -> None:
        """Build/drop hints contains expected keys."""
        result = build_lighting_hints(sample_song_features)

        build_drop = result["build_drop_hints"]
        assert "has_builds" in build_drop
        assert "has_drops" in build_drop
        assert "build_count" in build_drop
        assert "drop_count" in build_drop
        assert "recommendation" in build_drop

    def test_handles_missing_keys(self) -> None:
        """Function handles missing keys gracefully."""
        minimal_features: dict[str, Any] = {
            "tempo_bpm": 120,
        }

        # Should not raise
        result = build_lighting_hints(minimal_features)
        assert "movement_speed" in result

    def test_tempo_stability_values(
        self,
        sample_song_features: dict[str, Any],
    ) -> None:
        """Tempo stability is 'stable' or 'variable'."""
        # Stable tempo
        stable_features = sample_song_features.copy()
        stable_features["tempo_analysis"] = {"is_stable": True, "average_tempo_bpm": 120}
        result_stable = build_lighting_hints(stable_features)
        assert result_stable["tempo_stability"] == "stable"

        # Variable tempo
        variable_features = sample_song_features.copy()
        variable_features["tempo_analysis"] = {"is_stable": False, "average_tempo_bpm": 120}
        result_variable = build_lighting_hints(variable_features)
        assert result_variable["tempo_stability"] == "variable"
