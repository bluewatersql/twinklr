"""Unit tests for P2 effect handlers."""

from __future__ import annotations

from twinklr.core.sequencer.display.effects.handlers.fan import FanHandler
from twinklr.core.sequencer.display.effects.handlers.marquee import (
    MarqueeHandler,
)
from twinklr.core.sequencer.display.effects.handlers.meteors import (
    MeteorsHandler,
)
from twinklr.core.sequencer.display.effects.handlers.shockwave import (
    ShockwaveHandler,
)
from twinklr.core.sequencer.display.effects.handlers.snowflakes import (
    SnowflakesHandler,
)
from twinklr.core.sequencer.display.effects.handlers.strobe import (
    StrobeHandler,
)
from twinklr.core.sequencer.display.effects.handlers.twinkle import (
    TwinkleHandler,
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
        lane=LaneKind.ACCENT,
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


class TestFanHandler:
    """Tests for the FanHandler."""

    def test_effect_type(self) -> None:
        assert FanHandler().effect_type == "Fan"

    def test_default_settings(self) -> None:
        h = FanHandler()
        settings = h.build_settings(_event("Fan"), _ctx())
        assert "E_SLIDER_Fan_Num_Blades=16" in settings.settings_string
        assert "E_SLIDER_Fan_End_Radius=250" in settings.settings_string
        assert settings.effect_name == "Fan"

    def test_custom_params(self) -> None:
        h = FanHandler()
        event = _event("Fan", parameters={"num_blades": 8, "reverse": True})
        settings = h.build_settings(event, _ctx())
        assert "E_SLIDER_Fan_Num_Blades=8" in settings.settings_string
        assert "E_CHECKBOX_Fan_Reverse=1" in settings.settings_string


class TestShockwaveHandler:
    """Tests for the ShockwaveHandler."""

    def test_effect_type(self) -> None:
        assert ShockwaveHandler().effect_type == "Shockwave"

    def test_default_settings(self) -> None:
        h = ShockwaveHandler()
        settings = h.build_settings(_event("Shockwave"), _ctx())
        assert "E_SLIDER_Shockwave_Start_Radius=1" in settings.settings_string
        assert "E_SLIDER_Shockwave_End_Radius=250" in settings.settings_string

    def test_custom_center(self) -> None:
        h = ShockwaveHandler()
        event = _event("Shockwave", parameters={"center_x": 25, "center_y": 75})
        settings = h.build_settings(event, _ctx())
        assert "E_SLIDER_Shockwave_CenterX=25" in settings.settings_string
        assert "E_SLIDER_Shockwave_CenterY=75" in settings.settings_string


class TestStrobeHandler:
    """Tests for the StrobeHandler."""

    def test_effect_type(self) -> None:
        assert StrobeHandler().effect_type == "Strobe"

    def test_default_settings(self) -> None:
        h = StrobeHandler()
        settings = h.build_settings(_event("Strobe"), _ctx())
        assert "E_SLIDER_Number_Strobes=300" in settings.settings_string
        assert "E_CHECKBOX_Strobe_Music=0" in settings.settings_string

    def test_music_reactive(self) -> None:
        h = StrobeHandler()
        event = _event("Strobe", parameters={"music_reactive": True})
        settings = h.build_settings(event, _ctx())
        assert "E_CHECKBOX_Strobe_Music=1" in settings.settings_string


class TestTwinkleHandler:
    """Tests for the TwinkleHandler."""

    def test_effect_type(self) -> None:
        assert TwinkleHandler().effect_type == "Twinkle"

    def test_default_settings(self) -> None:
        h = TwinkleHandler()
        settings = h.build_settings(_event("Twinkle"), _ctx())
        assert "E_SLIDER_Twinkle_Count=3" in settings.settings_string
        assert "E_SLIDER_Twinkle_Steps=30" in settings.settings_string

    def test_strobe_mode(self) -> None:
        h = TwinkleHandler()
        event = _event("Twinkle", parameters={"strobe": True, "count": 10})
        settings = h.build_settings(event, _ctx())
        assert "E_CHECKBOX_Twinkle_Strobe=1" in settings.settings_string
        assert "E_SLIDER_Twinkle_Count=10" in settings.settings_string


class TestSnowflakesHandler:
    """Tests for the SnowflakesHandler."""

    def test_effect_type(self) -> None:
        assert SnowflakesHandler().effect_type == "Snowflakes"

    def test_default_settings(self) -> None:
        h = SnowflakesHandler()
        settings = h.build_settings(_event("Snowflakes"), _ctx())
        assert "E_SLIDER_Snowflakes_Count=100" in settings.settings_string
        assert "E_SLIDER_Snowflakes_Speed=50" in settings.settings_string


class TestMarqueeHandler:
    """Tests for the MarqueeHandler."""

    def test_effect_type(self) -> None:
        assert MarqueeHandler().effect_type == "Marquee"

    def test_default_settings(self) -> None:
        h = MarqueeHandler()
        settings = h.build_settings(_event("Marquee"), _ctx())
        assert "E_SLIDER_Marquee_Band_Size=39" in settings.settings_string
        assert "E_SLIDER_Marquee_Speed=50" in settings.settings_string

    def test_reverse(self) -> None:
        h = MarqueeHandler()
        event = _event("Marquee", parameters={"reverse": True})
        settings = h.build_settings(event, _ctx())
        assert "E_CHECKBOX_Marquee_Reverse=1" in settings.settings_string


class TestMeteorsHandler:
    """Tests for the MeteorsHandler."""

    def test_effect_type(self) -> None:
        assert MeteorsHandler().effect_type == "Meteors"

    def test_default_settings(self) -> None:
        h = MeteorsHandler()
        settings = h.build_settings(_event("Meteors"), _ctx())
        assert "E_SLIDER_Meteors_Count=10" in settings.settings_string
        assert "E_CHOICE_Meteors_Effect=Down" in settings.settings_string

    def test_custom_direction(self) -> None:
        h = MeteorsHandler()
        event = _event("Meteors", parameters={"direction": "Up", "count": 50})
        settings = h.build_settings(event, _ctx())
        assert "E_CHOICE_Meteors_Effect=Up" in settings.settings_string
        assert "E_SLIDER_Meteors_Count=50" in settings.settings_string
