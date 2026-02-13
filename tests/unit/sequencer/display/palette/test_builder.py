"""Unit tests for the PaletteBuilder."""

from __future__ import annotations

from twinklr.core.sequencer.display.models.palette import ResolvedPalette
from twinklr.core.sequencer.display.palette.builder import build_palette_string


class TestBuildPaletteString:
    """Tests for the build_palette_string function."""

    def test_single_color(self) -> None:
        p = ResolvedPalette(colors=["#FF0000"], active_slots=[1])
        s = build_palette_string(p)

        assert "C_BUTTON_Palette1=#FF0000" in s
        assert "C_CHECKBOX_Palette1=1" in s
        # Inactive slots should NOT have checkbox entries
        assert "C_CHECKBOX_Palette2" not in s
        # All 8 button slots should be present
        assert "C_BUTTON_Palette8=" in s

    def test_two_colors(self) -> None:
        p = ResolvedPalette(
            colors=["#FF0000", "#00FF00"],
            active_slots=[1, 2],
        )
        s = build_palette_string(p)

        assert "C_BUTTON_Palette1=#FF0000" in s
        assert "C_BUTTON_Palette2=#00FF00" in s
        assert "C_CHECKBOX_Palette1=1" in s
        assert "C_CHECKBOX_Palette2=1" in s

    def test_sparkle_frequency(self) -> None:
        p = ResolvedPalette(
            colors=["#FFFFFF"],
            active_slots=[1],
            sparkle_frequency=100,
        )
        s = build_palette_string(p)
        assert "C_SLIDER_SparkleFrequency=100" in s

    def test_no_sparkle_omitted(self) -> None:
        """SparkleFrequency=0 should be omitted (xLights convention)."""
        p = ResolvedPalette(colors=["#FFFFFF"], active_slots=[1])
        s = build_palette_string(p)
        assert "SparkleFrequency" not in s

    def test_brightness(self) -> None:
        p = ResolvedPalette(
            colors=["#FF0000"],
            active_slots=[1],
            brightness=80,
        )
        s = build_palette_string(p)
        assert "C_SLIDER_Brightness=80" in s

    def test_music_sparkles(self) -> None:
        p = ResolvedPalette(
            colors=["#FF0000"],
            active_slots=[1],
            music_sparkles=True,
        )
        s = build_palette_string(p)
        assert "C_CHECKBOX_MusicSparkles=1" in s

    def test_hue_adjust(self) -> None:
        p = ResolvedPalette(
            colors=["#FF0000"],
            active_slots=[1],
            hue_adjust=25,
        )
        s = build_palette_string(p)
        assert "C_SLIDER_Color_HueAdjust=25" in s

    def test_default_slots_black(self) -> None:
        """Slots beyond provided colors should default to black."""
        p = ResolvedPalette(colors=["#FF0000"], active_slots=[1])
        s = build_palette_string(p)
        assert "C_BUTTON_Palette2=#000000" in s
        assert "C_BUTTON_Palette8=#000000" in s

    def test_buttons_grouped_before_checkboxes(self) -> None:
        """All C_BUTTON entries should appear before any C_CHECKBOX entries."""
        p = ResolvedPalette(
            colors=["#FF0000", "#00FF00"],
            active_slots=[1, 2],
        )
        s = build_palette_string(p)

        # Find the position of the last button and first checkbox
        last_button_pos = s.rfind("C_BUTTON_Palette")
        first_checkbox_pos = s.find("C_CHECKBOX_Palette")
        assert last_button_pos < first_checkbox_pos

    def test_inactive_checkbox_not_emitted(self) -> None:
        """Inactive slots should not have C_CHECKBOX entries at all."""
        p = ResolvedPalette(
            colors=["#FF0000", "#00FF00", "#0000FF"],
            active_slots=[1, 3],  # slot 2 inactive
        )
        s = build_palette_string(p)

        assert "C_CHECKBOX_Palette1=1" in s
        assert "C_CHECKBOX_Palette3=1" in s
        # Slot 2 should have a button but NO checkbox
        assert "C_BUTTON_Palette2=#00FF00" in s
        assert "C_CHECKBOX_Palette2" not in s

    def test_matches_xlights_format(self) -> None:
        """Full palette should match xLights native format structure."""
        p = ResolvedPalette(
            colors=["#FFFFFF", "#FF0000", "#00FF00"],
            active_slots=[1],
            music_sparkles=True,
        )
        s = build_palette_string(p)

        # Should start with C_BUTTON entries
        assert s.startswith("C_BUTTON_Palette1=")
        # Should have exactly one checkbox
        parts = s.split(",")
        checkbox_parts = [p for p in parts if "C_CHECKBOX_Palette" in p]
        assert len(checkbox_parts) == 1
        assert checkbox_parts[0] == "C_CHECKBOX_Palette1=1"
