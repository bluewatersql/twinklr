"""Current-schema fixtures shared by public show-evaluation seam tests."""

from __future__ import annotations

from twinklr.core.agents.audio.profile.models import SongSectionRef
from twinklr.core.reporting.evaluation.show_manifest import (
    ShowCapability,
    ShowEvaluationManifest,
    ShowTraceEntry,
    ShowTraceV2,
    identity_sha256,
)
from twinklr.core.sequencer.display.xlights_mapping import (
    XLightsGroupMapping,
    XLightsMapping,
)
from twinklr.core.sequencer.planning import (
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
    MotionDensity,
    StepUnit,
    TargetType,
)


def graph() -> ChoreographyGraph:
    return ChoreographyGraph(
        graph_id="show",
        groups=[
            ChoreoGroup(id="DISPLAY", role="DISPLAY"),
            ChoreoGroup(id="MOVING_HEADS", role="MOVING_HEADS"),
        ],
    )


def mapping() -> XLightsMapping:
    return XLightsMapping(
        entries=[
            XLightsGroupMapping(choreo_id="DISPLAY", group_name="Display Group"),
            XLightsGroupMapping(choreo_id="MOVING_HEADS", group_name="Moving Heads"),
        ]
    )


def macro() -> MacroPlan:
    display = PlanTarget(type=TargetType.GROUP, id="DISPLAY")
    moving = PlanTarget(type=TargetType.GROUP, id="MOVING_HEADS")
    return MacroPlan(
        sections=[
            MacroSection(
                section=SongSectionRef(
                    section_id="section", name="Section", start_ms=0, end_ms=2_000
                ),
                energy_target=EnergyTarget.HIGH,
                motion_density=MotionDensity.BUSY,
                choreography_style=ChoreographyStyle.HYBRID,
                palette_role=PaletteRoleRef(stop_id="palette", override=None),
                theme=ThemeRef(theme_id="theme.holiday.traditional", scope=ThemeScope.SECTION),
                motif_ids=[],
                focal_roles=[
                    FocalRole(target=display, role=FocalRoleKind.LEAD),
                    FocalRole(target=moving, role=FocalRoleKind.SUPPORT),
                ],
                call_response_pairs=[
                    CallResponsePair(
                        call=display,
                        response=moving,
                        step_unit=StepUnit.BEAT,
                        step_duration=1,
                    )
                ],
                coordination_intent=CoordinationMode.CALL_RESPONSE,
                notes="Exchange a clear visual phrase across both rendered parts.",
            )
        ],
        palette_arc=[
            PaletteStop(
                stop_id="palette",
                palette=PaletteRef(palette_id="core.christmas_traditional"),
                applies_from_section_id="section",
                transition=PaletteTransition.CUT,
            )
        ],
        motif_continuity=[],
        focal_arc=[FocalAssignment(section_id="section", lead_target=display)],
    )


def grid() -> BeatGrid:
    points = [0.0, 500.0, 1_000.0, 1_500.0, 2_000.0]
    return BeatGrid(
        bar_boundaries=[0.0, 2_000.0],
        beat_boundaries=points,
        eighth_boundaries=points,
        sixteenth_boundaries=points,
        tempo_bpm=120.0,
        beats_per_bar=4,
        duration_ms=2_000.0,
    )


def entry(
    backend: str,
    start_ms: int,
    end_ms: int,
    *,
    event_id: str | None = None,
) -> ShowTraceEntry:
    moving = backend == "moving_head"
    return ShowTraceEntry.model_validate(
        {
            "backend": backend,
            "event_id": event_id or f"{backend}-{start_ms}",
            "section_id": "section",
            "lane": "BASE",
            "group_id": "Moving Heads" if moving else "Display Group",
            "template_id": "mh-template" if moving else "display-recipe",
            "sources": (
                [{"fixture_id": "MH1", "segment_id": "segment", "step_id": "step"}]
                if moving
                else None
            ),
            "element_name": "Moving Heads" if moving else "Display Group",
            "effect_name": "DMX" if moving else "On",
            "logical_layer": 0,
            "file_layer": 0,
            "live_layer": 99,
            "start_ms": start_ms,
            "end_ms": end_ms,
            "effectdb_ref": 0,
            "palette_ref": None,
        }
    )


def trace(*entries: ShowTraceEntry) -> ShowTraceV2:
    return ShowTraceV2(
        schema_version="twinklr-xsq-trace.v2",
        entry_count=len(entries),
        fallback_substitutions=0,
        entries=list(entries),
    )


def manifest(*, combined: bool = True) -> ShowEvaluationManifest:
    plan = macro()
    show_graph = graph()
    show_mapping = mapping()
    zeros = "0" * 64
    return ShowEvaluationManifest(
        xsq_path="show.xsq",
        trace_path="show.xsq.trace.json",
        xsq_sha256=zeros,
        trace_sha256=zeros,
        macro_plan_sha256=identity_sha256(plan),
        choreography_graph_sha256=identity_sha256(show_graph),
        xlights_mapping_sha256=identity_sha256(show_mapping),
        macro_plan=plan,
        choreography_graph=show_graph,
        xlights_mapping=show_mapping,
        moving_head_target_ids=["MOVING_HEADS"] if combined else [],
        capability=ShowCapability(
            has_display=True,
            has_moving_heads=combined,
            cross_part_applicable=combined,
        ),
    )
