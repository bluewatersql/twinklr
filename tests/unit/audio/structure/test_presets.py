"""Unit tests for section detection presets."""

import pytest

from twinklr.core.audio.structure.presets import (
    PRESETS,
    get_preset,
    get_preset_or_default,
)


class TestPresets:
    """Tests for genre presets."""

    def test_all_presets_valid(self):
        """Test that all predefined presets are valid."""
        for genre, preset in PRESETS.items():
            assert preset.genre == genre
            assert preset.min_sections >= 2
            assert preset.max_sections >= preset.min_sections
            assert preset.min_len_beats >= 1
            assert 0.0 <= preset.peak_delta <= 1.0

    def test_edm_preset(self):
        """Test EDM preset has expected characteristics."""
        preset = PRESETS["edm"]
        assert preset.genre == "edm"
        assert preset.min_sections == 12
        assert preset.max_sections == 18
        assert preset.min_len_beats == 16  # Longer for drops
        assert preset.context_weights["drops_weight"] > 0.7  # Drops important

    def test_pop_preset(self):
        """Test pop preset has balanced settings."""
        preset = PRESETS["pop"]
        assert preset.genre == "pop"
        assert preset.min_sections == 14
        assert preset.max_sections == 20
        assert preset.context_weights["vocals_weight"] > 0.6  # Vocals important

    def test_country_preset(self):
        """Test country preset has higher vocal weight."""
        preset = PRESETS["country"]
        assert preset.genre == "country"
        assert preset.peak_delta < 0.06  # More sensitive
        assert preset.context_weights["vocals_weight"] > 0.7
        assert preset.context_weights["chords_weight"] > 0.5

    def test_christmas_classic_preset(self):
        """Test classic Christmas preset."""
        preset = PRESETS["christmas_classic"]
        assert preset.genre == "christmas_classic"
        assert preset.min_len_beats <= 10  # Shorter sections
        assert preset.context_weights["chords_weight"] > 0.6  # Harmonic structure

    def test_christmas_modern_preset(self):
        """Test modern Christmas preset is pop-like."""
        preset = PRESETS["christmas_modern"]
        pop_preset = PRESETS["pop"]
        assert preset.genre == "christmas_modern"
        assert preset.min_sections == pop_preset.min_sections
        assert preset.max_sections == pop_preset.max_sections

    def test_get_preset_valid_genre(self):
        """Test getting preset by genre name."""
        preset = get_preset("edm")
        assert preset.genre == "edm"

    def test_get_preset_invalid_genre(self):
        """Test that get_preset raises KeyError for unknown genre."""
        with pytest.raises(KeyError, match="Unknown genre"):
            get_preset("unknown_genre")

    def test_get_preset_or_default_valid(self):
        """Test get_preset_or_default with valid genre."""
        preset = get_preset_or_default("edm")
        assert preset.genre == "edm"

    def test_get_preset_or_default_none(self):
        """Test get_preset_or_default with None returns default."""
        preset = get_preset_or_default(None)
        assert preset.genre == "pop"  # Default

    def test_get_preset_or_default_invalid(self):
        """Test get_preset_or_default with invalid genre returns default."""
        preset = get_preset_or_default("unknown_genre")
        assert preset.genre == "pop"  # Default

    def test_get_preset_or_default_custom_default(self):
        """Test get_preset_or_default with custom default."""
        preset = get_preset_or_default("unknown_genre", default="edm")
        assert preset.genre == "edm"

    def test_all_presets_have_context_weights(self):
        """Test that all presets define context weights."""
        required_keys = ["drops_weight", "builds_weight", "vocals_weight", "chords_weight"]
        for genre, preset in PRESETS.items():
            for key in required_keys:
                assert key in preset.context_weights, f"{genre} missing {key}"
                assert 0.0 <= preset.context_weights[key] <= 1.0
