"""Tests for holistic evaluation models and evaluator."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from twinklr.core.agents.issues import ActionType, IssueCategory, IssueSeverity, TargetedAction
from twinklr.core.agents.sequencer.group_planner.holistic import (
    CrossSectionIssue,
    HolisticEvaluation,
    HolisticEvaluator,
    cross_section_issues_to_issues,
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
    GroupPlacement,
)
from twinklr.core.sequencer.templates.group.models.choreography import (
    ChoreographyGraph,
    ChoreoGroup,
)
from twinklr.core.sequencer.templates.group.models.coordination import PlanTarget
from twinklr.core.sequencer.vocabulary import (
    CoordinationMode,
    EffectDuration,
    GroupTemplateType,
    GroupVisualIntent,
    LaneKind,
    PlanningTimeRef,
)
from twinklr.core.sequencer.vocabulary.choreography import TargetType

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

    def test_cross_section_issue_with_targeted_actions(self) -> None:
        """Targeted actions provide specific group plan changes."""
        issue = CrossSectionIssue(
            issue_id="GROUP_UNDERUTILIZED",
            severity=IssueSeverity.WARN,
            affected_sections=["chorus_1", "instrumental"],
            description="ARCHES group is absent in key sections",
            recommendation="Add ARCHES to high-energy sections",
            targeted_actions=[
                TargetedAction(
                    action_type=ActionType.ADD_TARGET,
                    section_id="chorus_1",
                    lane="RHYTHM",
                    target="group:ARCHES",
                    template_id="gtpl_rhythm_sparkle_beat",
                    description="Add ARCHES to RHYTHM lane with gtpl_rhythm_sparkle_beat",
                ),
                TargetedAction(
                    action_type=ActionType.ADD_TARGET,
                    section_id="instrumental",
                    lane="BASE",
                    target="group:ARCHES",
                    template_id="gtpl_base_candy_stripes",
                    description="Add ARCHES to BASE lane with gtpl_base_candy_stripes",
                ),
            ],
        )

        assert len(issue.targeted_actions) == 2
        assert issue.targeted_actions[0].section_id == "chorus_1"
        assert "ARCHES" in (issue.targeted_actions[0].target or "")

    def test_cross_section_issue_targeted_actions_default_empty(self) -> None:
        """Targeted actions default to empty list when not provided."""
        issue = CrossSectionIssue(
            issue_id="NIT_ISSUE",
            severity=IssueSeverity.NIT,
            affected_sections=["verse_1"],
            description="Minor style concern",
            recommendation="Consider adjusting",
        )

        assert issue.targeted_actions == []


class TestCrossSectionIssuesToIssues:
    """Tests for cross_section_issues_to_issues function."""

    def test_cross_section_issues_to_issues_basic(self) -> None:
        """Converts a CrossSectionIssue to Issue with correct fields."""
        csi = CrossSectionIssue(
            issue_id="ENERGY_FLAT",
            severity=IssueSeverity.WARN,
            affected_sections=["verse_1", "verse_2"],
            description="Energy stays constant across sections",
            recommendation="Increase energy in chorus",
        )
        issues = cross_section_issues_to_issues([csi])

        assert len(issues) == 1
        assert issues[0].issue_id == "ENERGY_FLAT"
        assert issues[0].severity == IssueSeverity.WARN
        assert issues[0].message == (
            "Energy stays constant across sections (affects: verse_1, verse_2)"
        )
        assert issues[0].fix_hint == "Increase energy in chorus"
        assert issues[0].location.section_id == "verse_1"
        assert issues[0].scope.value == "GLOBAL"

    def test_cross_section_issues_to_issues_preserves_targeted_actions(self) -> None:
        """TargetedAction list is carried over from CrossSectionIssue to Issue."""
        action = TargetedAction(
            action_type=ActionType.ADD_TARGET,
            section_id="chorus_1",
            lane="RHYTHM",
            target="group:ARCHES",
            description="Add ARCHES to RHYTHM lane",
        )
        csi = CrossSectionIssue(
            issue_id="GROUP_UNDERUTILIZED",
            severity=IssueSeverity.WARN,
            affected_sections=["chorus_1", "instrumental"],
            description="ARCHES group absent",
            recommendation="Add ARCHES to sections",
            targeted_actions=[action],
        )
        issues = cross_section_issues_to_issues([csi])

        assert len(issues) == 1
        assert len(issues[0].targeted_actions) == 1
        assert issues[0].targeted_actions[0].action_type == ActionType.ADD_TARGET
        assert issues[0].targeted_actions[0].target == "group:ARCHES"

    def test_cross_section_issues_to_issues_infers_category(self) -> None:
        """energy -> CONTRAST_DYNAMICS, variety -> VARIETY, etc."""
        cases = [
            ("ENERGY_FLAT", IssueCategory.CONTRAST_DYNAMICS),
            ("LOW_ENERGY_ARC", IssueCategory.CONTRAST_DYNAMICS),
            ("VARIETY_LOW", IssueCategory.VARIETY),
            ("TEMPLATE_REPETITION", IssueCategory.VARIETY),
            ("MONOTONY_CHORUS", IssueCategory.VARIETY),
            ("PALETTE_OVERUSE", IssueCategory.PALETTE),
            ("COLOR_MISMATCH", IssueCategory.PALETTE),
            ("MOTIF_INCONSISTENCY", IssueCategory.MOTIF_COHESION),
            ("LAYERING_IMBALANCE", IssueCategory.LAYERING),
            ("TRANSITION_ABRUPT", IssueCategory.COORDINATION),
            ("COVERAGE_GAP", IssueCategory.COVERAGE),
            ("THEME_MISMATCH", IssueCategory.STYLE),
        ]
        for issue_id, expected_category in cases:
            csi = CrossSectionIssue(
                issue_id=issue_id,
                severity=IssueSeverity.WARN,
                affected_sections=["verse_1"],
                description="Test",
                recommendation="Fix it",
            )
            issues = cross_section_issues_to_issues([csi])
            assert len(issues) == 1
            assert issues[0].category == expected_category, (
                f"issue_id={issue_id} expected {expected_category} got {issues[0].category}"
            )


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
                        targets=[PlanTarget(type=TargetType.GROUP, id="HERO_1")],
                        placements=[
                            GroupPlacement(
                                placement_id="p2",
                                target=PlanTarget(type=TargetType.GROUP, id="HERO_1"),
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
def sample_choreo_graph() -> ChoreographyGraph:
    """Sample choreography graph."""
    return ChoreographyGraph(
        graph_id="test",
        groups=[
            ChoreoGroup(id="HERO_1", role="HERO"),
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
        sample_choreo_graph: ChoreographyGraph,
        sample_template_catalog: TemplateCatalog,
    ) -> None:
        """Evaluator builds correct judge variables."""
        mock_provider = MagicMock()
        evaluator = HolisticEvaluator(provider=mock_provider)

        variables = evaluator._build_judge_variables(
            group_plan_set=sample_group_plan_set,
            choreo_graph=sample_choreo_graph,
            template_catalog=sample_template_catalog,
            macro_plan_summary={"global_story": {"theme": "Test theme"}},
        )

        assert "group_plan_set" in variables
        assert "display_graph" in variables
        assert "section_count" in variables
        assert variables["section_count"] == 2
