"""Headline P3-T5 artifact: actual DMX + Spirals + chase in one XSequence."""

from __future__ import annotations

import json
from pathlib import Path

from twinklr.core.agents.audio.profile.models import SongSectionRef
from twinklr.core.agents.sequencer.moving_heads.models import ChoreographyPlan, PlanSection
from twinklr.core.config.fixtures import FixtureGroup, FixtureInstance
from twinklr.core.config.fixtures.dmx import DmxMapping
from twinklr.core.config.fixtures.instances import FixtureConfig
from twinklr.core.formats.xlights.sequence.models.xsq import TimeMarker, XSequence
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
from twinklr.core.sequencer.models.enum import ChannelName
from twinklr.core.sequencer.moving_heads.channels.state import ChannelValue, FixtureSegment
from twinklr.core.sequencer.moving_heads.delivery import build_sequence
from twinklr.core.sequencer.moving_heads.handlers.wheels import DefaultColorHandler
from twinklr.core.sequencer.planning.models import (
    CallResponsePair,
    FocalAssignment,
    FocalRole,
    FocalRoleKind,
    MacroPlan,
    MacroSection,
    PaletteRef,
    PaletteRoleRef,
    PaletteStop,
    PaletteTransition,
)
from twinklr.core.sequencer.show_coordination import (
    coordinate_display_render_plan,
    coordinate_moving_head_plan,
    coordinate_moving_head_segments,
)
from twinklr.core.sequencer.templates.group.models.choreography import (
    ChoreographyGraph,
    ChoreoGroup,
)
from twinklr.core.sequencer.templates.group.models.coordination import PlanTarget
from twinklr.core.sequencer.theming import ThemeRef, ThemeScope
from twinklr.core.sequencer.timing.beat_grid import BeatGrid
from twinklr.core.sequencer.vocabulary import (
    ChoreographyStyle,
    CoordinationMode,
    EnergyTarget,
    LaneKind,
    MotionDensity,
    StepUnit,
)
from twinklr.core.sequencer.vocabulary.choreography import ChoreoTag, TargetType

GOLDEN = Path(__file__).resolve().parent / "fixtures" / "combined_show_drop.json"
TRACE_GOLDEN = Path(__file__).resolve().parent / "fixtures" / "combined_show_drop.trace.json"


def _grid() -> BeatGrid:
    beats = [0.0, 500.0, 1100.0, 1600.0, 2200.0, 2700.0, 3300.0, 3800.0, 4400.0]
    return BeatGrid(
        bar_boundaries=[0.0, 2200.0, 4400.0],
        beat_boundaries=beats,
        eighth_boundaries=beats,
        sixteenth_boundaries=beats,
        tempo_bpm=109.0,
        beats_per_bar=4,
        duration_ms=4400,
    )


def _graph() -> ChoreographyGraph:
    return ChoreographyGraph(
        graph_id="combined-golden",
        groups=[
            ChoreoGroup(id="MOVING_HEADS", role="MOVING_HEADS", tags=[ChoreoTag.YARD]),
            ChoreoGroup(id="MEGA_TREE", role="MEGA_TREE", tags=[ChoreoTag.HOUSE]),
            ChoreoGroup(id="YARD_ARCHES", role="ARCH", tags=[ChoreoTag.HOUSE]),
        ],
    )


def _macro() -> MacroPlan:
    display_team = PlanTarget(type=TargetType.ZONE, id=ChoreoTag.HOUSE.value)
    mh_team = PlanTarget(type=TargetType.GROUP, id="MOVING_HEADS")
    return MacroPlan(
        sections=[
            MacroSection(
                section=SongSectionRef(section_id="drop", name="Drop", start_ms=0, end_ms=4400),
                energy_target=EnergyTarget.PEAK,
                motion_density=MotionDensity.BUSY,
                choreography_style=ChoreographyStyle.HYBRID,
                palette_role=PaletteRoleRef(
                    stop_id="drop-red",
                    override=PaletteRef(palette_id="core.ice_neon"),
                ),
                theme=ThemeRef(theme_id="theme.holiday.traditional", scope=ThemeScope.SECTION),
                motif_ids=[],
                focal_roles=[
                    FocalRole(target=display_team, role=FocalRoleKind.LEAD),
                    FocalRole(target=mh_team, role=FocalRoleKind.SUPPORT),
                ],
                call_response_pairs=[
                    CallResponsePair(
                        call=display_team,
                        response=mh_team,
                        step_unit=StepUnit.BEAT,
                        step_duration=1,
                    )
                ],
                coordination_intent=CoordinationMode.CALL_RESPONSE,
                notes="Display calls and moving heads respond on detected irregular beats.",
            )
        ],
        palette_arc=[
            PaletteStop(
                stop_id="drop-red",
                palette=PaletteRef(palette_id="core.christmas_traditional"),
                applies_from_section_id="drop",
                transition=PaletteTransition.CUT,
            )
        ],
        motif_continuity=[],
        focal_arc=[FocalAssignment(section_id="drop", lead_target=display_team)],
    )


def _fixture_group() -> FixtureGroup:
    group = FixtureGroup(group_id="MOVING_HEADS", xlights_group="Moving Heads")
    config = FixtureConfig(
        fixture_id="MH1",
        dmx_start_address=1,
        channel_count=16,
        dmx_mapping=DmxMapping(pan_channel=1, tilt_channel=2, dimmer_channel=3, color_channel=4),
    )
    group.add_fixture(
        FixtureInstance(fixture_id="MH1", config=config, xlights_model_name="Dmx MH1")
    )
    return group


def _event(group_id: str, effect_type: str) -> RenderEvent:
    return RenderEvent(
        event_id=f"{group_id}-{effect_type}",
        start_ms=0,
        end_ms=4400,
        effect_type=effect_type,
        parameters={"rotation": 50, "thickness": 40}
        if effect_type == "Spirals"
        else {"chase_count": 1},
        palette=ResolvedPalette(colors=["#E53935", "#43A047", "#F5F1E8"], active_slots=[1, 2, 3]),
        intensity=0.8,
        source=RenderEventSource(
            section_id="drop",
            lane=LaneKind.BASE,
            group_id=group_id,
            template_id=(
                "gtpl_base_megatree_spirals"
                if effect_type == "Spirals"
                else "gtpl_rhythm_chase_single"
            ),
        ),
    )


def _build_combined() -> tuple[XSequence, dict[str, object]]:
    macro = _macro()
    grid = _grid()
    graph = _graph()
    fixture_group = _fixture_group()
    coordinated_plan = coordinate_moving_head_plan(
        ChoreographyPlan(
            sections=[
                PlanSection(
                    section_name="drop",
                    start_bar=1,
                    end_bar=2,
                    template_id="sweep_lr_fan_hold",
                )
            ],
            overall_strategy="golden",
        ),
        macro,
        grid,
        {"MOVING_HEADS"},
        coordination_graph=graph,
    )
    color_preset = coordinated_plan.sections[0].color_intent.explicit_color
    assert color_preset is not None
    fixture_config = fixture_group.expand_fixtures()[0].config
    color_result = DefaultColorHandler().generate(
        {
            "preset": color_preset.value,
            "calibration": {"fixture_config": fixture_config},
        },
        1,
    )
    assert color_result.static_dmx is not None
    source_segment = FixtureSegment(
        section_id="drop",
        segment_id="sweep",
        step_id="sweep",
        template_id="sweep_lr_fan_hold",
        fixture_id="MH1",
        t0_ms=0,
        t1_ms=4400,
        channels={
            ChannelName.PAN: ChannelValue(channel=ChannelName.PAN, static_dmx=180),
            ChannelName.TILT: ChannelValue(channel=ChannelName.TILT, static_dmx=90),
            ChannelName.DIMMER: ChannelValue(channel=ChannelName.DIMMER, static_dmx=200),
            ChannelName.COLOR: ChannelValue(
                channel=ChannelName.COLOR, static_dmx=color_result.static_dmx
            ),
        },
    )
    mh_segments = coordinate_moving_head_segments(
        [source_segment], macro, grid, graph, moving_head_target_ids={"MOVING_HEADS"}
    )
    sequence = build_sequence(
        mh_segments,
        [TimeMarker(name="drop", time_ms=0, end_time_ms=4400)],
        fixture_group=fixture_group,
        media_file="combined-show.wav",
        duration_ms=4400,
    )
    display_source = RenderPlan(
        render_id="combined-show",
        duration_ms=4400,
        groups=[
            RenderGroupPlan(
                element_name="Mega Tree",
                layers=[
                    RenderLayerPlan(
                        layer_index=0,
                        layer_role=LaneKind.BASE,
                        events=[_event("MEGA_TREE", "Spirals")],
                    )
                ],
            ),
            RenderGroupPlan(
                element_name="Yard Arches",
                layers=[
                    RenderLayerPlan(
                        layer_index=0,
                        layer_role=LaneKind.RHYTHM,
                        events=[_event("YARD_ARCHES", "SingleStrand")],
                    )
                ],
            ),
        ],
    )
    display_plan = coordinate_display_render_plan(
        display_source, macro, grid, graph, moving_head_target_ids={"MOVING_HEADS"}
    )
    write_result = XSQWriter(
        handler_registry=load_builtin_handlers(),
        render_context=RenderContext(sequence_duration_ms=4400),
    ).write(display_plan, sequence)
    trace = {
        "schema_version": "display-xsq-trace.v1",
        "entry_count": len(write_result.trace_entries),
        "fallback_substitutions": write_result.fallback_substitutions,
        "entries": write_result.trace_entries,
    }
    return sequence, trace


def _snapshot(sequence: XSequence) -> dict[str, object]:
    effects: dict[str, dict[str, object]] = {}
    for element in sequence.element_effects:
        for layer in element.layers:
            for effect in layer.effects:
                assert effect.ref is not None
                current = effects.setdefault(
                    element.element_name,
                    {
                        "type": effect.effect_type,
                        "ranges": [],
                        "settings": sequence.effect_db.entries[effect.ref],
                        "palette": (
                            sequence.color_palettes[int(effect.palette)].settings
                            if effect.palette
                            else None
                        ),
                    },
                )
                assert current["type"] == effect.effect_type
                assert current["settings"] == sequence.effect_db.entries[effect.ref]
                current["ranges"].append([effect.start_time_ms, effect.end_time_ms])
    return {
        "media_file": sequence.head.media_file,
        "duration_ms": sequence.sequence_duration_ms,
        "effects": effects,
    }


def test_combined_show_drop_matches_emitted_golden() -> None:
    sequence, trace = _build_combined()
    actual = _snapshot(sequence)
    expected = json.loads(GOLDEN.read_text(encoding="utf-8"))
    assert actual == expected
    assert trace == json.loads(TRACE_GOLDEN.read_text(encoding="utf-8"))

    by_element = actual["effects"]
    assert by_element["Dmx MH1"]["type"] == "DMX"
    assert "E_SLIDER_DMX1=180" in by_element["Dmx MH1"]["settings"]
    assert "E_SLIDER_DMX2=90" in by_element["Dmx MH1"]["settings"]
    assert "E_SLIDER_DMX4=90" in by_element["Dmx MH1"]["settings"]
    assert by_element["Mega Tree"]["type"] == "Spirals"
    assert by_element["Yard Arches"]["type"] == "SingleStrand"
    assert by_element["Mega Tree"]["palette"] == by_element["Yard Arches"]["palette"]
    assert "C_BUTTON_Palette1=#00E5FF" in by_element["Mega Tree"]["palette"]
    display_ranges = {
        tuple(item)
        for element, details in by_element.items()
        if element != "Dmx MH1"
        for item in details["ranges"]
    }
    mh_ranges = {tuple(item) for item in by_element["Dmx MH1"]["ranges"]}
    assert all(
        display_end <= mh_start or mh_end <= display_start
        for display_start, display_end in display_ranges
        for mh_start, mh_end in mh_ranges
    )
