"""Integration tests for GroupPlannerOrchestrator with mock LLM."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from twinklr.core.agents.sequencer.group_planner import (
    CoordinationMode,
    CoordinationPlan,
    DisplayGraph,
    DisplayGroup,
    GroupPlacement,
    GroupPlannerOrchestrator,
    LaneKind,
    LanePlan,
    SectionCoordinationPlan,
    SectionPlanningContext,
    TemplateCatalog,
    TemplateInfo,
    TimeRef,
    TimeRefKind,
)
from twinklr.core.agents.sequencer.group_planner.timing import (
    BarInfo,
    SectionBounds,
    TimingContext,
)
from twinklr.core.agents.shared.judge.models import JudgeVerdict, VerdictStatus
from twinklr.core.sequencer.theming import ThemeRef, ThemeScope
from twinklr.core.sequencer.vocabulary import (
    EffectDuration,
    GroupTemplateType,
    GroupVisualIntent,
    PlanningTimeRef,
)


@pytest.fixture
def sample_display_graph() -> DisplayGraph:
    """Sample display graph."""
    return DisplayGraph(
        display_id="test",
        display_name="Test",
        groups=[
            DisplayGroup(group_id="HERO_1", role="HERO", display_name="Hero 1"),
            DisplayGroup(group_id="HERO_2", role="HERO", display_name="Hero 2"),
            DisplayGroup(group_id="ARCHES_1", role="ARCHES", display_name="Arches"),
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
                template_id="gtpl_rhythm_bounce",
                version="1.0",
                name="Bounce",
                template_type=GroupTemplateType.RHYTHM,
                visual_intent=GroupVisualIntent.GEOMETRIC,
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
            3: BarInfo(bar=3, start_ms=4000, duration_ms=2000),
            4: BarInfo(bar=4, start_ms=6000, duration_ms=2000),
        },
        section_bounds={
            "verse_1": SectionBounds(
                section_id="verse_1",
                start=TimeRef(kind=TimeRefKind.BAR_BEAT, bar=1, beat=1),
                end=TimeRef(kind=TimeRefKind.BAR_BEAT, bar=3, beat=1),
            ),
        },
    )


@pytest.fixture
def sample_section_context(
    sample_display_graph: DisplayGraph,
    sample_template_catalog: TemplateCatalog,
    sample_timing_context: TimingContext,
) -> SectionPlanningContext:
    """Sample section planning context."""
    return SectionPlanningContext(
        section_id="verse_1",
        section_name="verse",
        start_ms=0,
        end_ms=4000,
        energy_target="MED",
        motion_density="MED",
        choreography_style="HYBRID",
        primary_focus_targets=["HERO"],
        secondary_targets=["ARCHES"],
        notes=None,
        display_graph=sample_display_graph,
        template_catalog=sample_template_catalog,
        timing_context=sample_timing_context,
    )


def _make_section_theme() -> ThemeRef:
    """Create a valid section ThemeRef (SECTION scope)."""
    return ThemeRef(
        theme_id="theme.abstract.neon",
        scope=ThemeScope.SECTION,
        tags=["motif.geometric"],
    )


def create_mock_section_plan() -> SectionCoordinationPlan:
    """Create a mock SectionCoordinationPlan that passes validation."""
    return SectionCoordinationPlan(
        section_id="verse_1",
        theme=_make_section_theme(),
        lane_plans=[
            LanePlan(
                lane=LaneKind.ACCENT,
                target_roles=["HERO"],
                coordination_plans=[
                    CoordinationPlan(
                        coordination_mode=CoordinationMode.UNIFIED,
                        group_ids=["HERO_1", "HERO_2"],
                        placements=[
                            GroupPlacement(
                                placement_id="p1",
                                group_id="HERO_1",
                                template_id="gtpl_accent_flash",
                                start=PlanningTimeRef(bar=1, beat=1),
                                duration=EffectDuration.PHRASE,
                            ),
                            GroupPlacement(
                                placement_id="p2",
                                group_id="HERO_2",
                                template_id="gtpl_accent_flash",
                                start=PlanningTimeRef(bar=1, beat=1),
                                duration=EffectDuration.PHRASE,
                            ),
                        ],
                    ),
                ],
            ),
            LanePlan(
                lane=LaneKind.BASE,
                target_roles=["ARCHES"],
                coordination_plans=[
                    CoordinationPlan(
                        coordination_mode=CoordinationMode.UNIFIED,
                        group_ids=["ARCHES_1"],
                        placements=[
                            GroupPlacement(
                                placement_id="p3",
                                group_id="ARCHES_1",
                                template_id="gtpl_base_glow_warm",
                                start=PlanningTimeRef(bar=1, beat=1),
                                duration=EffectDuration.SECTION,
                            ),
                        ],
                    ),
                ],
            ),
        ],
    )


def create_mock_approve_verdict() -> JudgeVerdict:
    """Create a mock approval verdict."""
    return JudgeVerdict(
        status=VerdictStatus.APPROVE,
        score=8.0,
        confidence=0.9,
        overall_assessment="Good section coordination plan with proper template selection.",
        feedback_for_planner="No changes needed. Plan is ready for holistic evaluation.",
        iteration=1,
        issues=[],
        strengths=["Good template selection", "Proper coordination mode"],
    )


class TestGroupPlannerOrchestratorIntegration:
    """Integration tests for orchestrator with mock LLM."""

    def test_orchestrator_builds_correct_variables(
        self,
        sample_section_context: SectionPlanningContext,
    ) -> None:
        """Orchestrator builds correct planner variables from context."""
        mock_provider = MagicMock()

        orchestrator = GroupPlannerOrchestrator(
            provider=mock_provider,
            max_iterations=3,
            min_pass_score=7.0,
        )

        variables = orchestrator._build_planner_variables(sample_section_context)

        # Verify all expected variables are present (post-context-shaping)
        assert variables["section_id"] == "verse_1"
        assert variables["section_name"] == "verse"
        assert variables["start_ms"] == 0
        assert variables["end_ms"] == 4000
        assert variables["energy_target"] == "MED"
        assert variables["primary_focus_targets"] == ["HERO"]
        assert "display_graph" in variables
        assert "template_catalog" in variables
        # timing_context explicitly excluded via context shaping (not used in prompt)
        assert "timing_context" not in variables
        assert "layer_intents" in variables

    def test_orchestrator_validator_catches_invalid_template(
        self,
        sample_section_context: SectionPlanningContext,
    ) -> None:
        """Orchestrator validator catches invalid template_id."""
        mock_provider = MagicMock()

        orchestrator = GroupPlannerOrchestrator(provider=mock_provider)

        # Build validator
        validator = orchestrator._build_validator(sample_section_context)

        # Create plan with invalid template
        invalid_plan = SectionCoordinationPlan(
            section_id="verse_1",
            theme=_make_section_theme(),
            lane_plans=[
                LanePlan(
                    lane=LaneKind.ACCENT,
                    target_roles=["HERO"],
                    coordination_plans=[
                        CoordinationPlan(
                            coordination_mode=CoordinationMode.UNIFIED,
                            group_ids=["HERO_1"],
                            placements=[
                                GroupPlacement(
                                    placement_id="p1",
                                    group_id="HERO_1",
                                    template_id="INVALID_TEMPLATE",
                                    start=PlanningTimeRef(bar=1, beat=1),
                                    duration=EffectDuration.BURST,
                                ),
                            ],
                        ),
                    ],
                ),
            ],
        )

        # Validate
        errors = validator(invalid_plan)

        # Should have error about invalid template
        assert len(errors) > 0
        assert any("INVALID_TEMPLATE" in e for e in errors)

    def test_orchestrator_validator_passes_valid_plan(
        self,
        sample_section_context: SectionPlanningContext,
    ) -> None:
        """Orchestrator validator passes valid plan."""
        mock_provider = MagicMock()

        orchestrator = GroupPlannerOrchestrator(provider=mock_provider)
        validator = orchestrator._build_validator(sample_section_context)

        valid_plan = create_mock_section_plan()
        errors = validator(valid_plan)

        assert len(errors) == 0

    @pytest.mark.asyncio
    async def test_validates_section_context(
        self,
        sample_display_graph: DisplayGraph,
        sample_template_catalog: TemplateCatalog,
        sample_timing_context: TimingContext,
    ) -> None:
        """Orchestrator validates section context before running."""
        mock_provider = MagicMock()

        # Create context with no primary focus targets
        invalid_context = SectionPlanningContext(
            section_id="verse_1",
            section_name="verse",
            start_ms=0,
            end_ms=4000,
            energy_target="MED",
            motion_density="MED",
            choreography_style="HYBRID",
            primary_focus_targets=[],  # Empty - invalid!
            secondary_targets=[],
            notes=None,
            display_graph=sample_display_graph,
            template_catalog=sample_template_catalog,
            timing_context=sample_timing_context,
        )

        orchestrator = GroupPlannerOrchestrator(provider=mock_provider)

        with pytest.raises(ValueError, match="primary_focus_target"):
            await orchestrator.run(section_context=invalid_context)
