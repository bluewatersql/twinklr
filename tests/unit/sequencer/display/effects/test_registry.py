"""Unit tests for the HandlerRegistry."""

from __future__ import annotations

import pytest

from twinklr.core.sequencer.display.effects.handlers import load_builtin_handlers
from twinklr.core.sequencer.display.effects.handlers.on import OnHandler
from twinklr.core.sequencer.display.effects.protocol import (
    RenderContext,
)
from twinklr.core.sequencer.display.effects.registry import HandlerRegistry
from twinklr.core.sequencer.display.models.palette import ResolvedPalette
from twinklr.core.sequencer.display.models.render_event import (
    RenderEvent,
    RenderEventSource,
)
from twinklr.core.sequencer.vocabulary import LaneKind


def _make_event(effect_type: str = "On") -> RenderEvent:
    return RenderEvent(
        event_id="test_1",
        start_ms=0,
        end_ms=1000,
        effect_type=effect_type,
        palette=ResolvedPalette(colors=["#FF0000"], active_slots=[1]),
        source=RenderEventSource(
            section_id="intro",
            lane=LaneKind.BASE,
            group_id="G1",
            template_id="test",
        ),
    )


def _make_ctx() -> RenderContext:
    return RenderContext(sequence_duration_ms=60000)


class TestHandlerRegistry:
    """Tests for the HandlerRegistry."""

    def test_register_and_dispatch(self) -> None:
        reg = HandlerRegistry()
        reg.register(OnHandler())
        event = _make_event("On")
        settings = reg.dispatch(event, _make_ctx())
        assert settings.effect_name == "On"

    def test_unknown_type_raises_without_default(self) -> None:
        reg = HandlerRegistry()
        event = _make_event("UnknownEffect")
        with pytest.raises(ValueError, match="No handler registered"):
            reg.dispatch(event, _make_ctx())

    def test_default_handler_fallback(self) -> None:
        reg = HandlerRegistry()
        on = OnHandler()
        reg.register(on)
        reg.set_default(on)
        event = _make_event("UnknownEffect")
        settings = reg.dispatch(event, _make_ctx())
        assert settings.effect_name == "On"

    def test_registered_types(self) -> None:
        reg = HandlerRegistry()
        reg.register(OnHandler())
        assert "On" in reg.registered_types

    def test_len(self) -> None:
        reg = HandlerRegistry()
        assert len(reg) == 0
        reg.register(OnHandler())
        assert len(reg) == 1


class TestLoadBuiltinHandlers:
    """Tests for the load_builtin_handlers factory."""

    def test_loads_all_handlers(self) -> None:
        reg = load_builtin_handlers()
        expected = {
            "On",
            "Color Wash",
            "SingleStrand",
            "Spirals",
            "Pictures",
            "Fan",
            "Shockwave",
            "Strobe",
            "Twinkle",
            "Snowflakes",
            "Marquee",
            "Meteors",
            "Ripple",
            "Fire",
            "Pinwheel",
        }
        assert set(reg.registered_types) == expected

    def test_default_set(self) -> None:
        reg = load_builtin_handlers()
        # Unknown should fall back to On
        event = _make_event("Galaxy")
        settings = reg.dispatch(event, _make_ctx())
        assert settings.effect_name == "On"
