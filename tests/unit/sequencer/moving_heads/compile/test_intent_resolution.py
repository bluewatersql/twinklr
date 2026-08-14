"""Plan intent becomes deterministic template and segment output."""

from __future__ import annotations

from twinklr.core.config.fixtures.dmx import DmxMapping
from twinklr.core.config.fixtures.instances import FixtureConfig, FixtureInstance
from twinklr.core.curves.models import CurvePoint, PointsCurve
from twinklr.core.curves.registry import CurveRegistry
from twinklr.core.sequencer.models.context import (
    FixtureContext,
    SectionRenderIntent,
    TemplateCompileContext,
    TimedChannelIntent,
)
from twinklr.core.sequencer.models.enum import ChannelName, Intensity
from twinklr.core.sequencer.models.template import Color, Gobo, Shutter
from twinklr.core.sequencer.moving_heads.channels.state import FixtureSegment
from twinklr.core.sequencer.moving_heads.compile.intent_resolution import apply_timed_intents
from twinklr.core.sequencer.moving_heads.compile.template_compiler import compile_template
from twinklr.core.sequencer.moving_heads.export.dmx_settings_builder import DmxSettingsBuilder
from twinklr.core.sequencer.moving_heads.handlers.defaults import create_default_registries
from twinklr.core.sequencer.moving_heads.templates import get_template, load_builtin_templates
from twinklr.core.sequencer.timing.beat_grid import BeatGrid


def _fixture(mapping: DmxMapping) -> tuple[FixtureInstance, FixtureContext]:
    config = FixtureConfig(fixture_id="MH1", dmx_mapping=mapping)
    instance = FixtureInstance(fixture_id="MH1", config=config, xlights_model_name="Dmx MH1")
    return instance, FixtureContext(
        fixture_id="MH1", role="CENTER", calibration={"fixture_config": config}
    )


def _segment() -> FixtureSegment:
    segment = FixtureSegment(
        section_id="chorus",
        segment_id="A",
        step_id="main",
        template_id="synthetic",
        fixture_id="MH1",
        t0_ms=0,
        t1_ms=4000,
    )
    points = [CurvePoint(t=0.0, v=1.0), CurvePoint(t=1.0, v=1.0)]
    segment.add_channel(ChannelName.DIMMER, curve=PointsCurve(points=points), value_points=points)
    return segment


def _context(fixture: FixtureContext, intent: SectionRenderIntent) -> TemplateCompileContext:
    registries = create_default_registries()
    return TemplateCompileContext(
        section_id="chorus",
        template_id="synthetic",
        fixtures=[fixture],
        beat_grid=BeatGrid.from_tempo(tempo_bpm=120, total_bars=4),
        start_bar=1,
        duration_bars=2,
        curve_registry=CurveRegistry(),
        geometry_registry=registries["geometry"],
        movement_registry=registries["movement"],
        dimmer_registry=registries["dimmer"],
        color_registry=registries["color"],
        shutter_registry=registries["shutter"],
        gobo_registry=registries["gobo"],
        intent=intent,
    )


def test_shutter_event_splits_at_authoritative_grid_time_and_persists() -> None:
    mapping = DmxMapping(pan_channel=1, tilt_channel=2, dimmer_channel=3, shutter_channel=6)
    _, fixture = _fixture(mapping)
    intent = SectionRenderIntent(
        intensity=Intensity.INTENSE,
        shutter_events=[TimedChannelIntent(at_ms=1000, pattern_id="strobe_fast")],
    )

    pieces = apply_timed_intents([_segment()], _context(fixture, intent))

    assert [(piece.t0_ms, piece.t1_ms) for piece in pieces] == [(0, 1000), (1000, 4000)]
    assert ChannelName.SHUTTER not in pieces[0].channels
    assert pieces[1].channels[ChannelName.SHUTTER].static_dmx == 190
    assert pieces[1].metadata["shutter_event_ms"] == "1000"


def test_event_split_preserves_existing_curve_progress() -> None:
    mapping = DmxMapping(pan_channel=1, tilt_channel=2, dimmer_channel=3, shutter_channel=6)
    _, fixture = _fixture(mapping)
    segment = _segment()
    points = [CurvePoint(t=0.0, v=0.0), CurvePoint(t=1.0, v=1.0)]
    segment.channels[ChannelName.DIMMER].curve = PointsCurve(points=points)
    segment.channels[ChannelName.DIMMER].value_points = points
    intent = SectionRenderIntent(
        shutter_events=[TimedChannelIntent(at_ms=1000, pattern_id="strobe_fast")]
    )

    first, second = apply_timed_intents([segment], _context(fixture, intent))

    assert [point.v for point in first.channels[ChannelName.DIMMER].value_points or []] == [
        0.0,
        0.25,
    ]
    assert [point.v for point in second.channels[ChannelName.DIMMER].value_points or []] == [
        0.25,
        1.0,
    ]


def test_shutter_channel_17_intent_is_dropped_with_warning_and_exact_bytes_unchanged() -> None:
    mapping = DmxMapping(
        pan_channel=1,
        tilt_channel=2,
        dimmer_channel=3,
        shutter_channel=17,
        shutter_default=211,
    )
    instance, fixture = _fixture(mapping)
    intent = SectionRenderIntent(
        shutter_events=[TimedChannelIntent(at_ms=0, pattern_id="strobe_fast")]
    )
    original = _segment()
    resolved = apply_timed_intents([original], _context(fixture, intent))[0]

    builder = DmxSettingsBuilder(instance)
    baseline = builder.build_settings_string(original)
    assert builder.build_settings_string(resolved) == baseline
    assert "E_SLIDER_DMX17=211" in baseline
    assert ChannelName.SHUTTER not in resolved.channels
    assert resolved.metadata["shutter_trace"] == (
        "warning:shutter channel 17 outside plan-intent window 1-16; dropped"
    )


def test_wheel_channel_is_static_not_points_curve() -> None:
    mapping = DmxMapping(
        pan_channel=1,
        tilt_channel=2,
        dimmer_channel=3,
        gobo_channel=6,
        gobo_map={"open": 0, "circles": 20},
    )
    _, fixture = _fixture(mapping)
    intent = SectionRenderIntent(gobo_events=[TimedChannelIntent(at_ms=0, pattern_id="circles")])

    resolved = apply_timed_intents([_segment()], _context(fixture, intent))[0]
    channel = resolved.channels[ChannelName.GOBO]

    assert channel.static_dmx == 20
    assert channel.curve is None


def test_template_step_parameterized_axes_compile_to_all_three_channels() -> None:
    mapping = DmxMapping(
        pan_channel=1,
        tilt_channel=2,
        dimmer_channel=3,
        color_channel=4,
        shutter_channel=5,
        gobo_channel=6,
        color_map={"open": 0, "red": 18},
        gobo_map={"open": 0, "circles": 20},
    )
    _, fixture = _fixture(mapping)
    load_builtin_templates()
    original = get_template("sweep_lr_fan_hold").template
    steps = [
        step.model_copy(
            update={
                "color": Color(preset="red"),
                "shutter": Shutter(pattern="open"),
                "gobo": Gobo(pattern="circles"),
            },
            deep=True,
        )
        for step in original.steps
    ]
    template = original.model_copy(update={"steps": steps}, deep=True)

    result = compile_template(template, _context(fixture, SectionRenderIntent()))

    assert result.segments
    for segment in result.segments:
        assert segment.channels[ChannelName.COLOR].static_dmx == 18
        assert segment.channels[ChannelName.SHUTTER].static_dmx == 255
        assert segment.channels[ChannelName.GOBO].static_dmx == 20


def test_builtin_template_capability_proofs_emit_stable_settings() -> None:
    mapping = DmxMapping(
        pan_channel=1,
        tilt_channel=2,
        dimmer_channel=3,
        color_channel=4,
        shutter_channel=5,
        gobo_channel=6,
        color_map={"open": 0, "blue": 108},
        gobo_map={"open": 0, "prism": 120},
    )
    instance, fixture = _fixture(mapping)
    load_builtin_templates()
    expected = {
        "ambient_random_wash": (ChannelName.COLOR, "E_SLIDER_DMX4=108"),
        "figure8_mirror_strobe": (ChannelName.SHUTTER, "E_SLIDER_DMX5=190"),
        "accent_snap_tunnel_hit": (ChannelName.GOBO, "E_SLIDER_DMX6=120"),
    }

    for template_id, (channel, setting) in expected.items():
        result = compile_template(
            get_template(template_id).template,
            _context(fixture, SectionRenderIntent()),
        )
        assert result.segments
        assert all(channel in segment.channels for segment in result.segments)
        assert all(
            setting in DmxSettingsBuilder(instance).build_settings_string(segment)
            for segment in result.segments
        )
