"""Tests for HolisticCorrectorStage — scoped correction and reassembly."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from twinklr.core.agents.issues import ActionType, IssueSeverity, TargetedAction
from twinklr.core.agents.logging import NullLLMCallLogger
from twinklr.core.agents.providers.base import LLMProvider
from twinklr.core.agents.sequencer.group_planner.corrector_stage import (
    HolisticCorrectorStage,
)
from twinklr.core.agents.sequencer.group_planner.holistic import (
    CrossSectionIssue,
    HolisticEvaluation,
)
from twinklr.core.agents.shared.judge.models import VerdictStatus
from twinklr.core.caching.backends.null import NullCache
from twinklr.core.config.models import AppConfig, JobConfig
from twinklr.core.pipeline.context import PipelineContext
from twinklr.core.sequencer.planning import (
    CorrectionResult,
    GroupPlanSet,
    LanePlan,
    SectionCoordinationPlan,
)
from twinklr.core.sequencer.planning.models import PaletteRef
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
        return {}


_TEST_THEME = ThemeRef(
    theme_id="christmas.test",
    scope=ThemeScope.SECTION,
    tags=["test"],
    palette_id=None,
)


def _make_section(
    section_id: str,
    template_id: str = "gtpl_accent_flash",
    target_id: str = "HERO_1",
    start_ms: int | None = 0,
    end_ms: int | None = 10000,
) -> SectionCoordinationPlan:
    return SectionCoordinationPlan(
        section_id=section_id,
        theme=_TEST_THEME,
        motif_ids=["motif_a"],
        palette=PaletteRef(palette_id="core.classic_christmas"),
        lane_plans=[
            LanePlan(
                lane=LaneKind.ACCENT,
                target_roles=["HERO"],
                coordination_plans=[
                    CoordinationPlan(
                        coordination_mode=CoordinationMode.UNIFIED,
                        targets=[PlanTarget(type=TargetType.GROUP, id=target_id)],
                        placements=[
                            GroupPlacement(
                                placement_id="p1",
                                target=PlanTarget(type=TargetType.GROUP, id=target_id),
                                template_id=template_id,
                                start=PlanningTimeRef(bar=1, beat=1),
                                duration=EffectDuration.BURST,
                            ),
                        ],
                    ),
                ],
            ),
        ],
        start_ms=start_ms,
        end_ms=end_ms,
    )


@pytest.fixture
def three_section_plan_set() -> GroupPlanSet:
    """GroupPlanSet with three sections for corrector testing."""
    return GroupPlanSet(
        plan_set_id="test_plan",
        section_plans=[
            _make_section("verse_1", start_ms=0, end_ms=10000),
            _make_section("chorus_1", start_ms=10000, end_ms=20000),
            _make_section("verse_2", start_ms=20000, end_ms=30000),
        ],
    )


@pytest.fixture
def soft_fail_evaluation() -> HolisticEvaluation:
    """Soft fail evaluation with targeted actions on chorus_1 only."""
    return HolisticEvaluation(
        status=VerdictStatus.SOFT_FAIL,
        score=6.5,
        confidence=0.8,
        summary="Template monotony in chorus",
        strengths=["Good energy arc"],
        cross_section_issues=[
            CrossSectionIssue(
                issue_id="VARIETY_LOW",
                severity=IssueSeverity.WARN,
                affected_sections=["chorus_1"],
                description="Chorus uses same template as verse",
                recommendation="Swap template in chorus",
                targeted_actions=[
                    TargetedAction(
                        action_type=ActionType.SWAP_TEMPLATE,
                        section_id="chorus_1",
                        template_id="gtpl_accent_flash",
                        replacement_template_id="gtpl_accent_sparkle",
                        description="Replace flash with sparkle in chorus",
                    ),
                ],
            ),
        ],
        recommendations=["Vary templates"],
    )


@pytest.fixture
def approved_evaluation() -> HolisticEvaluation:
    return HolisticEvaluation(
        status=VerdictStatus.APPROVE,
        score=8.5,
        confidence=0.9,
        summary="Strong coordination",
        strengths=["Good variety"],
        cross_section_issues=[],
        recommendations=[],
    )


@pytest.fixture
def sample_choreo_graph() -> ChoreographyGraph:
    return ChoreographyGraph(
        graph_id="test",
        groups=[ChoreoGroup(id="HERO_1", role="HERO")],
    )


@pytest.fixture
def sample_template_catalog() -> TemplateCatalog:
    return TemplateCatalog(entries=[])


@pytest.fixture
def mock_context() -> PipelineContext:
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


class TestCorrectorStagePassThrough:
    """Tests for pass-through gating conditions."""

    @pytest.mark.asyncio
    async def test_pass_through_when_approved(
        self,
        sample_choreo_graph: ChoreographyGraph,
        sample_template_catalog: TemplateCatalog,
        three_section_plan_set: GroupPlanSet,
        approved_evaluation: HolisticEvaluation,
        mock_context: PipelineContext,
    ) -> None:
        """Stage returns input unchanged when evaluation is APPROVE."""
        plan_set = three_section_plan_set.model_copy(
            update={"holistic_evaluation": approved_evaluation}
        )
        stage = HolisticCorrectorStage(
            choreo_graph=sample_choreo_graph,
            template_catalog=sample_template_catalog,
        )

        result = await stage.execute(plan_set, mock_context)

        assert result.success is True
        assert result.output is plan_set

    @pytest.mark.asyncio
    async def test_pass_through_when_no_evaluation(
        self,
        sample_choreo_graph: ChoreographyGraph,
        sample_template_catalog: TemplateCatalog,
        three_section_plan_set: GroupPlanSet,
        mock_context: PipelineContext,
    ) -> None:
        """Stage returns input unchanged when no evaluation is attached."""
        stage = HolisticCorrectorStage(
            choreo_graph=sample_choreo_graph,
            template_catalog=sample_template_catalog,
        )

        result = await stage.execute(three_section_plan_set, mock_context)

        assert result.success is True
        assert result.output is three_section_plan_set


class TestCorrectorStageReassembly:
    """Tests for CorrectionResult reassembly into GroupPlanSet."""

    def test_reassemble_splices_corrected_section(
        self,
        sample_choreo_graph: ChoreographyGraph,
        sample_template_catalog: TemplateCatalog,
        three_section_plan_set: GroupPlanSet,
        soft_fail_evaluation: HolisticEvaluation,
    ) -> None:
        """Reassembly replaces the corrected section and preserves others."""
        stage = HolisticCorrectorStage(
            choreo_graph=sample_choreo_graph,
            template_catalog=sample_template_catalog,
        )

        corrected_chorus = _make_section(
            "chorus_1", template_id="gtpl_accent_sparkle", start_ms=None, end_ms=None
        )
        correction = CorrectionResult(corrected_sections=[corrected_chorus])
        affected = {"chorus_1"}

        result = stage._reassemble_plan(
            three_section_plan_set, correction, affected, soft_fail_evaluation
        )

        assert result is not None
        assert len(result.section_plans) == 3
        ids = [s.section_id for s in result.section_plans]
        assert ids == ["verse_1", "chorus_1", "verse_2"]

        chorus = next(s for s in result.section_plans if s.section_id == "chorus_1")
        assert chorus.lane_plans[0].coordination_plans[0].placements[0].template_id == (
            "gtpl_accent_sparkle"
        )
        # Timing restored from original
        assert chorus.start_ms == 10000
        assert chorus.end_ms == 20000

        # Unmodified sections are original objects
        verse_1 = next(s for s in result.section_plans if s.section_id == "verse_1")
        assert verse_1.start_ms == 0

    def test_reassemble_preserves_holistic_evaluation(
        self,
        sample_choreo_graph: ChoreographyGraph,
        sample_template_catalog: TemplateCatalog,
        three_section_plan_set: GroupPlanSet,
        soft_fail_evaluation: HolisticEvaluation,
    ) -> None:
        """Reassembly attaches the holistic evaluation to the result."""
        stage = HolisticCorrectorStage(
            choreo_graph=sample_choreo_graph,
            template_catalog=sample_template_catalog,
        )

        correction = CorrectionResult(
            corrected_sections=[_make_section("chorus_1", template_id="gtpl_accent_sparkle")]
        )

        result = stage._reassemble_plan(
            three_section_plan_set, correction, {"chorus_1"}, soft_fail_evaluation
        )

        assert result is not None
        assert result.holistic_evaluation is soft_fail_evaluation

    def test_reassemble_rejects_hallucinated_section_id(
        self,
        sample_choreo_graph: ChoreographyGraph,
        sample_template_catalog: TemplateCatalog,
        three_section_plan_set: GroupPlanSet,
        soft_fail_evaluation: HolisticEvaluation,
    ) -> None:
        """Reassembly rejects section IDs not in the affected set."""
        stage = HolisticCorrectorStage(
            choreo_graph=sample_choreo_graph,
            template_catalog=sample_template_catalog,
        )

        hallucinated = _make_section("verse_2", template_id="gtpl_accent_sparkle")
        correction = CorrectionResult(corrected_sections=[hallucinated])
        # verse_2 is NOT in the affected set
        affected = {"chorus_1"}

        result = stage._reassemble_plan(
            three_section_plan_set, correction, affected, soft_fail_evaluation
        )

        assert result is None

    def test_reassemble_rejects_unknown_section_id(
        self,
        sample_choreo_graph: ChoreographyGraph,
        sample_template_catalog: TemplateCatalog,
        three_section_plan_set: GroupPlanSet,
        soft_fail_evaluation: HolisticEvaluation,
    ) -> None:
        """Reassembly rejects a section_id that doesn't exist in the original plan."""
        stage = HolisticCorrectorStage(
            choreo_graph=sample_choreo_graph,
            template_catalog=sample_template_catalog,
        )

        unknown = _make_section("bridge_1", template_id="gtpl_accent_sparkle")
        correction = CorrectionResult(corrected_sections=[unknown])
        affected = {"bridge_1"}

        result = stage._reassemble_plan(
            three_section_plan_set, correction, affected, soft_fail_evaluation
        )

        assert result is None


class TestCorrectorStageValidation:
    """Tests for heuristic validation of corrected plan."""

    def test_validate_passes_for_structurally_valid_plan(
        self,
        sample_choreo_graph: ChoreographyGraph,
        sample_template_catalog: TemplateCatalog,
        three_section_plan_set: GroupPlanSet,
        mock_context: PipelineContext,
    ) -> None:
        """Valid plan passes heuristic validation."""
        stage = HolisticCorrectorStage(
            choreo_graph=sample_choreo_graph,
            template_catalog=sample_template_catalog,
        )

        assert stage._validate_corrected_plan(three_section_plan_set, ["chorus_1"], mock_context)

    def test_validate_fails_for_empty_targets(
        self,
        sample_choreo_graph: ChoreographyGraph,
        sample_template_catalog: TemplateCatalog,
        mock_context: PipelineContext,
    ) -> None:
        """Validation catches coordination plan with empty targets."""
        bad_section = SectionCoordinationPlan(
            section_id="chorus_1",
            theme=_TEST_THEME,
            motif_ids=["motif_a"],
            lane_plans=[
                LanePlan(
                    lane=LaneKind.ACCENT,
                    target_roles=["HERO"],
                    coordination_plans=[
                        CoordinationPlan(
                            coordination_mode=CoordinationMode.UNIFIED,
                            targets=[PlanTarget(type=TargetType.GROUP, id="HERO_1")],
                            placements=[],
                        ),
                        # This one will fail validation
                    ],
                ),
            ],
        )
        # Override targets to be empty (bypassing min_length at construction)
        bad_coord = CoordinationPlan(
            coordination_mode=CoordinationMode.UNIFIED,
            targets=[PlanTarget(type=TargetType.GROUP, id="X")],
            placements=[],
        )
        object.__setattr__(bad_coord, "targets", [])

        bad_section.lane_plans[0].coordination_plans = [bad_coord]

        plan_set = GroupPlanSet(
            plan_set_id="test",
            section_plans=[bad_section],
        )

        stage = HolisticCorrectorStage(
            choreo_graph=sample_choreo_graph,
            template_catalog=TemplateCatalog(entries=[]),
        )

        assert not stage._validate_corrected_plan(plan_set, ["chorus_1"], mock_context)

    def test_validate_fails_for_empty_motif_ids(
        self,
        sample_choreo_graph: ChoreographyGraph,
        sample_template_catalog: TemplateCatalog,
        mock_context: PipelineContext,
    ) -> None:
        """Validation catches empty motif_ids on modified section."""
        section = _make_section("chorus_1")
        section.motif_ids = []

        plan_set = GroupPlanSet(
            plan_set_id="test",
            section_plans=[section],
        )

        stage = HolisticCorrectorStage(
            choreo_graph=sample_choreo_graph,
            template_catalog=sample_template_catalog,
        )

        assert not stage._validate_corrected_plan(plan_set, ["chorus_1"], mock_context)


class TestCorrectorStageContextShaping:
    """Tests for scoped context shaping."""

    def test_context_shaping_scopes_to_affected_sections(
        self,
        three_section_plan_set: GroupPlanSet,
        soft_fail_evaluation: HolisticEvaluation,
    ) -> None:
        """Context shaping sends affected sections at full detail,
        others as summaries.
        """
        from twinklr.core.agents.sequencer.group_planner.context_shaping import (
            shape_holistic_corrector_context,
        )

        variables = shape_holistic_corrector_context(
            group_plan_set=three_section_plan_set,
            holistic_evaluation=soft_fail_evaluation,
        )

        assert "affected_sections_json" in variables
        assert "section_summaries" in variables
        assert "affected_section_ids" in variables

        assert "chorus_1" in variables["affected_section_ids"]

        # Non-affected sections should be summaries (dicts with section_id + template_ids)
        summary_ids = [s["section_id"] for s in variables["section_summaries"]]
        assert "verse_1" in summary_ids
        assert "verse_2" in summary_ids
        assert "chorus_1" not in summary_ids

    def test_context_shaping_extracts_affected_ids_from_actions(
        self,
    ) -> None:
        """Affected section IDs are deduped from both affected_sections
        and targeted_actions.section_id fields.
        """
        from twinklr.core.agents.sequencer.group_planner.context_shaping import (
            shape_holistic_corrector_context,
        )

        plan_set = GroupPlanSet(
            plan_set_id="test",
            section_plans=[
                _make_section("verse_1"),
                _make_section("chorus_1"),
                _make_section("verse_2"),
            ],
        )

        evaluation = HolisticEvaluation(
            status=VerdictStatus.SOFT_FAIL,
            score=6.0,
            confidence=0.8,
            summary="Issues",
            strengths=[],
            cross_section_issues=[
                CrossSectionIssue(
                    issue_id="ISSUE_1",
                    severity=IssueSeverity.WARN,
                    affected_sections=["verse_1"],
                    description="Desc",
                    recommendation="Fix",
                    targeted_actions=[
                        TargetedAction(
                            action_type=ActionType.SWAP_TEMPLATE,
                            section_id="chorus_1",
                            template_id="a",
                            replacement_template_id="b",
                            description="Swap",
                        ),
                    ],
                ),
            ],
        )

        variables = shape_holistic_corrector_context(
            group_plan_set=plan_set,
            holistic_evaluation=evaluation,
        )

        # Both verse_1 (from affected_sections) and chorus_1 (from action.section_id)
        assert set(variables["affected_section_ids"]) == {"verse_1", "chorus_1"}

        # Only verse_2 should be a summary
        summary_ids = [s["section_id"] for s in variables["section_summaries"]]
        assert summary_ids == ["verse_2"]


class TestCorrectionResultModel:
    """Tests for CorrectionResult model."""

    def test_creation_with_corrected_sections(self) -> None:
        """CorrectionResult requires at least one corrected section."""
        section = _make_section("chorus_1")
        result = CorrectionResult(corrected_sections=[section])

        assert len(result.corrected_sections) == 1
        assert result.corrected_sections[0].section_id == "chorus_1"
        assert result.correction_notes is None

    def test_creation_with_notes(self) -> None:
        section = _make_section("chorus_1")
        result = CorrectionResult(
            corrected_sections=[section],
            correction_notes="Swapped template for variety",
        )

        assert result.correction_notes == "Swapped template for variety"

    def test_rejects_empty_sections_list(self) -> None:
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            CorrectionResult(corrected_sections=[])
