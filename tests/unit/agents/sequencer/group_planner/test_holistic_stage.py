"""Tests for holistic evaluator pipeline stage."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

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
    GroupPlanSet,
    LanePlan,
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
    CoordinationMode,
    EffectDuration,
    LaneKind,
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
        recommendations=[],
    )


class TestExtractMacroPlanSummary:
    """Tests for _extract_macro_plan_summary helper."""

    def test_extract_expected_section_ids_from_pydantic_model(self) -> None:
        """Extract expected section IDs from a Pydantic MacroPlan model."""
        from twinklr.core.agents.sequencer.group_planner.holistic_stage import (
            _extract_macro_plan_summary,
        )

        mock_section_1 = MagicMock()
        mock_section_1.section = MagicMock()
        mock_section_1.section.section_id = "intro"

        mock_section_2 = MagicMock()
        mock_section_2.section = MagicMock()
        mock_section_2.section.section_id = "chorus_1"

        mock_macro_plan = MagicMock()
        mock_macro_plan.global_story = MagicMock()
        mock_macro_plan.global_story.model_dump.return_value = {"theme": "test"}
        mock_macro_plan.section_plans = [mock_section_1, mock_section_2]

        summary = _extract_macro_plan_summary(mock_macro_plan)

        assert "expected_section_ids" in summary
        assert summary["expected_section_ids"] == ["intro", "chorus_1"]

    def test_extract_expected_section_ids_from_dict(self) -> None:
        """Extract expected section IDs from a dict (cached) MacroPlan."""
        from twinklr.core.agents.sequencer.group_planner.holistic_stage import (
            _extract_macro_plan_summary,
        )

        macro_plan_dict = {
            "global_story": {"theme": "test"},
            "section_plans": [
                {"section": {"section_id": "verse_1"}},
                {"section": {"section_id": "chorus_1"}},
                {"section": {"section_id": "outro"}},
            ],
        }

        summary = _extract_macro_plan_summary(macro_plan_dict)

        assert "expected_section_ids" in summary
        assert summary["expected_section_ids"] == ["verse_1", "chorus_1", "outro"]

    def test_extract_expected_section_ids_none_macro_plan(self) -> None:
        """Return empty dict when macro_plan is None."""
        from twinklr.core.agents.sequencer.group_planner.holistic_stage import (
            _extract_macro_plan_summary,
        )

        summary = _extract_macro_plan_summary(None)
        assert summary == {}

    def test_extract_expected_section_ids_no_section_plans(self) -> None:
        """Handle MacroPlan without section_plans gracefully."""
        from twinklr.core.agents.sequencer.group_planner.holistic_stage import (
            _extract_macro_plan_summary,
        )

        mock_macro_plan = MagicMock()
        mock_macro_plan.global_story = MagicMock()
        mock_macro_plan.global_story.model_dump.return_value = {"theme": "test"}
        mock_macro_plan.section_plans = None
        # Simulate getattr returning None
        del mock_macro_plan.section_plans
        mock_macro_plan.configure_mock(section_plans=None)

        summary = _extract_macro_plan_summary(mock_macro_plan)

        assert "global_story" in summary
        assert summary.get("expected_section_ids", []) == []


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
    ) -> None:
        """execute() reads macro_plan from context state and passes to evaluator."""
        stage = HolisticEvaluatorStage(
            choreo_graph=sample_choreo_graph,
            template_catalog=sample_template_catalog,
        )

        mock_global_story = MagicMock()
        mock_global_story.model_dump.return_value = {"theme": "Holiday magic"}
        mock_macro_plan = MagicMock()
        mock_macro_plan.global_story = mock_global_story
        mock_context.set_state("macro_plan", mock_macro_plan)

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
        assert "global_story" in call_kwargs["macro_plan_summary"]
