"""Unit tests for GroupPlannerStage pipeline timing context behavior."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from twinklr.core.agents.audio.profile.models import SongSectionRef
from twinklr.core.agents.sequencer.group_planner.context import MacroSectionPlanningInput
from twinklr.core.agents.sequencer.group_planner.stage import (
    GroupPlanAggregatorStage,
    GroupPlannerStage,
)
from twinklr.core.audio.models import SongBundle, SongTiming
from twinklr.core.sequencer.planning import (
    FocalAssignment,
    FocalRole,
    FocalRoleKind,
    LanePlan,
    MacroPlan,
    MacroSection,
    PaletteRef,
    PaletteRoleRef,
    PaletteStop,
    PaletteTransition,
    SectionCoordinationPlan,
)
from twinklr.core.sequencer.planning.group_plan import NarrativeAssetDirective
from twinklr.core.sequencer.templates.group.catalog import TemplateCatalog
from twinklr.core.sequencer.templates.group.models.choreography import (
    ChoreographyGraph,
    ChoreoGroup,
)
from twinklr.core.sequencer.templates.group.models.coordination import PlanTarget
from twinklr.core.sequencer.theming import ThemeRef, ThemeScope
from twinklr.core.sequencer.vocabulary import (
    ChoreographyStyle,
    CoordinationMode,
    EnergyTarget,
    LaneKind,
    MotionDensity,
    TargetType,
)


def _make_stage() -> GroupPlannerStage:
    return GroupPlannerStage(
        choreo_graph=ChoreographyGraph(
            graph_id="test",
            groups=[ChoreoGroup(id="G1", role="OUTLINE")],
        ),
        template_catalog=TemplateCatalog(entries=[]),
    )


def _make_bundle(features: dict[str, object]) -> SongBundle:
    return SongBundle(
        schema_version="3.0",
        audio_path="/tmp/test.mp3",
        recording_id="rec_1",
        features=features,
        timing=SongTiming(sr=22050, hop_length=512, duration_s=30.0, duration_ms=30000),
    )


def test_build_timing_context_uses_derived_beats_per_bar() -> None:
    """Timing context should honor derived meter from analysis features."""
    stage = _make_stage()
    bundle = _make_bundle({"tempo_bpm": 120.0, "assumptions": {"beats_per_bar": 3}})

    timing_context = stage._build_timing_context(
        bundle, section_id="sec_1", section_start_ms=0, section_end_ms=6000
    )

    assert timing_context.beats_per_bar == 3


def test_build_timing_context_warns_and_falls_back_to_4_4(caplog) -> None:
    """Missing derived meter should emit warning and fallback to 4/4."""
    stage = _make_stage()
    bundle = _make_bundle({"tempo_bpm": 120.0})

    with caplog.at_level("WARNING"):
        timing_context = stage._build_timing_context(
            bundle, section_id="sec_1", section_start_ms=0, section_end_ms=6000
        )

    assert timing_context.beats_per_bar == 4
    assert "falling back to 4/4" in caplog.text


def test_build_section_context_receives_lossless_typed_macro_projection() -> None:
    """The group stage consumes the typed plan from state, not a flattened string map."""
    stage = _make_stage()
    target = PlanTarget(type=TargetType.GROUP, id="G1")
    section = MacroSection(
        section=SongSectionRef(section_id="verse_1", name="verse", start_ms=0, end_ms=6000),
        energy_target=EnergyTarget.MED,
        motion_density=MotionDensity.MED,
        choreography_style=ChoreographyStyle.HYBRID,
        palette_role=PaletteRoleRef(stop_id="main", override=None),
        theme=ThemeRef(
            theme_id="theme.abstract.neon",
            scope=ThemeScope.SECTION,
            tags=[],
            palette_id=None,
        ),
        motif_ids=[],
        focal_roles=[FocalRole(target=target, role=FocalRoleKind.LEAD)],
        call_response_pairs=[],
        coordination_intent=CoordinationMode.UNIFIED,
        notes="Typed group-planner stage guidance for this section.",
    )
    plan = MacroPlan(
        sections=[section],
        palette_arc=[
            PaletteStop(
                stop_id="main",
                palette=PaletteRef(
                    palette_id="core.christmas_traditional",
                    role=None,
                    intensity=None,
                    variant=None,
                ),
                applies_from_section_id="verse_1",
                transition=PaletteTransition.HOLD,
            )
        ],
        motif_continuity=[],
        focal_arc=[FocalAssignment(section_id="verse_1", lead_target=target)],
    )
    bundle = _make_bundle({"tempo_bpm": 120.0, "assumptions": {"beats_per_bar": 4}})
    context = MagicMock()
    context.get_state.side_effect = lambda key: {
        "audio_bundle": bundle,
        "macro_plan": plan,
        "lyric_context": None,
    }.get(key)

    result = stage._build_section_context(section, context)

    assert isinstance(result.macro_input, MacroSectionPlanningInput)
    assert result.macro_input.macro_section is not None
    assert result.macro_input.macro_section.section.section_id == "verse_1"
    assert result.macro_input.palette_stop.stop_id == "main"
    assert result.macro_input.focal_assignment.lead_target == target

    cached_plan = SectionCoordinationPlan(
        section_id="hallucinated",
        theme=ThemeRef(
            theme_id="theme.wrong",
            scope=ThemeScope.SECTION,
            tags=[],
            palette_id=None,
        ),
        palette=PaletteRef(palette_id="core.wrong"),
        motif_ids=["wrong"],
        lane_plans=[LanePlan(lane=LaneKind.BASE, target_roles=["OUTLINE"])],
    )
    extracted = stage._extract_plan_result(
        SimpleNamespace(plan=cached_plan.model_dump()),  # type: ignore[arg-type]
        result,
    )

    assert extracted.section_id == "verse_1"
    assert extracted.theme == section.theme
    assert extracted.palette == plan.palette_for_section("verse_1")
    assert extracted.motif_ids == []
    assert extracted.start_ms == 0
    assert extracted.end_ms == 6000


@pytest.mark.asyncio
async def test_aggregate_caps_narrative_assets_after_deduplication() -> None:
    def section(section_id: str, *ids: str) -> SectionCoordinationPlan:
        return SectionCoordinationPlan(
            section_id=section_id,
            theme=ThemeRef(theme_id="theme.abstract.neon", scope=ThemeScope.SECTION),
            lane_plans=[LanePlan(lane=LaneKind.BASE, target_roles=["OUTLINE"])],
            narrative_assets=[
                NarrativeAssetDirective(
                    directive_id=id_,
                    subject="An illuminated tree",
                    category="image_cutout",
                    visual_description="A tree outlined with bright white lights.",
                    story_context="The first glimpse of the display.",
                )
                for id_ in ids
            ],
        )

    intro = section("intro", "tree", "house", "star")
    chorus = section("chorus", "tree", "bell", "candle")
    result = await GroupPlanAggregatorStage().execute([intro, chorus], MagicMock())

    assert result.success, result.error
    assert result.output is not None
    assets = result.output.narrative_assets
    assert [asset.directive_id for asset in assets] == ["tree", "house", "star", "bell"]
    assert assets[0].section_ids == ["intro", "chorus"]
    assert result.output.section_plans == [intro, chorus]


def test_planner_bar_and_beat_names_resolve_to_the_renderers_detected_grid() -> None:
    from twinklr.core.sequencer.vocabulary import PlanningTimeRef

    bundle = _make_bundle(
        {
            "tempo_bpm": 120.0,
            "assumptions": {"beats_per_bar": 4},
            "beats_s": [0.0, 0.4, 1.0, 1.3, 1.9, 2.5, 3.0, 3.3, 4.0, 4.5, 5.0],
            "bars_s": [1.0, 3.0, 5.0],
        }
    )
    timing = _make_stage()._build_timing_context(
        bundle,
        section_id="verse",
        section_start_ms=900,
        section_end_ms=4800,
    )
    assert timing.bar_map[1].start_ms == 1000
    assert timing.resolve_planning_time_ref(PlanningTimeRef(bar=1, beat=2)) == 1300
    assert timing.resolve_planning_time_ref(PlanningTimeRef(bar=2, beat=3)) == 4000


def test_musical_context_retains_events_and_maps_detected_beat_times() -> None:
    stage = _make_stage()
    bundle = _make_bundle(
        {
            "tempo_bpm": 120.0,
            "assumptions": {"beats_per_bar": 4},
            "beats_s": [1, 1.3, 1.8, 2.4, 3, 3.5, 4, 4.5, 5],
            "bars_s": [1, 3, 5],
        }
    )
    timing = stage._build_timing_context(
        bundle, section_id="verse", section_start_ms=900, section_end_ms=4900
    )
    result = stage._build_musical_context(
        None,
        {"moment_cues": [{"timestamp_ms": 1280, "text": "Hook"}]},
        timing,
        section_id="verse",
        start_ms=900,
        end_ms=4900,
    )
    assert result["moments"][0] == {
        "timestamp_ms": 1280,
        "text": "Hook",
        "bar": 1,
        "beat": 2,
        "render_ms": 1300,
        "offset_ms": 20,
    }
    assert result["beat_times"][1] == {"bar": 1, "beat": 2, "timestamp_ms": 1300}
    assert all(900 <= beat["timestamp_ms"] < 4900 for beat in result["beat_times"])
