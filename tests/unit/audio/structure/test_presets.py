"""Unit tests for section detection presets."""

import pytest

from twinklr.core.audio.structure.presets import (
    PRESETS,
    get_preset,
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
        assert preset.min_sections == 10  # Updated from refactor
        assert preset.max_sections == 16
        assert preset.min_len_beats == 24  # Longer for drops

    def test_pop_preset(self):
        """Test pop preset has balanced settings."""
        preset = PRESETS["pop"]
        assert preset.genre == "pop"
        assert preset.min_sections == 8  # Updated from refactor
        assert preset.max_sections == 14

    def test_country_preset(self):
        """Test country preset has higher vocal weight."""
        preset = PRESETS["country"]
        assert preset.genre == "country"
        assert preset.peak_delta < 0.09  # More sensitive (updated threshold)

    def test_christmas_classic_preset(self):
        """Test classic Christmas preset."""
        preset = PRESETS["christmas_classic"]
        assert preset.genre == "christmas_classic"
        assert preset.min_len_beats <= 20  # Shorter sections (updated threshold)

    def test_christmas_modern_preset(self):
        """Test modern Christmas preset is pop-like."""
        preset = PRESETS["christmas_modern"]
        pop_preset = PRESETS["pop"]
        assert preset.genre == "christmas_modern"
        assert preset.min_sections == pop_preset.min_sections
        assert preset.max_sections == pop_preset.max_sections

    def test_get_preset_invalid_genre(self):
        """Test that get_preset raises KeyError for unknown genre."""
        with pytest.raises(KeyError, match="Unknown genre"):
            get_preset("unknown_genre")
