"""Unit tests for SettingsStringBuilder."""

from __future__ import annotations

from twinklr.core.sequencer.display.effects.settings_builder import (
    SettingsStringBuilder,
)


class TestSettingsStringBuilder:
    """Tests for the base SettingsStringBuilder functionality."""

    def test_basic_build(self) -> None:
        """Simple key=value pairs are joined by commas."""
        b = SettingsStringBuilder()
        b.add("E_SLIDER_Speed", 50)
        b.add("E_CHECKBOX_Mirror", 0)
        result = b.build()
        assert result == "E_SLIDER_Speed=50,E_CHECKBOX_Mirror=0"

    def test_empty_build(self) -> None:
        """Empty builder produces empty string."""
        assert SettingsStringBuilder().build() == ""

    def test_add_if_true(self) -> None:
        """add_if includes key when condition is True."""
        b = SettingsStringBuilder()
        b.add_if("E_SLIDER_Speed", 50, True)
        assert "E_SLIDER_Speed=50" in b.build()

    def test_add_if_false(self) -> None:
        """add_if omits key when condition is False."""
        b = SettingsStringBuilder()
        b.add_if("E_SLIDER_Speed", 50, False)
        assert b.build() == ""


class TestFadeInKeys:
    """Tests for fade-in transition key generation."""

    def test_basic_fade_in(self) -> None:
        """Fade-in adds Fadein time and transition type."""
        b = SettingsStringBuilder()
        b.add_fade_in(seconds=1.0)
        result = b.build()
        assert "T_TEXTCTRL_Fadein=1.00" in result
        assert "T_CHOICE_In_Transition_Type=Fade" in result

    def test_fade_in_with_adjust(self) -> None:
        """Fade-in with adjust parameter includes slider value."""
        b = SettingsStringBuilder()
        b.add_fade_in(seconds=0.50, adjust=75)
        result = b.build()
        assert "T_TEXTCTRL_Fadein=0.50" in result
        assert "T_SLIDER_In_Transition_Adjust=75" in result

    def test_fade_in_with_reverse(self) -> None:
        """Fade-in with reverse includes the checkbox."""
        b = SettingsStringBuilder()
        b.add_fade_in(seconds=0.30, reverse=True)
        result = b.build()
        assert "T_CHECKBOX_In_Transition_Reverse=1" in result

    def test_fade_in_custom_type(self) -> None:
        """Fade-in can use a non-Fade transition type (e.g., Wipe)."""
        b = SettingsStringBuilder()
        b.add_fade_in(seconds=0.50, transition_type="Wipe")
        result = b.build()
        assert "T_CHOICE_In_Transition_Type=Wipe" in result

    def test_fade_in_no_reverse_omits_checkbox(self) -> None:
        """When reverse is False, no checkbox key is emitted."""
        b = SettingsStringBuilder()
        b.add_fade_in(seconds=0.50, reverse=False)
        result = b.build()
        assert "T_CHECKBOX_In_Transition_Reverse" not in result

    def test_fade_in_no_adjust_omits_slider(self) -> None:
        """When adjust is None, no slider key is emitted."""
        b = SettingsStringBuilder()
        b.add_fade_in(seconds=0.50, adjust=None)
        result = b.build()
        assert "T_SLIDER_In_Transition_Adjust" not in result


class TestFadeOutKeys:
    """Tests for fade-out transition key generation."""

    def test_basic_fade_out(self) -> None:
        """Fade-out adds Fadeout time and transition type."""
        b = SettingsStringBuilder()
        b.add_fade_out(seconds=0.50)
        result = b.build()
        assert "T_TEXTCTRL_Fadeout=0.50" in result
        assert "T_CHOICE_Out_Transition_Type=Fade" in result

    def test_fade_out_with_adjust(self) -> None:
        """Fade-out with adjust includes the slider value."""
        b = SettingsStringBuilder()
        b.add_fade_out(seconds=0.20, adjust=50)
        result = b.build()
        assert "T_TEXTCTRL_Fadeout=0.20" in result
        assert "T_SLIDER_Out_Transition_Adjust=50" in result

    def test_fade_out_with_reverse(self) -> None:
        """Fade-out with reverse includes the checkbox."""
        b = SettingsStringBuilder()
        b.add_fade_out(seconds=0.30, reverse=True)
        result = b.build()
        assert "T_CHECKBOX_Out_Transition_Reverse=1" in result


class TestFadeChaining:
    """Tests for combining fade-in + fade-out with effect params."""

    def test_fade_in_and_out_combined(self) -> None:
        """Both fade-in and fade-out can be added to the same builder."""
        b = SettingsStringBuilder()
        b.add("E_SLIDER_Speed", 50)
        b.add_fade_in(seconds=1.00)
        b.add_fade_out(seconds=0.50)
        result = b.build()

        assert "E_SLIDER_Speed=50" in result
        assert "T_TEXTCTRL_Fadein=1.00" in result
        assert "T_TEXTCTRL_Fadeout=0.50" in result

    def test_full_settings_string(self) -> None:
        """Complete settings string with effect, buffer, and transition keys."""
        b = SettingsStringBuilder()
        b.add("E_SLIDER_Speed", 50)
        b.add_buffer_style("Per Model Default")
        b.add_layer_method("Max")
        b.add_fade_in(seconds=0.30)
        b.add_fade_out(seconds=0.20)
        result = b.build()

        parts = result.split(",")
        assert len(parts) == 7  # E_ + B_ + T_LayerMethod + 2 fadein + 2 fadeout

    def test_fluent_chaining(self) -> None:
        """Builder methods return self for chaining."""
        result = (
            SettingsStringBuilder()
            .add("E_SLIDER_Speed", 50)
            .add_fade_in(seconds=0.30)
            .add_fade_out(seconds=0.20)
            .build()
        )
        assert "E_SLIDER_Speed=50" in result
        assert "T_TEXTCTRL_Fadein=0.30" in result
        assert "T_TEXTCTRL_Fadeout=0.20" in result
