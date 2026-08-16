"""Tests for holistic evaluator pipeline stage."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from twinklr.core.agents.audio.profile.models import SongSectionRef
from twinklr.core.agents.logging import NullLLMCallLogger
from twinklr.core.agents.providers.base import LLMProvider
from twinklr.core.agents.sequencer.group_planner.holistic import (
    HolisticEvaluation,
    HolisticEvaluator,
)
from twinklr.core.agents.sequencer.group_planner.holistic_stage import (
    HolisticEvaluatorStage,
)
from twinklr.core.agents.shared.judge.models import VerdictStatus
from twinklr.core.caching.backends.null import NullCache
from twinklr.core.config.models import AppConfig, JobConfig
from twinklr.core.pipeline.context import PipelineContext
from twinklr.core.sequencer.planning import (
    FocalAssignment,
    FocalRole,
    FocalRoleKind,
    GroupPlanSet,
    LanePlan,
    MacroPlan,
    MacroSection,
    PaletteRef,
    PaletteRoleRef,
    PaletteStop,
    PaletteTransition,
    SectionCoordinationPlan,
)
from twinklr.core.sequencer.templates.group.catalog import TemplateCatalog
from twinklr.core.sequencer.templates.group.models import (
    CoordinationPlan,
    GroupPlacement,
)
from twinklr.core.sequencer.templates.group.models.choreography import (
    ChoreographyGraph,
    ChoreoGroup,
)
from twinklr.core.sequencer.templates.group.models.coordination import PlanTarget
from twinklr.core.sequencer.theming import ThemeRef, ThemeScope
from twinklr.core.sequencer.vocabulary import (
    ChoreographyStyle,
    CoordinationMode,
    EffectDuration,
    EnergyTarget,
    LaneKind,
    MotionDensity,
    PlanningTimeRef,
)
from twinklr.core.sequencer.vocabulary.choreography import TargetType


class MockProvider(LLMProvider):
    """Mock LLM provider for testing."""

    async def generate_json_async(self, *args: object, **kwargs: object) -> dict[str, object]:
        """Return empty dict."""
        return {}


_TEST_THEME = ThemeRef(
    theme_id="christmas.test",
    scope=ThemeScope.SECTION,
    tags=["test"],
    palette_id=None,
)


@pytest.fixture
def sample_macro_plan() -> MacroPlan:
    """Minimal valid typed macro contract."""
    target = PlanTarget(type=TargetType.GROUP, id="HERO_1")
    section = MacroSection(
        section=SongSectionRef(section_id="verse_1", name="Verse", start_ms=0, end_ms=10_000),
        energy_target=EnergyTarget.MED,
        motion_density=MotionDensity.MED,
        choreography_style=ChoreographyStyle.HYBRID,
        palette_role=PaletteRoleRef(stop_id="main", override=None),
        theme=_TEST_THEME,
        motif_ids=[],
        focal_roles=[FocalRole(target=target, role=FocalRoleKind.LEAD)],
        call_response_pairs=[],
        coordination_intent=CoordinationMode.UNIFIED,
        notes="Typed holistic macro guidance for the section.",
    )
    return MacroPlan(
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


@pytest.fixture
def mock_context() -> PipelineContext:
    """Create mock pipeline context with NullCache."""
    app_config = AppConfig.model_validate(
        {
            "cache": {"base_dir": "cache", "enabled": False},
            "logging": {"level": "INFO", "format": "json"},
        }
    )
    job_config = JobConfig.model_validate(
        {
            "agent": {
                "max_iterations": 3,
                "plan_agent": {"model": "gpt-5.2"},
                "validate_agent": {"model": "gpt-5.2"},
                "judge_agent": {"model": "gpt-5.2"},
                "llm_logging": {"enabled": False},
            }
        }
    )

    mock_session = MagicMock()
    mock_session.app_config = app_config
    mock_session.job_config = job_config
    mock_session.session_id = "test_session_123"
    mock_session.llm_provider = MockProvider()
    mock_session.agent_cache = NullCache()
    mock_session.llm_logger = NullLLMCallLogger()

    return PipelineContext(session=mock_session)


@pytest.fixture
def sample_choreo_graph() -> ChoreographyGraph:
    """Minimal choreography graph."""
    return ChoreographyGraph(
        graph_id="test",
        groups=[ChoreoGroup(id="HERO_1", role="HERO")],
    )


@pytest.fixture
def sample_template_catalog() -> TemplateCatalog:
    """Minimal template catalog."""
    return TemplateCatalog(entries=[])


@pytest.fixture
def sample_group_plan_set() -> GroupPlanSet:
    """Minimal group plan set with one section."""
    return GroupPlanSet(
        plan_set_id="test_plan",
        section_plans=[
            SectionCoordinationPlan(
                section_id="verse_1",
                theme=_TEST_THEME,
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
                                        duration=EffectDuration.BURST,
                                    ),
                                ],
                            ),
                        ],
                    ),
                ],
            ),
        ],
    )


@pytest.fixture
def approved_evaluation() -> HolisticEvaluation:
    """Sample approved evaluation result."""
    return HolisticEvaluation(
        status=VerdictStatus.APPROVE,
        score=8.5,
        confidence=0.9,
        summary="Strong coordination",
        strengths=["Good variety"],
        cross_section_issues=[],
    )


class TestExtractMacroPlanSummary:
    """Tests for _extract_macro_plan_summary helper."""

    def test_extract_expected_section_ids_from_pydantic_model(
        self, sample_macro_plan: MacroPlan
    ) -> None:
        """Extract expected section IDs from a Pydantic MacroPlan model."""
        from twinklr.core.agents.sequencer.group_planner.holistic_stage import (
            _extract_macro_plan_summary,
        )

        summary = _extract_macro_plan_summary(sample_macro_plan)

        assert "expected_section_ids" in summary
        assert summary["expected_section_ids"] == ["verse_1"]
        assert summary["macro_plan"] == sample_macro_plan.reader_projection()

    def test_extract_expected_section_ids_from_dict(self, sample_macro_plan: MacroPlan) -> None:
        """Extract expected section IDs from a dict (cached) MacroPlan."""
        from twinklr.core.agents.sequencer.group_planner.holistic_stage import (
            _extract_macro_plan_summary,
        )

        summary = _extract_macro_plan_summary(sample_macro_plan.model_dump(mode="json"))

        assert "expected_section_ids" in summary
        assert summary["expected_section_ids"] == ["verse_1"]

    def test_extract_expected_section_ids_none_macro_plan(self) -> None:
        """Return empty dict when macro_plan is None."""
        from twinklr.core.agents.sequencer.group_planner.holistic_stage import (
            _extract_macro_plan_summary,
        )

        summary = _extract_macro_plan_summary(None)
        assert summary == {}


class TestHolisticEvaluatorStage:
    """Tests for HolisticEvaluatorStage."""

    def test_stage_name(
        self,
        sample_choreo_graph: ChoreographyGraph,
        sample_template_catalog: TemplateCatalog,
    ) -> None:
        """Stage reports correct name."""
        stage = HolisticEvaluatorStage(
            choreo_graph=sample_choreo_graph,
            template_catalog=sample_template_catalog,
        )
        assert stage.name == "holistic_evaluator"

    @pytest.mark.asyncio
    async def test_execute_passes_through_group_plan_set(
        self,
        sample_choreo_graph: ChoreographyGraph,
        sample_template_catalog: TemplateCatalog,
        sample_group_plan_set: GroupPlanSet,
        approved_evaluation: HolisticEvaluation,
        mock_context: PipelineContext,
    ) -> None:
        """execute() returns the original GroupPlanSet (pass-through)."""
        stage = HolisticEvaluatorStage(
            choreo_graph=sample_choreo_graph,
            template_catalog=sample_template_catalog,
        )

        with (
            patch.object(
                HolisticEvaluator,
                "evaluate",
                new_callable=AsyncMock,
                return_value=approved_evaluation,
            ),
            patch.object(
                HolisticEvaluator,
                "get_cache_key",
                new_callable=AsyncMock,
                return_value="mock_cache_key",
            ),
        ):
            result = await stage.execute(sample_group_plan_set, mock_context)

        assert result.success is True
        assert result.output.plan_set_id == sample_group_plan_set.plan_set_id
        assert result.output.holistic_evaluation is not None
        assert result.output.holistic_evaluation.status == VerdictStatus.APPROVE

    @pytest.mark.asyncio
    async def test_execute_stores_evaluation_in_state(
        self,
        sample_choreo_graph: ChoreographyGraph,
        sample_template_catalog: TemplateCatalog,
        sample_group_plan_set: GroupPlanSet,
        approved_evaluation: HolisticEvaluation,
        mock_context: PipelineContext,
    ) -> None:
        """execute() stores HolisticEvaluation in context state."""
        stage = HolisticEvaluatorStage(
            choreo_graph=sample_choreo_graph,
            template_catalog=sample_template_catalog,
        )

        with (
            patch.object(
                HolisticEvaluator,
                "evaluate",
                new_callable=AsyncMock,
                return_value=approved_evaluation,
            ),
            patch.object(
                HolisticEvaluator,
                "get_cache_key",
                new_callable=AsyncMock,
                return_value="mock_cache_key",
            ),
        ):
            await stage.execute(sample_group_plan_set, mock_context)

        stored = mock_context.get_state("holistic_evaluator_result")
        assert stored is not None
        assert isinstance(stored, HolisticEvaluation)
        assert stored.score == 8.5

    @pytest.mark.asyncio
    async def test_execute_tracks_metrics(
        self,
        sample_choreo_graph: ChoreographyGraph,
        sample_template_catalog: TemplateCatalog,
        sample_group_plan_set: GroupPlanSet,
        approved_evaluation: HolisticEvaluation,
        mock_context: PipelineContext,
    ) -> None:
        """execute() adds holistic score, status, and issues count to metrics."""
        stage = HolisticEvaluatorStage(
            choreo_graph=sample_choreo_graph,
            template_catalog=sample_template_catalog,
        )

        with (
            patch.object(
                HolisticEvaluator,
                "evaluate",
                new_callable=AsyncMock,
                return_value=approved_evaluation,
            ),
            patch.object(
                HolisticEvaluator,
                "get_cache_key",
                new_callable=AsyncMock,
                return_value="mock_cache_key",
            ),
        ):
            await stage.execute(sample_group_plan_set, mock_context)

        assert mock_context.metrics["holistic_score"] == 8.5
        assert mock_context.metrics["holistic_status"] == "APPROVE"
        assert mock_context.metrics["holistic_issues_count"] == 0

    @pytest.mark.asyncio
    async def test_execute_failure_returns_failure_result(
        self,
        sample_choreo_graph: ChoreographyGraph,
        sample_template_catalog: TemplateCatalog,
        sample_group_plan_set: GroupPlanSet,
        mock_context: PipelineContext,
    ) -> None:
        """execute() returns failure StageResult on unhandled exception."""
        stage = HolisticEvaluatorStage(
            choreo_graph=sample_choreo_graph,
            template_catalog=sample_template_catalog,
        )

        with (
            patch.object(
                HolisticEvaluator,
                "evaluate",
                new_callable=AsyncMock,
                side_effect=ValueError("LLM provider error"),
            ),
            patch.object(
                HolisticEvaluator,
                "get_cache_key",
                new_callable=AsyncMock,
                return_value="mock_cache_key",
            ),
        ):
            result = await stage.execute(sample_group_plan_set, mock_context)

        assert result.success is False
        assert result.error is not None
        assert "LLM provider error" in result.error

    @pytest.mark.asyncio
    async def test_execute_reads_macro_plan_from_state(
        self,
        sample_choreo_graph: ChoreographyGraph,
        sample_template_catalog: TemplateCatalog,
        sample_group_plan_set: GroupPlanSet,
        approved_evaluation: HolisticEvaluation,
        mock_context: PipelineContext,
        sample_macro_plan: MacroPlan,
    ) -> None:
        """execute() reads macro_plan from context state and passes to evaluator."""
        stage = HolisticEvaluatorStage(
            choreo_graph=sample_choreo_graph,
            template_catalog=sample_template_catalog,
        )

        mock_context.set_state("macro_plan", sample_macro_plan)

        with (
            patch.object(
                HolisticEvaluator,
                "evaluate",
                new_callable=AsyncMock,
                return_value=approved_evaluation,
            ) as mock_evaluate,
            patch.object(
                HolisticEvaluator,
                "get_cache_key",
                new_callable=AsyncMock,
                return_value="mock_cache_key",
            ),
        ):
            result = await stage.execute(sample_group_plan_set, mock_context)

        assert result.success is True
        call_kwargs = mock_evaluate.call_args.kwargs
        assert "macro_plan_summary" in call_kwargs
        assert (
            call_kwargs["macro_plan_summary"]["macro_plan"] == sample_macro_plan.reader_projection()
        )
