"""Headline P3-T5 artifact: moving-head DMX + Spirals + chase in one XSequence.

The display half is pinned effect for effect (type, time ranges, settings and palette
strings, and its trace entries without their shared-table indices); the moving-head
half is the moving-head render, pinned by its render fingerprint, effect count and the
hash of its effects and trace entries.
"""

from __future__ import annotations

from collections.abc import Iterator
import hashlib
import json
from pathlib import Path
from typing import Any

import pytest

from tests.support.moving_heads import family_catalog, family_job, family_rig, plan_section
from twinklr.core.agents.audio.profile.models import SongSectionRef
from twinklr.core.agents.sequencer.moving_heads.models import ChoreographyPlan
from twinklr.core.formats.xlights.sequence.models.xsq import TimeMarker, XSequence
from twinklr.core.formats.xlights.sequence.trace import build_xsq_trace_payload
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
from twinklr.core.sequencer.moving_heads.delivery import build_sequence
from twinklr.core.sequencer.moving_heads.pipeline import RenderingPipeline
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
    moving_head_dark_spans,
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


MH_ELEMENT = "Dmx MH1"


@pytest.fixture(autouse=True)
def _catalog() -> Iterator[None]:
    with family_catalog():
        yield


def _build_combined() -> tuple[XSequence, dict[str, Any], RenderingPipeline]:
    macro = _macro()
    grid = _grid()
    graph = _graph()
    pipeline = RenderingPipeline(
        choreography_plan=ChoreographyPlan(
            sections=[plan_section("drop", 1, 2, "mirror_wings")],
            overall_strategy="golden",
        ),
        beat_grid=grid,
        fixture_group=family_rig(("MH1",)),
        job_config=family_job(("MH1",)),
        media_file="combined-show.wav",
        dark_spans=moving_head_dark_spans(
            macro, grid, graph, moving_head_target_ids={"MOVING_HEADS"}
        ),
    )
    pipeline.render()
    sequence = build_sequence(
        pipeline.requests,
        [TimeMarker(name="drop", time_ms=0, end_time_ms=4400)],
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
    trace = build_xsq_trace_payload(
        write_result.trace_entries,
        fallback_substitutions=write_result.fallback_substitutions,
    )
    return sequence, trace, pipeline


def _sha256(value: object) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()


def _snapshot(
    sequence: XSequence, trace: dict[str, Any], pipeline: RenderingPipeline
) -> dict[str, Any]:
    """Each display element's one effect type, settings, palette and time ranges; the
    moving heads' effects and trace entries by hash."""
    display: dict[str, dict[str, Any]] = {}
    moving_heads: list[list[object]] = []
    for element in sequence.element_effects:
        for layer in element.layers:
            for effect in layer.effects:
                assert effect.ref is not None
                settings = sequence.effect_db.entries[effect.ref]
                palette = (
                    sequence.color_palettes[int(effect.palette)].settings
                    if effect.palette
                    else None
                )
                if element.element_name == MH_ELEMENT:
                    moving_heads.append(
                        [effect.effect_type, effect.start_time_ms, effect.end_time_ms, settings]
                    )
                    assert palette is None
                    continue
                current = display.setdefault(
                    element.element_name,
                    {
                        "type": effect.effect_type,
                        "ranges": [],
                        "settings": settings,
                        "palette": palette,
                    },
                )
                assert current["type"] == effect.effect_type
                assert current["settings"] == settings
                current["ranges"].append([effect.start_time_ms, effect.end_time_ms])
    assert pipeline.render_record is not None
    return {
        "media_file": sequence.head.media_file,
        "duration_ms": sequence.sequence_duration_ms,
        "effects": display,
        "moving_heads": {
            "render_fingerprint": pipeline.render_record["render_fingerprint"],
            "effect_count": len(moving_heads),
            "effects_sha256": _sha256(moving_heads),
            "trace_sha256": _sha256(
                [entry for entry in trace["entries"] if entry["backend"] == "moving_head"]
            ),
        },
    }


def _display_trace(trace: dict[str, Any]) -> list[dict[str, Any]]:
    """The display trace entries without their EffectDB and palette indices, which
    count the moving heads' entries the shared tables hold before them."""
    return [
        {key: value for key, value in entry.items() if key not in ("effectdb_ref", "palette_ref")}
        for entry in trace["entries"]
        if entry["backend"] == "display"
    ]


def test_combined_show_drop_matches_emitted_golden() -> None:
    sequence, trace, pipeline = _build_combined()
    actual = _snapshot(sequence, trace, pipeline)
    expected = json.loads(GOLDEN.read_text(encoding="utf-8"))
    assert actual == expected
    assert _display_trace(trace) == json.loads(TRACE_GOLDEN.read_text(encoding="utf-8"))
    assert trace["entry_count"] == len(trace["entries"])
    # The trace header the tag's golden recorded: no display effect fell back.
    assert trace["schema_version"] == "twinklr-xsq-trace.v2"
    assert trace["fallback_substitutions"] == 0

    by_element = actual["effects"]
    assert by_element["Mega Tree"]["type"] == "Spirals"
    assert by_element["Yard Arches"]["type"] == "SingleStrand"
    assert by_element["Mega Tree"]["palette"] == by_element["Yard Arches"]["palette"]
    assert "C_BUTTON_Palette1=#00E5FF" in by_element["Mega Tree"]["palette"]
    # The display calls where the moving heads rest: each display range is a span the
    # render holds the heads dark over.
    display_ranges = {tuple(item) for details in by_element.values() for item in details["ranges"]}
    assert display_ranges == {tuple(span) for span in pipeline.render_record["dark_spans"]}
    assert actual["moving_heads"]["effect_count"] > 0
