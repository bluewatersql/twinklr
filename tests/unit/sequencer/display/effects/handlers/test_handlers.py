"""Unit tests for P1 effect handlers."""

from __future__ import annotations

from twinklr.core.sequencer.display.effects.handlers.chase import ChaseHandler
from twinklr.core.sequencer.display.effects.handlers.color_wash import (
    ColorWashHandler,
)
from twinklr.core.sequencer.display.effects.handlers.on import OnHandler
from twinklr.core.sequencer.display.effects.handlers.pictures import (
    PicturesHandler,
)
from twinklr.core.sequencer.display.effects.handlers.spirals import (
    SpiralsHandler,
)
from twinklr.core.sequencer.display.effects.protocol import RenderContext
from twinklr.core.sequencer.display.models.palette import ResolvedPalette
from twinklr.core.sequencer.display.models.render_event import (
    RenderEvent,
    RenderEventSource,
)
from twinklr.core.sequencer.vocabulary import LaneKind


def _palette() -> ResolvedPalette:
    return ResolvedPalette(
        colors=["#FF0000", "#00FF00"],
        active_slots=[1, 2],
    )


def _source() -> RenderEventSource:
    return RenderEventSource(
        section_id="test",
        lane=LaneKind.BASE,
        group_id="G1",
        template_id="test_template",
    )


def _ctx() -> RenderContext:
    return RenderContext(sequence_duration_ms=120000)


def _event(
    effect_type: str,
    intensity: float = 1.0,
    parameters: dict | None = None,
) -> RenderEvent:
    return RenderEvent(
        event_id="test_1",
        start_ms=0,
        end_ms=4000,
        effect_type=effect_type,
        parameters=parameters or {},
        palette=_palette(),
        intensity=intensity,
        source=_source(),
    )


class TestOnHandler:
    """Tests for the OnHandler."""

    def test_effect_type(self) -> None:
        assert OnHandler().effect_type == "On"

    def test_full_intensity(self) -> None:
        h = OnHandler()
        settings = h.build_settings(_event("On", intensity=1.0), _ctx())
        assert "E_TEXTCTRL_Eff_On_End=100" in settings.settings_string
        assert "E_TEXTCTRL_Eff_On_Start=100" in settings.settings_string

    def test_half_intensity(self) -> None:
        h = OnHandler()
        settings = h.build_settings(_event("On", intensity=0.5), _ctx())
        assert "E_TEXTCTRL_Eff_On_End=50" in settings.settings_string

    def test_includes_buffer_style(self) -> None:
        h = OnHandler()
        settings = h.build_settings(_event("On"), _ctx())
        assert "B_CHOICE_BufferStyle=Per Model Default" in settings.settings_string


class TestColorWashHandler:
    """Tests for the ColorWashHandler."""

    def test_effect_type(self) -> None:
        assert ColorWashHandler().effect_type == "Color Wash"

    def test_default_settings(self) -> None:
        h = ColorWashHandler()
        settings = h.build_settings(_event("Color Wash"), _ctx())
        assert "E_CHECKBOX_ColorWash_HFade=1" in settings.settings_string
        assert "E_CHECKBOX_ColorWash_VFade=0" in settings.settings_string

    def test_custom_params(self) -> None:
        h = ColorWashHandler()
        event = _event(
            "Color Wash",
            parameters={"shimmer": True, "speed": 75},
        )
        settings = h.build_settings(event, _ctx())
        assert "E_CHECKBOX_ColorWash_Shimmer=1" in settings.settings_string
        assert "E_SLIDER_ColorWash_Speed=75" in settings.settings_string


class TestChaseHandler:
    """Tests for the ChaseHandler (SingleStrand)."""

    def test_effect_type(self) -> None:
        assert ChaseHandler().effect_type == "SingleStrand"

    def test_default_settings(self) -> None:
        h = ChaseHandler()
        settings = h.build_settings(_event("SingleStrand"), _ctx())
        assert "E_CHOICE_Chase_Type1=Left-Right" in settings.settings_string
        assert "E_SLIDER_Chase_Speed1=50" in settings.settings_string

    def test_custom_chase_type(self) -> None:
        h = ChaseHandler()
        event = _event(
            "SingleStrand",
            parameters={"chase_type": "Bounce from Left"},
        )
        settings = h.build_settings(event, _ctx())
        assert "E_CHOICE_Chase_Type1=Bounce from Left" in settings.settings_string


class TestSpiralsHandler:
    """Tests for the SpiralsHandler."""

    def test_effect_type(self) -> None:
        assert SpiralsHandler().effect_type == "Spirals"

    def test_default_settings(self) -> None:
        h = SpiralsHandler()
        settings = h.build_settings(_event("Spirals"), _ctx())
        assert "E_SLIDER_Spirals_Count=3" in settings.settings_string
        assert "E_SLIDER_Spirals_Thickness=50" in settings.settings_string

    def test_custom_params(self) -> None:
        h = SpiralsHandler()
        event = _event(
            "Spirals",
            parameters={"palette_count": 5, "blend": True},
        )
        settings = h.build_settings(event, _ctx())
        assert "E_SLIDER_Spirals_Count=5" in settings.settings_string
        assert "E_CHECKBOX_Spirals_Blend=1" in settings.settings_string


class TestPicturesHandler:
    """Tests for the PicturesHandler."""

    def test_effect_type(self) -> None:
        assert PicturesHandler().effect_type == "Pictures"

    def test_with_filename(self) -> None:
        h = PicturesHandler()
        event = _event(
            "Pictures",
            parameters={"filename": "cutouts/rudolph.png"},
        )
        settings = h.build_settings(event, _ctx())
        assert "E_FILEPICKER_Pictures_Filename=" in settings.settings_string
        assert "rudolph.png" in settings.settings_string
        assert len(settings.requires_assets) == 1

    def test_missing_file_warning(self) -> None:
        h = PicturesHandler()
        event = _event(
            "Pictures",
            parameters={"filename": "nonexistent/file.png"},
        )
        settings = h.build_settings(event, _ctx())
        assert len(settings.warnings) == 1
        assert "not found" in settings.warnings[0]
