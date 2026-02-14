"""Unit tests for XSQWriter — transition, blend-mode, and intensity augmentation."""

from __future__ import annotations

from twinklr.core.sequencer.display.export.writer import XSQWriter
from twinklr.core.sequencer.display.models.palette import (
    ResolvedPalette,
    TransitionSpec,
)
from twinklr.core.sequencer.display.models.render_event import (
    RenderEvent,
    RenderEventSource,
)
from twinklr.core.sequencer.vocabulary import LaneKind

_DEFAULT_PALETTE = ResolvedPalette(
    colors=["#FF0000", "#00FF00"],
    active_slots=[1, 2],
)


def _make_event(
    *,
    transition_in: TransitionSpec | None = None,
    transition_out: TransitionSpec | None = None,
    intensity: float = 1.0,
    effect_type: str = "Color Wash",
    palette: ResolvedPalette | None = None,
) -> RenderEvent:
    """Create a minimal RenderEvent for testing augmentation."""
    return RenderEvent(
        event_id="test_evt",
        start_ms=0,
        end_ms=1000,
        effect_type=effect_type,
        parameters={},
        intensity=intensity,
        palette=palette or _DEFAULT_PALETTE,
        transition_in=transition_in,
        transition_out=transition_out,
        source=RenderEventSource(
            section_id="s1",
            lane=LaneKind.BASE,
            group_id="g1",
            template_id="t1",
            placement_index=0,
        ),
    )


class TestAugmentSettings:
    """Tests for XSQWriter._augment_settings static method."""

    def test_no_transitions_no_blend_returns_base(self) -> None:
        """With no transitions and Normal blend on layer 0, base string is returned unchanged."""
        event = _make_event()
        result = XSQWriter._augment_settings(
            "E_SLIDER_Speed=50",
            event=event,
            layer_index=0,
            blend_mode="Normal",
        )
        assert result == "E_SLIDER_Speed=50"

    def test_fade_in_appended(self) -> None:
        """Fade-in transition adds T_TEXTCTRL_Fadein keys."""
        event = _make_event(
            transition_in=TransitionSpec(type="Fade", duration_ms=1000),
        )
        result = XSQWriter._augment_settings(
            "E_SLIDER_Speed=50",
            event=event,
            layer_index=0,
            blend_mode="Normal",
        )
        assert "T_TEXTCTRL_Fadein=1.00" in result
        assert "T_CHOICE_In_Transition_Type=Fade" in result
        # Base settings still present
        assert result.startswith("E_SLIDER_Speed=50")

    def test_fade_out_appended(self) -> None:
        """Fade-out transition adds T_TEXTCTRL_Fadeout keys."""
        event = _make_event(
            transition_out=TransitionSpec(type="Fade", duration_ms=500),
        )
        result = XSQWriter._augment_settings(
            "E_SLIDER_Speed=50",
            event=event,
            layer_index=0,
            blend_mode="Normal",
        )
        assert "T_TEXTCTRL_Fadeout=0.50" in result
        assert "T_CHOICE_Out_Transition_Type=Fade" in result

    def test_both_fades_appended(self) -> None:
        """Both fade-in and fade-out transitions appear in the output."""
        event = _make_event(
            transition_in=TransitionSpec(type="Fade", duration_ms=1000),
            transition_out=TransitionSpec(type="Fade", duration_ms=500),
        )
        result = XSQWriter._augment_settings(
            "E_SLIDER_Speed=50",
            event=event,
            layer_index=0,
            blend_mode="Normal",
        )
        assert "T_TEXTCTRL_Fadein=1.00" in result
        assert "T_TEXTCTRL_Fadeout=0.50" in result

    def test_blend_mode_on_higher_layer(self) -> None:
        """Non-Normal blend mode on layer > 0 adds T_CHOICE_LayerMethod."""
        event = _make_event()
        result = XSQWriter._augment_settings(
            "E_SLIDER_Speed=50",
            event=event,
            layer_index=1,
            blend_mode="Max",
        )
        assert "T_CHOICE_LayerMethod=Max" in result

    def test_blend_mode_normal_on_higher_layer_omitted(self) -> None:
        """Normal blend mode on any layer is omitted (it's the default)."""
        event = _make_event()
        result = XSQWriter._augment_settings(
            "E_SLIDER_Speed=50",
            event=event,
            layer_index=1,
            blend_mode="Normal",
        )
        assert "T_CHOICE_LayerMethod" not in result

    def test_blend_mode_on_base_layer_omitted(self) -> None:
        """Even non-Normal blend mode on layer 0 is omitted (base has nothing to blend with)."""
        event = _make_event()
        result = XSQWriter._augment_settings(
            "E_SLIDER_Speed=50",
            event=event,
            layer_index=0,
            blend_mode="Max",
        )
        assert "T_CHOICE_LayerMethod" not in result

    def test_blend_mode_with_transitions(self) -> None:
        """Blend mode + transitions all appear together."""
        event = _make_event(
            transition_in=TransitionSpec(type="Fade", duration_ms=300),
            transition_out=TransitionSpec(type="Fade", duration_ms=200),
        )
        result = XSQWriter._augment_settings(
            "E_SLIDER_Speed=50",
            event=event,
            layer_index=2,
            blend_mode="1 reveals 2",
        )
        assert "T_CHOICE_LayerMethod=1 reveals 2" in result
        assert "T_TEXTCTRL_Fadein=0.30" in result
        assert "T_TEXTCTRL_Fadeout=0.20" in result

    def test_empty_base_settings(self) -> None:
        """Augmentation works even when base settings string is empty."""
        event = _make_event(
            transition_in=TransitionSpec(type="Fade", duration_ms=500),
        )
        result = XSQWriter._augment_settings(
            "",
            event=event,
            layer_index=0,
            blend_mode="Normal",
        )
        assert result.startswith("T_TEXTCTRL_Fadein=0.50")

    def test_wipe_transition_type(self) -> None:
        """Non-Fade transition types are correctly emitted."""
        event = _make_event(
            transition_in=TransitionSpec(
                type="Wipe", duration_ms=400, adjust=75
            ),
        )
        result = XSQWriter._augment_settings(
            "E_SLIDER_Speed=50",
            event=event,
            layer_index=0,
            blend_mode="Normal",
        )
        assert "T_CHOICE_In_Transition_Type=Wipe" in result
        assert "T_SLIDER_In_Transition_Adjust=75" in result

    def test_reverse_transition(self) -> None:
        """Reversed transitions include the checkbox key."""
        event = _make_event(
            transition_out=TransitionSpec(
                type="Fade", duration_ms=300, reverse=True
            ),
        )
        result = XSQWriter._augment_settings(
            "E_SLIDER_Speed=50",
            event=event,
            layer_index=0,
            blend_mode="Normal",
        )
        assert "T_CHECKBOX_Out_Transition_Reverse=1" in result


class TestApplyIntensityBrightness:
    """Tests for XSQWriter._apply_intensity_brightness.

    Intensity (0.0-1.0) is mapped to xLights C_SLIDER_Brightness
    (0-100) on the palette, providing universal brightness control
    for all non-On effects.
    """

    def test_full_intensity_unchanged(self) -> None:
        """intensity=1.0 leaves palette unchanged (no brightness key)."""
        palette = _DEFAULT_PALETTE
        result = XSQWriter._apply_intensity_brightness(
            palette, intensity=1.0, effect_name="Color Wash"
        )
        assert result.brightness is None  # No brightness override

    def test_half_intensity_sets_brightness_50(self) -> None:
        """intensity=0.5 sets brightness to 50."""
        palette = _DEFAULT_PALETTE
        result = XSQWriter._apply_intensity_brightness(
            palette, intensity=0.5, effect_name="Spirals"
        )
        assert result.brightness == 50

    def test_zero_intensity_sets_brightness_0(self) -> None:
        """intensity=0.0 sets brightness to 0 (blackout)."""
        palette = _DEFAULT_PALETTE
        result = XSQWriter._apply_intensity_brightness(
            palette, intensity=0.0, effect_name="Twinkle"
        )
        assert result.brightness == 0

    def test_quarter_intensity(self) -> None:
        """intensity=0.25 sets brightness to 25."""
        palette = _DEFAULT_PALETTE
        result = XSQWriter._apply_intensity_brightness(
            palette, intensity=0.25, effect_name="Fan"
        )
        assert result.brightness == 25

    def test_on_effect_skipped(self) -> None:
        """On effects are skipped — they handle intensity via E_ keys."""
        palette = _DEFAULT_PALETTE
        result = XSQWriter._apply_intensity_brightness(
            palette, intensity=0.3, effect_name="On"
        )
        assert result.brightness is None  # Unchanged

    def test_composes_with_existing_brightness(self) -> None:
        """If palette already has brightness, intensity multiplies it."""
        palette = ResolvedPalette(
            colors=["#FF0000"],
            active_slots=[1],
            brightness=80,  # Already reduced
        )
        result = XSQWriter._apply_intensity_brightness(
            palette, intensity=0.5, effect_name="Color Wash"
        )
        # 80 * 0.5 = 40
        assert result.brightness == 40

    def test_preserves_other_palette_fields(self) -> None:
        """Non-brightness palette fields are preserved."""
        palette = ResolvedPalette(
            colors=["#FF0000", "#00FF00"],
            active_slots=[1, 2],
            sparkle_frequency=50,
            music_sparkles=True,
        )
        result = XSQWriter._apply_intensity_brightness(
            palette, intensity=0.5, effect_name="Color Wash"
        )
        assert result.brightness == 50
        assert result.sparkle_frequency == 50
        assert result.music_sparkles is True
        assert result.colors == ["#FF0000", "#00FF00"]

    def test_works_for_all_non_on_effect_types(self) -> None:
        """Brightness is applied for every non-On effect type."""
        palette = _DEFAULT_PALETTE
        for effect_name in [
            "Color Wash", "Spirals", "SingleStrand", "Fan",
            "Shockwave", "Strobe", "Twinkle", "Snowflakes",
            "Marquee", "Meteors", "Pictures",
        ]:
            result = XSQWriter._apply_intensity_brightness(
                palette, intensity=0.5, effect_name=effect_name
            )
            assert result.brightness == 50, f"Failed for {effect_name}"
