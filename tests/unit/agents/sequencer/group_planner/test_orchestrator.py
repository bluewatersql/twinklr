"""Tests for GroupPlannerOrchestrator."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from twinklr.core.agents.sequencer.group_planner.context import SectionPlanningContext
from twinklr.core.agents.sequencer.group_planner.orchestrator import (
    GroupPlannerOrchestrator,
)
from twinklr.core.agents.sequencer.group_planner.timing import (
    BarInfo,
    SectionBounds,
    TimingContext,
)
from twinklr.core.sequencer.planning import LanePlan, SectionCoordinationPlan
from twinklr.core.sequencer.templates.group.catalog import (
    TemplateCatalog,
    TemplateInfo,
)
from twinklr.core.sequencer.templates.group.models import (
    CoordinationPlan,
    DisplayGraph,
    DisplayGroup,
    GroupPlacement,
)
from twinklr.core.sequencer.timing import TimeRef
from twinklr.core.sequencer.vocabulary import (
    CoordinationMode,
    GroupTemplateType,
    GroupVisualIntent,
    LaneKind,
)
from twinklr.core.sequencer.vocabulary.timing import TimeRefKind

from .conftest import DEFAULT_THEME


@pytest.fixture
def mock_provider() -> MagicMock:
    """Create mock LLM provider."""
    provider = MagicMock()
    provider.generate_json_async = AsyncMock()
    return provider


@pytest.fixture
def sample_display_graph() -> DisplayGraph:
    """Sample display graph."""
    return DisplayGraph(
        display_id="test",
        display_name="Test",
        groups=[
            DisplayGroup(group_id="HERO_1", role="HERO", display_name="Hero 1"),
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
    sample_display_graph: DisplayGraph,
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
        primary_focus_targets=["HERO"],
        secondary_targets=["ARCHES"],
        notes=None,
        display_graph=sample_display_graph,
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
                        group_ids=["HERO_1"],
                        placements=[
                            GroupPlacement(
                                placement_id="p1",
                                group_id="HERO_1",
                                template_id="gtpl_accent_flash",
                                start=TimeRef(kind=TimeRefKind.BAR_BEAT, bar=1, beat=1),
                                end=TimeRef(kind=TimeRefKind.BAR_BEAT, bar=1, beat=4),
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
                            group_ids=["HERO_1"],
                            placements=[
                                GroupPlacement(
                                    placement_id="p1",
                                    group_id="HERO_1",
                                    template_id="NONEXISTENT",  # Invalid!
                                    start=TimeRef(kind=TimeRefKind.BAR_BEAT, bar=1, beat=1),
                                    end=TimeRef(kind=TimeRefKind.BAR_BEAT, bar=1, beat=4),
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
