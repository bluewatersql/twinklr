"""Tests for holistic evaluation models and evaluator."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from twinklr.core.agents.sequencer.group_planner.holistic import (
    CrossSectionIssue,
    HolisticEvaluation,
    HolisticEvaluator,
    IssueSeverity,
)
from twinklr.core.agents.shared.judge.models import VerdictStatus
from twinklr.core.sequencer.planning import (
    GroupPlanSet,
    LanePlan,
    SectionCoordinationPlan,
)
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
from twinklr.core.sequencer.vocabulary import (
    CoordinationMode,
    EffectDuration,
    GroupTemplateType,
    GroupVisualIntent,
    LaneKind,
    PlanningTimeRef,
)

from .conftest import DEFAULT_THEME

# Rebuild TemplateInfo after LaneKind is imported (forward ref resolution)
TemplateInfo.model_rebuild()


class TestHolisticEvaluation:
    """Tests for HolisticEvaluation model."""

    def test_create_approved_evaluation(self) -> None:
        """Create approved holistic evaluation."""
        evaluation = HolisticEvaluation(
            status=VerdictStatus.APPROVE,
            score=8.5,
            confidence=0.9,
            summary="Strong coordination across all sections",
            strengths=["Good energy progression", "Consistent template usage"],
            cross_section_issues=[],
            recommendations=[],
        )

        assert evaluation.status == VerdictStatus.APPROVE
        assert evaluation.score == 8.5
        assert evaluation.is_approved

    def test_create_soft_fail_evaluation(self) -> None:
        """Create soft fail holistic evaluation with issues."""
        evaluation = HolisticEvaluation(
            status=VerdictStatus.SOFT_FAIL,
            score=6.0,
            confidence=0.8,
            summary="Needs improvement in energy arc",
            strengths=["Good group coordination"],
            cross_section_issues=[
                CrossSectionIssue(
                    issue_id="ENERGY_FLAT",
                    severity=IssueSeverity.WARN,
                    affected_sections=["verse_1", "verse_2", "chorus_1"],
                    description="Energy stays constant across sections",
                    recommendation="Increase energy in chorus sections",
                ),
            ],
            recommendations=["Add variety to chorus sections"],
        )

        assert evaluation.status == VerdictStatus.SOFT_FAIL
        assert not evaluation.is_approved
        assert len(evaluation.cross_section_issues) == 1

    def test_is_approved_property(self) -> None:
        """is_approved returns True only for APPROVE status."""
        approved = HolisticEvaluation(
            status=VerdictStatus.APPROVE,
            score=7.5,
            confidence=0.85,
            summary="Good",
            strengths=[],
            cross_section_issues=[],
            recommendations=[],
        )
        assert approved.is_approved is True

        soft_fail = HolisticEvaluation(
            status=VerdictStatus.SOFT_FAIL,
            score=6.0,
            confidence=0.8,
            summary="Needs work",
            strengths=[],
            cross_section_issues=[],
            recommendations=[],
        )
        assert soft_fail.is_approved is False


class TestCrossSectionIssue:
    """Tests for CrossSectionIssue model."""

    def test_cross_section_issue_creation(self) -> None:
        """Create cross-section issue."""
        issue = CrossSectionIssue(
            issue_id="TEMPLATE_MONOTONY",
            severity=IssueSeverity.WARN,
            affected_sections=["verse_1", "verse_2"],
            description="Same template used in consecutive sections",
            recommendation="Vary templates between sections",
        )

        assert issue.issue_id == "TEMPLATE_MONOTONY"
        assert len(issue.affected_sections) == 2


@pytest.fixture
def sample_group_plan_set() -> GroupPlanSet:
    """Sample GroupPlanSet with multiple sections."""
    section_1 = SectionCoordinationPlan(
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
                                start=PlanningTimeRef(bar=1, beat=1),
                                duration=EffectDuration.BURST,
                            ),
                        ],
                    ),
                ],
            ),
        ],
    )

    section_2 = SectionCoordinationPlan(
        section_id="chorus_1",
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
                                placement_id="p2",
                                group_id="HERO_1",
                                template_id="gtpl_accent_flash",
                                start=PlanningTimeRef(bar=3, beat=1),
                                duration=EffectDuration.BURST,
                            ),
                        ],
                    ),
                ],
            ),
        ],
    )

    return GroupPlanSet(
        plan_set_id="test_plan_set",
        section_plans=[section_1, section_2],
    )


@pytest.fixture
def sample_display_graph() -> DisplayGraph:
    """Sample display graph."""
    return DisplayGraph(
        display_id="test",
        display_name="Test",
        groups=[
            DisplayGroup(group_id="HERO_1", role="HERO", display_name="Hero 1"),
        ],
    )


@pytest.fixture
def sample_template_catalog() -> TemplateCatalog:
    """Sample template catalog."""
    return TemplateCatalog(
        entries=[
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


class TestHolisticEvaluator:
    """Tests for HolisticEvaluator."""

    def test_evaluator_initialization(self) -> None:
        """Evaluator initializes with default spec."""
        mock_provider = MagicMock()
        evaluator = HolisticEvaluator(provider=mock_provider)

        assert evaluator.holistic_judge_spec is not None
        assert evaluator.holistic_judge_spec.name == "holistic_judge"

    def test_build_judge_variables(
        self,
        sample_group_plan_set: GroupPlanSet,
        sample_display_graph: DisplayGraph,
        sample_template_catalog: TemplateCatalog,
    ) -> None:
        """Evaluator builds correct judge variables."""
        mock_provider = MagicMock()
        evaluator = HolisticEvaluator(provider=mock_provider)

        variables = evaluator._build_judge_variables(
            group_plan_set=sample_group_plan_set,
            display_graph=sample_display_graph,
            template_catalog=sample_template_catalog,
            macro_plan_summary={"global_story": {"theme": "Test theme"}},
        )

        assert "group_plan_set" in variables
        assert "display_graph" in variables
        assert "section_count" in variables
        assert variables["section_count"] == 2
