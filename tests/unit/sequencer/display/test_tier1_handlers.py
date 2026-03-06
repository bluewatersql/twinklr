"""Unit tests for Phase 09 Tier 1 effect handlers."""

from __future__ import annotations

from twinklr.core.sequencer.display.effects.protocol import (
    EffectSettings,
    RenderContext,
)
from twinklr.core.sequencer.display.models.palette import ResolvedPalette
from twinklr.core.sequencer.display.models.render_event import (
    RenderEvent,
    RenderEventSource,
)
from twinklr.core.sequencer.vocabulary import LaneKind

# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


def _make_event(effect_type: str, parameters: dict | None = None) -> RenderEvent:
    """Build a minimal RenderEvent for handler testing."""
    return RenderEvent(
        event_id="test-evt-001",
        start_ms=0,
        end_ms=1000,
        effect_type=effect_type,
        parameters=parameters or {},
        buffer_style="Per Model Default",
        buffer_transform=None,
        palette=ResolvedPalette(colors=["#FF0000", "#00FF00", "#0000FF"], active_slots=[1, 2, 3]),
        source=RenderEventSource(
            section_id="s1",
            lane=LaneKind.BASE,
            group_id="g1",
            template_id="tpl1",
        ),
    )


def _make_ctx() -> RenderContext:
    return RenderContext(sequence_duration_ms=60000)


# ---------------------------------------------------------------------------
# BarsHandler
# ---------------------------------------------------------------------------


class TestBarsHandler:
    """Tests for BarsHandler."""

    def test_bars_handler_effect_type(self) -> None:
        from twinklr.core.sequencer.display.effects.handlers.bars_handler import BarsHandler

        h = BarsHandler()
        assert h.effect_type == "Bars"

    def test_bars_handler_build_settings(self) -> None:
        from twinklr.core.sequencer.display.effects.handlers.bars_handler import BarsHandler

        h = BarsHandler()
        event = _make_event("Bars")
        result = h.build_settings(event, _make_ctx())
        assert isinstance(result, EffectSettings)
        assert result.effect_name == "Bars"
        assert "B_CHOICE_BufferStyle" in result.settings_string

    def test_bars_handler_explicit_params(self) -> None:
        from twinklr.core.sequencer.display.effects.handlers.bars_handler import BarsHandler

        h = BarsHandler()
        event = _make_event("Bars", {"bar_count": 10, "direction": "Right", "highlight": True})
        result = h.build_settings(event, _make_ctx())
        assert "E_SLIDER_Bars_BarCount=10" in result.settings_string
        assert "E_CHOICE_Bars_Direction=Right" in result.settings_string

    def test_bars_handler_registered(self) -> None:
        from twinklr.core.sequencer.display.effects.handlers import load_builtin_handlers

        registry = load_builtin_handlers()
        assert registry.get("Bars") is not None


# ---------------------------------------------------------------------------
# ButterflyHandler
# ---------------------------------------------------------------------------


class TestButterflyHandler:
    """Tests for ButterflyHandler."""

    def test_butterfly_handler_effect_type(self) -> None:
        from twinklr.core.sequencer.display.effects.handlers.butterfly_handler import (
            ButterflyHandler,
        )

        h = ButterflyHandler()
        assert h.effect_type == "Butterfly"

    def test_butterfly_handler_build_settings(self) -> None:
        from twinklr.core.sequencer.display.effects.handlers.butterfly_handler import (
            ButterflyHandler,
        )

        h = ButterflyHandler()
        result = h.build_settings(_make_event("Butterfly"), _make_ctx())
        assert isinstance(result, EffectSettings)
        assert result.effect_name == "Butterfly"
        assert "B_CHOICE_BufferStyle" in result.settings_string

    def test_butterfly_handler_registered(self) -> None:
        from twinklr.core.sequencer.display.effects.handlers import load_builtin_handlers

        registry = load_builtin_handlers()
        assert registry.get("Butterfly") is not None


# ---------------------------------------------------------------------------
# CirclesHandler
# ---------------------------------------------------------------------------


class TestCirclesHandler:
    """Tests for CirclesHandler."""

    def test_circles_handler_effect_type(self) -> None:
        from twinklr.core.sequencer.display.effects.handlers.circles_handler import CirclesHandler

        h = CirclesHandler()
        assert h.effect_type == "Circles"

    def test_circles_handler_build_settings(self) -> None:
        from twinklr.core.sequencer.display.effects.handlers.circles_handler import CirclesHandler

        h = CirclesHandler()
        result = h.build_settings(_make_event("Circles"), _make_ctx())
        assert isinstance(result, EffectSettings)
        assert result.effect_name == "Circles"
        assert "B_CHOICE_BufferStyle" in result.settings_string

    def test_circles_handler_registered(self) -> None:
        from twinklr.core.sequencer.display.effects.handlers import load_builtin_handlers

        registry = load_builtin_handlers()
        assert registry.get("Circles") is not None


# ---------------------------------------------------------------------------
# LightningHandler
# ---------------------------------------------------------------------------


class TestLightningHandler:
    """Tests for LightningHandler."""

    def test_lightning_handler_effect_type(self) -> None:
        from twinklr.core.sequencer.display.effects.handlers.lightning_handler import (
            LightningHandler,
        )

        h = LightningHandler()
        assert h.effect_type == "Lightning"

    def test_lightning_handler_build_settings(self) -> None:
        from twinklr.core.sequencer.display.effects.handlers.lightning_handler import (
            LightningHandler,
        )

        h = LightningHandler()
        result = h.build_settings(_make_event("Lightning"), _make_ctx())
        assert isinstance(result, EffectSettings)
        assert result.effect_name == "Lightning"
        assert "B_CHOICE_BufferStyle" in result.settings_string

    def test_lightning_handler_registered(self) -> None:
        from twinklr.core.sequencer.display.effects.handlers import load_builtin_handlers

        registry = load_builtin_handlers()
        assert registry.get("Lightning") is not None


# ---------------------------------------------------------------------------
# MorphHandler
# ---------------------------------------------------------------------------


class TestMorphHandler:
    """Tests for MorphHandler."""

    def test_morph_handler_effect_type(self) -> None:
        from twinklr.core.sequencer.display.effects.handlers.morph_handler import MorphHandler

        h = MorphHandler()
        assert h.effect_type == "Morph"

    def test_morph_handler_build_settings(self) -> None:
        from twinklr.core.sequencer.display.effects.handlers.morph_handler import MorphHandler

        h = MorphHandler()
        result = h.build_settings(_make_event("Morph"), _make_ctx())
        assert isinstance(result, EffectSettings)
        assert result.effect_name == "Morph"
        assert "B_CHOICE_BufferStyle" in result.settings_string

    def test_morph_handler_registered(self) -> None:
        from twinklr.core.sequencer.display.effects.handlers import load_builtin_handlers

        registry = load_builtin_handlers()
        assert registry.get("Morph") is not None


# ---------------------------------------------------------------------------
# ShimmerHandler
# ---------------------------------------------------------------------------


class TestShimmerHandler:
    """Tests for ShimmerHandler."""

    def test_shimmer_handler_effect_type(self) -> None:
        from twinklr.core.sequencer.display.effects.handlers.shimmer_handler import ShimmerHandler

        h = ShimmerHandler()
        assert h.effect_type == "Shimmer"

    def test_shimmer_handler_build_settings(self) -> None:
        from twinklr.core.sequencer.display.effects.handlers.shimmer_handler import ShimmerHandler

        h = ShimmerHandler()
        result = h.build_settings(_make_event("Shimmer"), _make_ctx())
        assert isinstance(result, EffectSettings)
        assert result.effect_name == "Shimmer"
        assert "B_CHOICE_BufferStyle" in result.settings_string

    def test_shimmer_handler_registered(self) -> None:
        from twinklr.core.sequencer.display.effects.handlers import load_builtin_handlers

        registry = load_builtin_handlers()
        assert registry.get("Shimmer") is not None


# ---------------------------------------------------------------------------
# WaveHandler
# ---------------------------------------------------------------------------


class TestWaveHandler:
    """Tests for WaveHandler."""

    def test_wave_handler_effect_type(self) -> None:
        from twinklr.core.sequencer.display.effects.handlers.wave_handler import WaveHandler

        h = WaveHandler()
        assert h.effect_type == "Wave"

    def test_wave_handler_build_settings(self) -> None:
        from twinklr.core.sequencer.display.effects.handlers.wave_handler import WaveHandler

        h = WaveHandler()
        result = h.build_settings(_make_event("Wave"), _make_ctx())
        assert isinstance(result, EffectSettings)
        assert result.effect_name == "Wave"
        assert "B_CHOICE_BufferStyle" in result.settings_string

    def test_wave_handler_registered(self) -> None:
        from twinklr.core.sequencer.display.effects.handlers import load_builtin_handlers

        registry = load_builtin_handlers()
        assert registry.get("Wave") is not None


# ---------------------------------------------------------------------------
# WarpHandler
# ---------------------------------------------------------------------------


class TestWarpHandler:
    """Tests for WarpHandler."""

    def test_warp_handler_effect_type(self) -> None:
        from twinklr.core.sequencer.display.effects.handlers.warp_handler import WarpHandler

        h = WarpHandler()
        assert h.effect_type == "Warp"

    def test_warp_handler_build_settings(self) -> None:
        from twinklr.core.sequencer.display.effects.handlers.warp_handler import WarpHandler

        h = WarpHandler()
        result = h.build_settings(_make_event("Warp"), _make_ctx())
        assert isinstance(result, EffectSettings)
        assert result.effect_name == "Warp"
        assert "B_CHOICE_BufferStyle" in result.settings_string

    def test_warp_handler_registered(self) -> None:
        from twinklr.core.sequencer.display.effects.handlers import load_builtin_handlers

        registry = load_builtin_handlers()
        assert registry.get("Warp") is not None


# ---------------------------------------------------------------------------
# FireworksHandler
# ---------------------------------------------------------------------------


class TestFireworksHandler:
    """Tests for FireworksHandler."""

    def test_fireworks_handler_effect_type(self) -> None:
        from twinklr.core.sequencer.display.effects.handlers.fireworks_handler import (
            FireworksHandler,
        )

        h = FireworksHandler()
        assert h.effect_type == "Fireworks"

    def test_fireworks_handler_build_settings(self) -> None:
        from twinklr.core.sequencer.display.effects.handlers.fireworks_handler import (
            FireworksHandler,
        )

        h = FireworksHandler()
        result = h.build_settings(_make_event("Fireworks"), _make_ctx())
        assert isinstance(result, EffectSettings)
        assert result.effect_name == "Fireworks"
        assert "B_CHOICE_BufferStyle" in result.settings_string

    def test_fireworks_handler_registered(self) -> None:
        from twinklr.core.sequencer.display.effects.handlers import load_builtin_handlers

        registry = load_builtin_handlers()
        assert registry.get("Fireworks") is not None
