"""Offline deterministic execution of the real combined pipeline definition."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from tests.golden.harness import RIGS, build_fixture_group
from twinklr.core.agents.audio.profile.models import SongSectionRef
from twinklr.core.agents.sequencer.moving_heads.models import (
    ChoreographyPlan,
    PlanSection,
    PlanSegment,
)
from twinklr.core.config.models import AppConfig, JobConfig
from twinklr.core.pipeline import PipelineContext, PipelineExecutor
from twinklr.core.pipeline.definition import PipelineDefinition
from twinklr.core.pipeline.result import success_result
from twinklr.core.pipeline.show_wiring import prepare_combined_show_pipeline
from twinklr.core.sequencer.models.enum import ChannelName, Intensity
from twinklr.core.sequencer.moving_heads.pipeline import RenderingPipeline
from twinklr.core.sequencer.planning.group_plan import LanePlan, SectionCoordinationPlan
from twinklr.core.sequencer.planning.models import (
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
    coordinate_moving_head_plan,
    coordinate_moving_head_segments,
)
from twinklr.core.sequencer.templates.group.models.choreography import (
    ChoreographyGraph,
    ChoreoGroup,
)
from twinklr.core.sequencer.templates.group.models.coordination import (
    CoordinationPlan,
    GroupPlacement,
    PlanTarget,
)
from twinklr.core.sequencer.theming import ThemeRef, ThemeScope
from twinklr.core.sequencer.timing.beat_grid import BeatGrid
from twinklr.core.sequencer.vocabulary import (
    ChoreographyStyle,
    CoordinationMode,
    EffectDuration,
    EnergyTarget,
    IntensityLevel,
    LaneKind,
    MotionDensity,
    PlanningTimeRef,
)
from twinklr.core.sequencer.vocabulary.choreography import TargetType

REPO_ROOT = Path(__file__).resolve().parents[2]


class _FixtureStage:
    def __init__(self, name: str, output: object) -> None:
        self.name = name
        self.output = output

    async def execute(self, input: object, context: PipelineContext):
        return success_result(self.output, stage_name=self.name)


class _MacroFixtureStage(_FixtureStage):
    async def execute(self, input: object, context: PipelineContext):
        assert isinstance(self.output, MacroPlan)
        context.set_state("macro_plan", self.output)
        return success_result(self.output.sections, stage_name=self.name)


class _PassInputStage:
    def __init__(self, name: str) -> None:
        self.name = name

    async def execute(self, input: object, context: PipelineContext):
        return success_result(input, stage_name=self.name)


def _target(group_id: str) -> PlanTarget:
    return PlanTarget(type=TargetType.GROUP, id=group_id)


def _macro(moving_head_target_id: str) -> MacroPlan:
    tree = _target("MEGA_TREE")
    return MacroPlan(
        sections=[
            MacroSection(
                section=SongSectionRef(section_id="drop", name="Drop", start_ms=0, end_ms=4400),
                energy_target=EnergyTarget.PEAK,
                motion_density=MotionDensity.BUSY,
                choreography_style=ChoreographyStyle.HYBRID,
                palette_role=PaletteRoleRef(
                    stop_id="drop",
                    override=PaletteRef(palette_id="core.ice_neon"),
                ),
                theme=ThemeRef(theme_id="theme.holiday.traditional", scope=ThemeScope.SECTION),
                motif_ids=[],
                focal_roles=[
                    FocalRole(target=tree, role=FocalRoleKind.LEAD),
                    FocalRole(target=_target("YARD_ARCHES"), role=FocalRoleKind.SUPPORT),
                    FocalRole(target=_target(moving_head_target_id), role=FocalRoleKind.SUPPORT),
                ],
                call_response_pairs=[],
                coordination_intent=CoordinationMode.UNIFIED,
                notes="One shared macro section drives both deterministic branch renderers.",
            )
        ],
        palette_arc=[
            PaletteStop(
                stop_id="drop",
                palette=PaletteRef(palette_id="core.christmas_traditional"),
                applies_from_section_id="drop",
                transition=PaletteTransition.CUT,
            )
        ],
        motif_continuity=[],
        focal_arc=[FocalAssignment(section_id="drop", lead_target=tree)],
    )


def _section_plan() -> SectionCoordinationPlan:
    placements = [
        GroupPlacement(
            placement_id="tree-spirals",
            target=_target("MEGA_TREE"),
            template_id="gtpl_base_megatree_spirals",
            start=PlanningTimeRef(bar=1, beat=1),
            duration=EffectDuration.PHRASE,
            intensity=IntensityLevel.STRONG,
        ),
        GroupPlacement(
            placement_id="arch-chase",
            target=_target("YARD_ARCHES"),
            template_id="gtpl_rhythm_chase_single",
            start=PlanningTimeRef(bar=1, beat=1),
            duration=EffectDuration.PHRASE,
            intensity=IntensityLevel.MED,
        ),
    ]
    return SectionCoordinationPlan(
        section_id="drop",
        theme=ThemeRef(theme_id="theme.holiday.traditional", scope=ThemeScope.SECTION),
        palette=PaletteRef(palette_id="core.christmas_traditional"),
        start_ms=0,
        end_ms=4400,
        lane_plans=[
            LanePlan(
                lane=LaneKind.BASE,
                target_roles=["MEGA_TREE", "YARD_ARCHES"],
                coordination_plans=[
                    CoordinationPlan(
                        coordination_mode=CoordinationMode.UNIFIED,
                        targets=[_target("MEGA_TREE"), _target("YARD_ARCHES")],
                        placements=placements,
                    )
                ],
            )
        ],
    )


@pytest.mark.integration
@pytest.mark.asyncio
async def test_single_run_drives_both_with_one_grid_by_identity(tmp_path: Path) -> None:
    layout_path = tmp_path / "xlights_rgbeffects.xml"
    mh_members = ",".join(f"Dmx MH{index}" for index in range(1, 5))
    layout_path.write_text(
        f"""<xrgb>
  <models>
    <model name="Dmx MH1" DisplayAs="Dmx" />
    <model name="Dmx MH2" DisplayAs="Dmx" />
    <model name="Dmx MH3" DisplayAs="Dmx" />
    <model name="Dmx MH4" DisplayAs="Dmx" />
    <model name="Mega Tree" DisplayAs="Tree 360" parm1="16" parm2="50" />
    <model name="Arch 1" DisplayAs="Arches" parm1="1" parm2="50" />
  </models>
  <modelGroups>
    <modelGroup name="GROUP - MOVING HEADS" models="{mh_members}" />
    <modelGroup name="Yard Arches" models="Arch 1" />
  </modelGroups>
</xrgb>""",
        encoding="utf-8",
    )
    fixture_group = build_fixture_group(RIGS["mh4_shutter_in_window"])
    wiring = prepare_combined_show_pipeline(
        layout_path=layout_path,
        fixture_group=fixture_group,
        job_config=JobConfig(),
        available_templates=["sweep_lr_fan_hold"],
        song_name="combined_fixture",
        catalog_dir=REPO_ROOT / "catalog" / "templates",
    )
    macro = _macro(next(iter(wiring.moving_head_target_ids)))
    mh_plan = ChoreographyPlan(
        sections=[
            PlanSection(
                section_name="drop",
                start_bar=1,
                end_bar=2,
                template_id="sweep_lr_fan_hold",
                intensity=Intensity.SMOOTH,
            )
        ],
        overall_strategy="fixture",
    )
    replacements = {
        "profile": _FixtureStage("fixture_profile", object()),
        "lyrics": _FixtureStage("fixture_lyrics", object()),
        "macro": _MacroFixtureStage("fixture_macro", macro),
        "groups": _FixtureStage("fixture_groups", _section_plan()),
        "holistic": _PassInputStage("fixture_holistic"),
        "holistic_corrector": _PassInputStage("fixture_holistic_corrector"),
        "moving_heads": _FixtureStage("fixture_moving_heads", mh_plan),
    }
    pipeline = PipelineDefinition(
        name="combined_fixture",
        stages=[
            replace(stage, stage=replacements[stage.id]) if stage.id in replacements else stage
            for stage in wiring.pipeline.stages
        ],
    )
    features = {
        "tempo_bpm": 109.0,
        "beats_s": [0.0, 0.5, 1.1, 1.6, 2.2, 2.7, 3.3, 3.8, 4.4],
        "bars_s": [0.0, 2.2, 4.4],
        "duration_s": 4.4,
        "assumptions": {"beats_per_bar": 4},
    }
    bundle = SimpleNamespace(
        features=features,
        timing=SimpleNamespace(duration_ms=4400),
        lyrics=SimpleNamespace(text="fixture lyric", words=[], phrases=[]),
        phonemes=None,
        audio_path="combined-fixture.wav",
        metadata=None,
    )
    analyzer = MagicMock()
    analyzer.analyze = AsyncMock(return_value=bundle)
    analyzer.aclose = AsyncMock()
    session = MagicMock()
    session.app_config = AppConfig()
    session.job_config = JobConfig()
    context = PipelineContext(session=session)
    with patch("twinklr.core.audio.analyzer.AudioAnalyzer", return_value=analyzer):
        result = await PipelineExecutor().execute(pipeline, "combined-fixture.wav", context)

    assert result.success, result.failed_stages
    assert all(
        list(result.stage_results).count(stage_id) == 1
        for stage_id in ("audio", "profile", "lyrics", "macro")
    )
    grid = context.get_state("beat_grid")
    assert isinstance(grid, BeatGrid)
    assert grid.beat_boundaries[2] == 1100.0
    assert context.get_state("mh_render_beat_grid") is grid
    assert context.get_state("display_render_beat_grid") is grid
    output = result.outputs["show_render"]
    assert output["beat_grid"] is grid
    assert output["sequence"] is context.get_state("sequence")
    evaluation_contract = output["evaluation_contract"]
    assert evaluation_contract["macro_plan"] == macro
    assert evaluation_contract["choreography_graph"] == wiring.choreo_graph
    assert evaluation_contract["xlights_mapping"] == wiring.xlights_mapping
    assert evaluation_contract["moving_head_target_ids"] == sorted(wiring.moving_head_target_ids)
    element_types = {
        element.element_name: {
            effect.effect_type for layer in element.layers for effect in layer.effects
        }
        for element in output["sequence"].element_effects
    }
    assert any("DMX" in types for name, types in element_types.items() if name.startswith("Dmx MH"))
    assert element_types["Mega Tree"] == {"Spirals"}
    assert element_types["Yard Arches"] == {"SingleStrand"}
    coordinated_mh = context.get_state("coordinated_mh_plan")
    assert coordinated_mh.sections[0].color_intent.explicit_color.value == "cyan"
    dmx_settings = [
        output["sequence"].effect_db.entries[effect.ref]
        for element in output["sequence"].element_effects
        if element.element_name.startswith("Dmx MH")
        for layer in element.layers
        for effect in layer.effects
        if effect.ref is not None
    ]
    assert dmx_settings
    assert all("E_SLIDER_DMX7=90" in settings for settings in dmx_settings)


@pytest.mark.integration
def test_real_segmented_two_section_render_preserves_transitions_and_macro_palette() -> None:
    mh_target = _target("MOVING_HEADS")
    tree = _target("MEGA_TREE")
    macro = MacroPlan(
        sections=[
            MacroSection(
                section=SongSectionRef(section_id="drop", name="Drop", start_ms=0, end_ms=4_400),
                energy_target=EnergyTarget.PEAK,
                motion_density=MotionDensity.BUSY,
                choreography_style=ChoreographyStyle.HYBRID,
                palette_role=PaletteRoleRef(stop_id="drop-red", override=None),
                theme=ThemeRef(theme_id="theme.holiday.traditional", scope=ThemeScope.SECTION),
                motif_ids=[],
                focal_roles=[
                    FocalRole(target=tree, role=FocalRoleKind.LEAD),
                    FocalRole(target=mh_target, role=FocalRoleKind.SUPPORT),
                ],
                call_response_pairs=[],
                coordination_intent=CoordinationMode.UNIFIED,
                notes="Segmented first section.",
            ),
            MacroSection(
                section=SongSectionRef(
                    section_id="chorus", name="Chorus", start_ms=4_400, end_ms=8_800
                ),
                energy_target=EnergyTarget.HIGH,
                motion_density=MotionDensity.MED,
                choreography_style=ChoreographyStyle.HYBRID,
                palette_role=PaletteRoleRef(
                    stop_id="drop-red",
                    override=PaletteRef(palette_id="core.ice_neon"),
                ),
                theme=ThemeRef(theme_id="theme.holiday.traditional", scope=ThemeScope.SECTION),
                motif_ids=[],
                focal_roles=[
                    FocalRole(target=tree, role=FocalRoleKind.LEAD),
                    FocalRole(target=mh_target, role=FocalRoleKind.SUPPORT),
                ],
                call_response_pairs=[],
                coordination_intent=CoordinationMode.UNIFIED,
                notes="Second section exercises a palette override.",
            ),
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
        focal_arc=[
            FocalAssignment(section_id="drop", lead_target=tree),
            FocalAssignment(section_id="chorus", lead_target=tree),
        ],
    )
    grid = BeatGrid(
        bar_boundaries=[0.0, 2_200.0, 4_400.0, 6_600.0, 8_800.0],
        beat_boundaries=[float(value) for value in range(0, 8_801, 550)],
        eighth_boundaries=[float(value) for value in range(0, 8_801, 550)],
        sixteenth_boundaries=[float(value) for value in range(0, 8_801, 550)],
        tempo_bpm=109.0,
        beats_per_bar=4,
        duration_ms=8_800,
    )
    graph = ChoreographyGraph(
        graph_id="segmented-transition",
        groups=[
            ChoreoGroup(id="MOVING_HEADS", role="MOVING_HEADS"),
            ChoreoGroup(id="MEGA_TREE", role="MEGA_TREE"),
        ],
    )
    plan = ChoreographyPlan(
        sections=[
            PlanSection(
                section_name="drop",
                start_bar=1,
                end_bar=2,
                segments=[
                    PlanSegment(
                        segment_id="a",
                        start_bar=1,
                        end_bar=1,
                        template_id="sweep_lr_fan_hold",
                    ),
                    PlanSegment(
                        segment_id="b",
                        start_bar=2,
                        end_bar=2,
                        template_id="bounce_fan_pulse",
                    ),
                ],
            ),
            PlanSection(
                section_name="chorus",
                start_bar=3,
                end_bar=4,
                template_id="sweep_lr_fan_hold",
            ),
        ],
        overall_strategy="real segmented transition fixture",
    )
    fixture_group = build_fixture_group(RIGS["mh4_shutter_in_window"])
    coordinated_plan = coordinate_moving_head_plan(
        plan,
        macro,
        grid,
        {"MOVING_HEADS"},
        coordination_graph=graph,
    )
    raw = RenderingPipeline(
        choreography_plan=coordinated_plan,
        beat_grid=grid,
        fixture_group=fixture_group,
        job_config=JobConfig(),
        output_path=None,
    ).render()
    regular_identity = {
        (segment.section_id, segment.segment_id, segment.template_id)
        for segment in raw
        if segment.metadata.get("is_transition") != "true"
    }
    assert any(identity[:2] == ("drop", "a") for identity in regular_identity)
    assert any(identity[:2] == ("drop", "b") for identity in regular_identity)
    assert any(identity[0] == "chorus" for identity in regular_identity)
    assert any(segment.metadata.get("is_transition") == "true" for segment in raw)

    emitted = coordinate_moving_head_segments(
        raw,
        macro,
        grid,
        graph,
        moving_head_target_ids={"MOVING_HEADS"},
    )
    emitted_identity = {
        (segment.section_id, segment.segment_id)
        for segment in emitted
        if "transition_" not in segment.section_id
    }
    assert any(
        identity[0] == "drop" and identity[1].startswith("a|coord-")
        for identity in emitted_identity
    )
    assert any(
        identity[0] == "drop" and identity[1].startswith("b|coord-")
        for identity in emitted_identity
    )
    assert any(identity[0] == "chorus" for identity in emitted_identity)
    assert any(segment.metadata.get("is_transition") == "true" for segment in emitted)
    regular_colors = {
        segment.section_id: segment.channels[ChannelName.COLOR].static_dmx
        for segment in emitted
        if segment.metadata.get("is_transition") != "true" and ChannelName.COLOR in segment.channels
    }
    assert regular_colors["drop"] == 18
    assert regular_colors["chorus"] == 90
