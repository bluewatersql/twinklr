"""Tests for CompiledEffect and TemplateCompileError models."""

from __future__ import annotations

from pydantic import ValidationError
import pytest

from twinklr.core.sequencer.display.composition.models import (
    CompiledEffect,
    TemplateCompileError,
)
from twinklr.core.sequencer.display.models.palette import ResolvedPalette
from twinklr.core.sequencer.display.models.render_event import (
    RenderEvent,
    RenderEventSource,
)
from twinklr.core.sequencer.vocabulary import LaneKind, VisualDepth


def _make_event(
    *,
    effect_type: str = "Color Wash",
    value_curves: dict[str, str] | None = None,
) -> RenderEvent:
    """Build a minimal RenderEvent for testing."""
    return RenderEvent(
        event_id="test-evt-1",
        start_ms=0,
        end_ms=1000,
        effect_type=effect_type,
        palette=ResolvedPalette(colors=["#FF0000"], active_slots=[1]),
        value_curves=value_curves or {},
        source=RenderEventSource(
            section_id="s1",
            lane=LaneKind.BASE,
            group_id="g1",
            template_id="tpl1",
        ),
    )


class TestCompiledEffect:
    """Tests for the CompiledEffect model."""

    def test_basic_construction(self) -> None:
        """CompiledEffect bundles event + visual depth."""
        evt = _make_event()
        ce = CompiledEffect(event=evt, visual_depth=VisualDepth.FOREGROUND)
        assert ce.event.effect_type == "Color Wash"
        assert ce.visual_depth == VisualDepth.FOREGROUND

    def test_frozen(self) -> None:
        """CompiledEffect is immutable."""
        ce = CompiledEffect(
            event=_make_event(),
            visual_depth=VisualDepth.BACKGROUND,
        )
        with pytest.raises(ValidationError):
            ce.visual_depth = VisualDepth.MIDGROUND  # type: ignore[misc]

    def test_value_curves_on_event(self) -> None:
        """RenderEvent carries value_curves through CompiledEffect."""
        curves = {"Speed": "Active=TRUE|Id=ID_VALUECURVE_Speed|Type=Custom|..."}
        evt = _make_event(value_curves=curves)
        ce = CompiledEffect(event=evt, visual_depth=VisualDepth.MIDGROUND)
        assert "Speed" in ce.event.value_curves


class TestTemplateCompileError:
    """Tests for the TemplateCompileError exception."""

    def test_message_format(self) -> None:
        """Error message includes template_id and reason."""
        err = TemplateCompileError(
            template_id="gtpl_foo",
            reason="empty layer_recipe",
        )
        assert "gtpl_foo" in str(err)
        assert "empty layer_recipe" in str(err)

    def test_with_section_and_placement(self) -> None:
        """Error message includes optional section/placement context."""
        err = TemplateCompileError(
            template_id="gtpl_bar",
            reason="unrecognised motif 'disco_ball'",
            section_id="verse_1",
            placement_id="p-42",
        )
        msg = str(err)
        assert "section=verse_1" in msg
        assert "placement=p-42" in msg
        assert "disco_ball" in msg

    def test_attributes_stored(self) -> None:
        """Structured attributes are accessible for programmatic use."""
        err = TemplateCompileError(
            template_id="gtpl_baz",
            reason="not found in registry",
            section_id="chorus_2",
        )
        assert err.template_id == "gtpl_baz"
        assert err.section_id == "chorus_2"
        assert err.placement_id == ""
        assert err.reason == "not found in registry"

    def test_is_exception(self) -> None:
        """TemplateCompileError is a proper Exception subclass."""
        with pytest.raises(TemplateCompileError):
            raise TemplateCompileError(template_id="x", reason="test")
