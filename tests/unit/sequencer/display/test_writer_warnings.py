"""P3-T2 structured effect-fallback observability tests."""

from __future__ import annotations

from twinklr.core.formats.xlights.sequence.models.xsq import SequenceHead, XSequence
from twinklr.core.sequencer.display.effects.handlers import load_builtin_handlers
from twinklr.core.sequencer.display.effects.protocol import RenderContext
from twinklr.core.sequencer.display.export.writer import XSQWriter
from twinklr.core.sequencer.display.models.palette import ResolvedPalette
from twinklr.core.sequencer.display.models.render_event import RenderEvent, RenderEventSource
from twinklr.core.sequencer.display.models.render_plan import (
    RenderGroupPlan,
    RenderLayerPlan,
    RenderPlan,
)
from twinklr.core.sequencer.display.renderer import (
    RenderResult,
    build_display_xsq_trace_sidecar_payload,
)
from twinklr.core.sequencer.vocabulary import LaneKind


def test_fallback_surfaces_in_write_result_and_trace() -> None:
    event = RenderEvent(
        event_id="unknown-event",
        start_ms=0,
        end_ms=1000,
        effect_type="Invented Sparkle",
        palette=ResolvedPalette(colors=["#FFFFFF"], active_slots=[1]),
        source=RenderEventSource(
            section_id="intro",
            lane=LaneKind.BASE,
            group_id="G0",
            template_id="recipe_invented",
            placement_id="p1",
        ),
    )
    plan = RenderPlan(
        render_id="fallback-test",
        duration_ms=1000,
        groups=[
            RenderGroupPlan(
                element_name="G0",
                layers=[RenderLayerPlan(layer_index=0, layer_role=LaneKind.BASE, events=[event])],
            )
        ],
    )
    sequence = XSequence(
        head=SequenceHead(
            version="2024.01",
            author="test",
            song="test",
            sequence_timing="20 ms",
            media_file="",
            sequence_duration_ms=1000,
        )
    )
    writer = XSQWriter(
        handler_registry=load_builtin_handlers(),
        render_context=RenderContext(sequence_duration_ms=1000),
    )

    result = writer.write(plan, sequence)

    assert result.fallback_substitutions == 1
    assert any("Invented Sparkle" in warning and "On" in warning for warning in result.warnings)
    assert result.trace_entries[0]["fallback_substitution"] == {
        "requested_effect_type": "Invented Sparkle",
        "substituted_effect_type": "On",
        "reason": "unregistered effect type",
    }
    render_result = RenderResult(
        render_plan=plan,
        warnings=result.warnings,
        xsq_trace_entries=result.trace_entries,
        fallback_substitutions=result.fallback_substitutions,
    )
    assert render_result.fallback_substitutions == 1
    assert build_display_xsq_trace_sidecar_payload(render_result)["fallback_substitutions"] == 1
