"""Unit tests for section detection Pydantic models."""

from pydantic import ValidationError
import pytest

from twinklr.core.audio.structure.models import SectioningPreset


class TestSectioningPreset:
    """Tests for SectioningPreset."""

    def test_valid_preset(self):
        """Test creating a valid preset."""
        preset = SectioningPreset(
            genre="edm",
            min_sections=12,
            max_sections=18,
            min_len_beats=16,
            novelty_l_beats=16,
            peak_delta=0.07,
            pre_avg=12,
            post_avg=12,
        )
        assert preset.genre == "edm"
        assert preset.min_sections == 12
        assert preset.max_sections == 18
        assert preset.min_len_beats == 16

    def test_preset_is_frozen(self):
        """Test that preset is immutable."""
        preset = SectioningPreset(
            genre="pop",
            min_sections=14,
            max_sections=20,
            min_len_beats=12,
            novelty_l_beats=12,
            peak_delta=0.06,
            pre_avg=10,
            post_avg=10,
        )
        with pytest.raises((ValidationError, AttributeError)):
            preset.min_sections = 10  # type: ignore
