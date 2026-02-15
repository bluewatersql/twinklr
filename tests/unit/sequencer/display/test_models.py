"""Unit tests for display renderer models."""

from __future__ import annotations

import pytest

from twinklr.core.sequencer.display.models import (
    CompositionConfig,
    GapPolicy,
    OverlapPolicy,
    RenderConfig,
    RenderEvent,
    RenderEventSource,
    RenderGroupPlan,
    RenderLayerPlan,
    RenderPlan,
    ResolvedPalette,
    TransitionPolicy,
    TransitionSpec,
)
from twinklr.core.sequencer.vocabulary import LaneKind

# ---------------------------------------------------------------------------
# ResolvedPalette
# ---------------------------------------------------------------------------


class TestResolvedPalette:
    """Tests for the ResolvedPalette model."""

    def test_basic_palette(self) -> None:
        p = ResolvedPalette(
            colors=["#FF0000", "#00FF00"],
            active_slots=[1, 2],
        )
        assert p.colors == ["#FF0000", "#00FF00"]
        assert p.active_slots == [1, 2]
        assert p.sparkle_frequency is None
        assert p.brightness is None

    def test_full_palette(self) -> None:
        p = ResolvedPalette(
            colors=["#FF0000", "#00FF00", "#0000FF"],
            active_slots=[1, 2, 3],
            sparkle_frequency=50,
            music_sparkles=True,
            brightness=80,
            sparkle_color="#FFFFFF",
            hue_adjust=10,
        )
        assert p.sparkle_frequency == 50
        assert p.music_sparkles is True
        assert p.brightness == 80

    def test_invalid_color_format(self) -> None:
        with pytest.raises(ValueError, match="must be #RRGGBB"):
            ResolvedPalette(colors=["red"], active_slots=[1])

    def test_invalid_slot_index(self) -> None:
        with pytest.raises(ValueError, match="must be 1-8"):
            ResolvedPalette(colors=["#FF0000"], active_slots=[0])

    def test_too_many_colors(self) -> None:
        with pytest.raises(ValueError):
            ResolvedPalette(
                colors=["#FF0000"] * 9,
                active_slots=[1],
            )


# ---------------------------------------------------------------------------
# RenderEvent
# ---------------------------------------------------------------------------


def _make_palette() -> ResolvedPalette:
    return ResolvedPalette(colors=["#FF0000"], active_slots=[1])


def _make_source() -> RenderEventSource:
    return RenderEventSource(
        section_id="intro",
        lane=LaneKind.BASE,
        group_id="OUTLINE_1",
        template_id="gtpl_base_wash_soft",
    )


class TestRenderEvent:
    """Tests for the RenderEvent model."""

    def test_basic_event(self) -> None:
        event = RenderEvent(
            event_id="test_1",
            start_ms=0,
            end_ms=2000,
            effect_type="Color Wash",
            palette=_make_palette(),
            source=_make_source(),
        )
        assert event.duration_ms == 2000
        assert event.effect_type == "Color Wash"
        assert event.intensity == 1.0
        assert event.buffer_style == "Per Model Default"

    def test_event_with_parameters(self) -> None:
        event = RenderEvent(
            event_id="test_2",
            start_ms=1000,
            end_ms=5000,
            effect_type="SingleStrand",
            parameters={"chase_type": "Left-Right", "speed": 75},
            palette=_make_palette(),
            intensity=0.8,
            source=_make_source(),
        )
        assert event.parameters["chase_type"] == "Left-Right"
        assert event.intensity == 0.8
        assert event.duration_ms == 4000


# ---------------------------------------------------------------------------
# RenderPlan
# ---------------------------------------------------------------------------


class TestRenderPlan:
    """Tests for the RenderPlan model."""

    def test_empty_plan(self) -> None:
        plan = RenderPlan(render_id="test", duration_ms=60000)
        assert plan.total_events == 0
        assert plan.element_names == []

    def test_plan_with_events(self) -> None:
        event = RenderEvent(
            event_id="e1",
            start_ms=0,
            end_ms=1000,
            effect_type="On",
            palette=_make_palette(),
            source=_make_source(),
        )
        plan = RenderPlan(
            render_id="test",
            duration_ms=60000,
            groups=[
                RenderGroupPlan(
                    element_name="Outline 1",
                    layers=[
                        RenderLayerPlan(
                            layer_index=0,
                            layer_role=LaneKind.BASE,
                            events=[event],
                        )
                    ],
                )
            ],
        )
        assert plan.total_events == 1
        assert plan.element_names == ["Outline 1"]


# ---------------------------------------------------------------------------
# Config models
# ---------------------------------------------------------------------------


class TestCompositionConfig:
    """Tests for CompositionConfig."""

    def test_defaults(self) -> None:
        cfg = CompositionConfig()
        assert cfg.overlap_policy == OverlapPolicy.TRIM
        assert cfg.gap_policy == GapPolicy.DARK
        assert cfg.transition_policy == TransitionPolicy.CUT
        assert cfg.max_layers_per_element == 5
        assert cfg.default_buffer_style == "Per Model Default"

    def test_custom_config(self) -> None:
        cfg = CompositionConfig(
            overlap_policy=OverlapPolicy.ERROR,
            gap_policy=GapPolicy.FILL_OFF,
            max_layers_per_element=3,
        )
        assert cfg.overlap_policy == OverlapPolicy.ERROR


class TestRenderConfig:
    """Tests for RenderConfig."""

    def test_defaults(self) -> None:
        cfg = RenderConfig()
        assert cfg.frame_interval_ms == 20
        assert cfg.composition.overlap_policy == OverlapPolicy.TRIM


class TestTransitionSpec:
    """Tests for TransitionSpec."""

    def test_defaults(self) -> None:
        t = TransitionSpec()
        assert t.type == "Fade"
        assert t.duration_ms == 500
        assert t.reverse is False

    def test_custom(self) -> None:
        t = TransitionSpec(type="Wipe", duration_ms=1000, reverse=True, adjust=50)
        assert t.type == "Wipe"
        assert t.adjust == 50
