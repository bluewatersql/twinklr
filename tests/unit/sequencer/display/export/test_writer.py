"""Unit tests for XSQWriter — transition and blend-mode augmentation."""

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


def _make_event(
    *,
    transition_in: TransitionSpec | None = None,
    transition_out: TransitionSpec | None = None,
) -> RenderEvent:
    """Create a minimal RenderEvent for testing augmentation."""
    return RenderEvent(
        event_id="test_evt",
        start_ms=0,
        end_ms=1000,
        effect_type="Color Wash",
        parameters={},
        palette=ResolvedPalette(
            colors=["#FF0000", "#00FF00"],
            active_slots=[1, 2],
        ),
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
