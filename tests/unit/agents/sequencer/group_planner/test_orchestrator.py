"""Tests for GroupPlannerOrchestrator."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from twinklr.core.agents.audio.profile.models import SongSectionRef
from twinklr.core.agents.sequencer.group_planner.context import (
    SectionPlanningContext,
    project_macro_section,
)
from twinklr.core.agents.sequencer.group_planner.orchestrator import (
    GroupPlannerOrchestrator,
)
from twinklr.core.agents.sequencer.group_planner.timing import (
    BarInfo,
    SectionBounds,
    TimingContext,
)
from twinklr.core.sequencer.planning import (
    FocalAssignment,
    FocalRole,
    FocalRoleKind,
    LanePlan,
    MacroPlan,
    MacroSection,
    MotifEvolution,
    MotifThread,
    PaletteRef,
    PaletteRoleRef,
    PaletteStop,
    PaletteTransition,
    SectionCoordinationPlan,
)
from twinklr.core.sequencer.templates.group.catalog import (
    TemplateCatalog,
    TemplateInfo,
)
from twinklr.core.sequencer.templates.group.models import (
    CoordinationPlan,
    GroupPlacement,
)
from twinklr.core.sequencer.templates.group.models.choreography import (
    ChoreographyGraph,
    ChoreoGroup,
)
from twinklr.core.sequencer.templates.group.models.coordination import PlanTarget
from twinklr.core.sequencer.timing import TimeRef
from twinklr.core.sequencer.vocabulary import (
    ChoreographyStyle,
    CoordinationMode,
    EffectDuration,
    EnergyTarget,
    GroupTemplateType,
    GroupVisualIntent,
    LaneKind,
    MotionDensity,
    PlanningTimeRef,
)
from twinklr.core.sequencer.vocabulary.choreography import TargetType
from twinklr.core.sequencer.vocabulary.timing import TimeRefKind

from .conftest import DEFAULT_THEME


@pytest.fixture
def mock_provider() -> MagicMock:
    """Create mock LLM provider."""
    provider = MagicMock()
    provider.generate_json_async = AsyncMock()
    return provider


@pytest.fixture
def sample_choreo_graph() -> ChoreographyGraph:
    """Sample choreography graph."""
    return ChoreographyGraph(
        graph_id="test",
        groups=[
            ChoreoGroup(id="HERO_1", role="HERO"),
            ChoreoGroup(id="ARCHES_1", role="ARCHES"),
        ],
    )


@pytest.fixture
def sample_template_catalog() -> TemplateCatalog:
    """Sample template catalog."""
    return TemplateCatalog(
        entries=[
            TemplateInfo(
                template_id="gtpl_base_glow_warm",
                version="1.0",
                name="Warm BG",
                template_type=GroupTemplateType.BASE,
                visual_intent=GroupVisualIntent.ABSTRACT,
                tags=(),
            ),
            TemplateInfo(
                template_id="gtpl_accent_flash",
                version="1.0",
                name="Flash",
                template_type=GroupTemplateType.ACCENT,
                visual_intent=GroupVisualIntent.TEXTURE,
                tags=(),
            ),
        ]
    )


@pytest.fixture
def sample_timing_context() -> TimingContext:
    """Sample timing context."""
    return TimingContext(
        song_duration_ms=8000,
        beats_per_bar=4,
        bar_map={
            1: BarInfo(bar=1, start_ms=0, duration_ms=2000),
            2: BarInfo(bar=2, start_ms=2000, duration_ms=2000),
        },
        section_bounds={
            "verse_1": SectionBounds(
                section_id="verse_1",
                start=TimeRef(kind=TimeRefKind.BAR_BEAT, bar=1, beat=1),
                end=TimeRef(kind=TimeRefKind.BAR_BEAT, bar=2, beat=1),
            ),
        },
    )


@pytest.fixture
def sample_section_context(
    sample_choreo_graph: ChoreographyGraph,
    sample_template_catalog: TemplateCatalog,
    sample_timing_context: TimingContext,
) -> SectionPlanningContext:
    """Sample section planning context."""
    return SectionPlanningContext(
        section_id="verse_1",
        section_name="verse",
        start_ms=0,
        end_ms=2000,
        energy_target="MED",
        motion_density="MED",
        choreography_style="HYBRID",
        lead_targets=["HERO"],
        support_targets=["ARCHES"],
        notes=None,
        choreo_graph=sample_choreo_graph,
        template_catalog=sample_template_catalog,
        timing_context=sample_timing_context,
    )


@pytest.fixture
def sample_section_plan() -> SectionCoordinationPlan:
    """Sample valid section coordination plan."""
    return SectionCoordinationPlan(
        section_id="verse_1",
        theme=DEFAULT_THEME,
        lane_plans=[
            LanePlan(
                lane=LaneKind.ACCENT,
                target_roles=["HERO"],
                coordination_plans=[
                    CoordinationPlan(
                        coordination_mode=CoordinationMode.UNIFIED,
                        targets=[PlanTarget(type=TargetType.GROUP, id="HERO_1")],
                        placements=[
                            GroupPlacement(
                                placement_id="p1",
                                target=PlanTarget(type=TargetType.GROUP, id="HERO_1"),
                                template_id="gtpl_accent_flash",
                                start=PlanningTimeRef(bar=1, beat=1),
                                duration=EffectDuration.HIT,
                            ),
                        ],
                    ),
                ],
            ),
        ],
    )


class TestGroupPlannerOrchestrator:
    """Tests for GroupPlannerOrchestrator."""

    def test_orchestrator_initialization(self, mock_provider: MagicMock) -> None:
        """Orchestrator initializes with default specs."""
        orchestrator = GroupPlannerOrchestrator(provider=mock_provider)

        assert orchestrator.planner_spec is not None
        assert orchestrator.planner_spec.name == "group_planner"
        assert orchestrator.section_judge_spec is not None
        assert orchestrator.section_judge_spec.name == "section_judge"

    def test_orchestrator_custom_specs(self, mock_provider: MagicMock) -> None:
        """Orchestrator accepts custom specs."""
        from twinklr.core.agents.spec import AgentMode, AgentSpec

        custom_planner = AgentSpec(
            name="custom_planner",
            prompt_pack="test/prompts/planner",
            response_model=SectionCoordinationPlan,
            mode=AgentMode.ONESHOT,
        )

        orchestrator = GroupPlannerOrchestrator(
            provider=mock_provider,
            planner_spec=custom_planner,
        )

        assert orchestrator.planner_spec.name == "custom_planner"

    def test_heuristic_validator_integration(
        self,
        mock_provider: MagicMock,
        sample_section_context: SectionPlanningContext,
        sample_section_plan: SectionCoordinationPlan,
    ) -> None:
        """Orchestrator uses heuristic validator."""
        orchestrator = GroupPlannerOrchestrator(provider=mock_provider)

        # Validator should catch unknown templates
        invalid_plan = SectionCoordinationPlan(
            section_id="verse_1",
            theme=DEFAULT_THEME,
            lane_plans=[
                LanePlan(
                    lane=LaneKind.ACCENT,
                    target_roles=["HERO"],
                    coordination_plans=[
                        CoordinationPlan(
                            coordination_mode=CoordinationMode.UNIFIED,
                            targets=[PlanTarget(type=TargetType.GROUP, id="HERO_1")],
                            placements=[
                                GroupPlacement(
                                    placement_id="p1",
                                    target=PlanTarget(type=TargetType.GROUP, id="HERO_1"),
                                    template_id="NONEXISTENT",  # Invalid!
                                    start=PlanningTimeRef(bar=1, beat=1),
                                    duration=EffectDuration.HIT,
                                ),
                            ],
                        ),
                    ],
                ),
            ],
        )

        # Build the validator function as the orchestrator does
        validator = orchestrator._build_validator(sample_section_context)
        errors = validator(invalid_plan)

        assert len(errors) > 0
        assert any("NONEXISTENT" in e for e in errors)

    def test_build_planner_variables(
        self,
        mock_provider: MagicMock,
        sample_section_context: SectionPlanningContext,
    ) -> None:
        """Orchestrator builds correct planner variables."""
        orchestrator = GroupPlannerOrchestrator(provider=mock_provider)

        variables = orchestrator._build_planner_variables(sample_section_context)

        assert variables["section_id"] == "verse_1"
        assert variables["energy_target"] == "MED"
        assert "display_graph" in variables
        assert "template_catalog" in variables

    @pytest.mark.asyncio
    async def test_cache_key_tracks_typed_macro_projection(
        self,
        mock_provider: MagicMock,
        sample_section_context: SectionPlanningContext,
    ) -> None:
        """Palette, motif, and focal projection data participate in cache identity."""
        target = PlanTarget(type=TargetType.GROUP, id="HERO_1")
        section = MacroSection(
            section=SongSectionRef(section_id="verse_1", name="verse", start_ms=0, end_ms=2000),
            energy_target=EnergyTarget.MED,
            motion_density=MotionDensity.MED,
            choreography_style=ChoreographyStyle.HYBRID,
            palette_role=PaletteRoleRef(stop_id="main", override=None),
            theme=DEFAULT_THEME,
            motif_ids=["pulse"],
            focal_roles=[FocalRole(target=target, role=FocalRoleKind.LEAD)],
            call_response_pairs=[],
            coordination_intent=CoordinationMode.UNIFIED,
            notes="Typed group-planner macro guidance for this section.",
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
            motif_continuity=[
                MotifThread(
                    motif_id="pulse",
                    section_ids=["verse_1"],
                    evolution=MotifEvolution.INTRODUCE,
                    description="A pulse motif for this section.",
                )
            ],
            focal_arc=[FocalAssignment(section_id="verse_1", lead_target=target)],
        )
        context = sample_section_context.model_copy(
            update={"macro_input": project_macro_section(plan, section)}
        )
        changed_projection = context.macro_input.model_copy(
            update={
                "resolved_palette": PaletteRef(
                    palette_id="core.ice_blue",
                    role=None,
                    intensity=None,
                    variant=None,
                )
            }
        )
        changed = context.model_copy(update={"macro_input": changed_projection})
        orchestrator = GroupPlannerOrchestrator(provider=mock_provider)

        assert await orchestrator.get_cache_key(context) != await orchestrator.get_cache_key(
            changed
        )

    def test_validator_stamps_macro_owned_fields_before_heuristics(
        self,
        mock_provider: MagicMock,
        sample_section_context: SectionPlanningContext,
        sample_section_plan: SectionCoordinationPlan,
    ) -> None:
        """LLM metadata drift is normalized before every validation path."""
        target = PlanTarget(type=TargetType.GROUP, id="HERO_1")
        macro_section = MacroSection(
            section=SongSectionRef(section_id="verse_1", name="verse", start_ms=0, end_ms=2000),
            energy_target=EnergyTarget.MED,
            motion_density=MotionDensity.MED,
            choreography_style=ChoreographyStyle.HYBRID,
            palette_role=PaletteRoleRef(stop_id="main", override=None),
            theme=DEFAULT_THEME,
            motif_ids=[],
            focal_roles=[FocalRole(target=target, role=FocalRoleKind.LEAD)],
            call_response_pairs=[],
            coordination_intent=CoordinationMode.UNIFIED,
            notes="Typed metadata must remain authoritative through validation.",
        )
        macro_plan = MacroPlan(
            sections=[macro_section],
            palette_arc=[
                PaletteStop(
                    stop_id="main",
                    palette=PaletteRef(palette_id="core.christmas_traditional"),
                    applies_from_section_id="verse_1",
                    transition=PaletteTransition.HOLD,
                )
            ],
            motif_continuity=[],
            focal_arc=[FocalAssignment(section_id="verse_1", lead_target=target)],
        )
        context = sample_section_context.model_copy(
            update={"macro_input": project_macro_section(macro_plan, macro_section)}
        )
        drifted = sample_section_plan.model_copy(
            update={
                "section_id": "hallucinated",
                "theme": DEFAULT_THEME.model_copy(update={"theme_id": "theme.wrong"}),
                "palette": PaletteRef(palette_id="core.wrong"),
                "motif_ids": ["wrong"],
            }
        )

        GroupPlannerOrchestrator(provider=mock_provider)._build_validator(context)(drifted)

        assert drifted.section_id == "verse_1"
        assert drifted.theme == DEFAULT_THEME
        assert drifted.palette == macro_plan.palette_for_section("verse_1")
        assert drifted.motif_ids == []
