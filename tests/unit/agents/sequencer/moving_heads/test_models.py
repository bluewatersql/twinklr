"""Tests for moving heads agent response models."""

from pydantic import ValidationError
import pytest

from twinklr.core.agents.issues import (
    Issue,
    IssueCategory,
    IssueEffort,
    IssueLocation,
    IssueScope,
    IssueSeverity,
    SuggestedAction,
)
from twinklr.core.agents.sequencer.moving_heads.models import (
    ChoreographyPlan,
    JudgeDecision,
    JudgeIssue,
    JudgeResponse,
    PlanSection,
)


def test_plan_section_model():
    """Test plan section model."""
    section = PlanSection(
        section_name="intro",
        start_bar=1,
        end_bar=8,
        template_id="sweep_lr_fan_pulse",
        preset_id="CHILL",
        modifiers={"intensity": "HIGH"},
        reasoning="Low energy section needs calm movement",
    )

    assert section.section_name == "intro"
    assert section.start_bar == 1
    assert section.end_bar == 8
    assert section.template_id == "sweep_lr_fan_pulse"
    assert section.preset_id == "CHILL"
    assert section.modifiers == {"intensity": "HIGH"}


def test_plan_section_minimal():
    """Test plan section with minimal required fields."""
    section = PlanSection(
        section_name="verse",
        start_bar=1,
        end_bar=16,
        template_id="circle_fan_hold",
    )

    assert section.section_name == "verse"
    assert section.start_bar == 1
    assert section.end_bar == 16
    assert section.template_id == "circle_fan_hold"
    assert section.preset_id is None
    assert section.modifiers == {}


def test_plan_section_bar_validation():
    """Test plan section validates bar range."""
    # Valid section
    section = PlanSection(
        section_name="intro",
        start_bar=1,
        end_bar=8,
        template_id="test",
    )
    assert section.end_bar >= section.start_bar

    # Invalid: end_bar before start_bar
    with pytest.raises(ValidationError):
        PlanSection(
            section_name="intro",
            start_bar=8,
            end_bar=1,
            template_id="test",
        )


def test_plan_section_start_bar_minimum():
    """Test plan section enforces minimum start_bar of 1."""
    # Test valid case with start_bar = 1
    section = PlanSection(
        section_name="intro",
        start_bar=1,
        end_bar=8,
        template_id="test",
    )
    assert section.start_bar == 1

    # Test invalid case with start_bar = 0 (bars are 1-indexed)
    with pytest.raises(ValidationError):
        PlanSection(
            section_name="intro",
            start_bar=0,
            end_bar=8,
            template_id="test",
        )


def test_choreography_plan_model():
    """Test complete choreography plan model."""
    plan = ChoreographyPlan(
        sections=[
            PlanSection(
                section_name="intro",
                start_bar=1,
                end_bar=8,
                template_id="sweep_lr_fan_pulse",
            )
        ],
        overall_strategy="Start calm and build energy",
    )

    assert len(plan.sections) == 1
    assert plan.sections[0].section_name == "intro"
    assert plan.overall_strategy == "Start calm and build energy"


def test_choreography_plan_validation():
    """Test choreography plan validation."""
    # Missing required fields should fail
    with pytest.raises(ValidationError):
        ChoreographyPlan(sections=[])  # Empty sections

    # Valid plan
    plan = ChoreographyPlan(
        sections=[
            PlanSection(
                section_name="intro",
                start_bar=1,
                end_bar=8,
                template_id="circle_fan_hold",
            )
        ]
    )
    assert plan.sections is not None
    assert len(plan.sections) == 1


def test_judge_issue_model():
    """Test judge issue model (alias for Issue)."""
    issue = JudgeIssue(
        issue_id="VARIETY_LOW_VERSE1",
        category=IssueCategory.VARIETY,
        severity=IssueSeverity.WARN,
        estimated_effort=IssueEffort.LOW,
        scope=IssueScope.SECTION,
        location=IssueLocation(section_id="verse_1", bar_start=8, bar_end=24),
        message="Repetitive movement pattern throughout verse",
        fix_hint="Add variety by using different geometry types",
        acceptance_test="Verse_1 should use at least 2 different templates or presets",
        suggested_action=SuggestedAction.PATCH,
    )

    assert issue.issue_id == "VARIETY_LOW_VERSE1"
    assert issue.category == IssueCategory.VARIETY
    assert issue.severity == IssueSeverity.WARN
    assert issue.location.section_id == "verse_1"

    # Verify JudgeIssue is an alias for Issue
    assert type(issue).__name__ == "Issue"


def test_judge_response_approve():
    """Test judge response with APPROVE decision."""
    response = JudgeResponse(
        decision=JudgeDecision.APPROVE,
        score=8.5,
        score_breakdown={"musicality": 9.0, "variety": 8.0, "flow": 8.5},
        confidence=0.9,
        feedback_for_planner="Excellent work, plan is ready to render",
        overall_assessment="Strong choreography with good energy arc and musical synchronization",
        strengths=["Good energy match", "Creative variety"],
        issues=[],
    )

    assert response.decision == JudgeDecision.APPROVE
    assert response.score == 8.5
    assert response.confidence == 0.9
    assert len(response.strengths) == 2
    assert len(response.score_breakdown) == 3


def test_judge_response_soft_fail():
    """Test judge response with SOFT_FAIL decision."""
    response = JudgeResponse(
        decision=JudgeDecision.SOFT_FAIL,
        score=6.5,
        score_breakdown={"musicality": 7.0, "variety": 6.0, "flow": 6.5},
        confidence=0.8,
        feedback_for_planner="Address chorus energy mismatch to improve overall score",
        overall_assessment="Good foundation but needs minor improvements in energy matching",
        strengths=["Good foundation"],
        issues=[
            Issue(
                issue_id="ENERGY_MISMATCH_CHORUS",
                category=IssueCategory.MUSICALITY,
                severity=IssueSeverity.WARN,
                estimated_effort=IssueEffort.MEDIUM,
                scope=IssueScope.SECTION,
                location=IssueLocation(section_id="chorus"),
                message="Energy mismatch in chorus section",
                fix_hint="Increase intensity by using ENERGETIC preset",
                acceptance_test="Chorus energy level >= 70/100",
                suggested_action=SuggestedAction.PATCH,
            )
        ],
    )

    assert response.decision == JudgeDecision.SOFT_FAIL
    assert response.score == 6.5
    assert response.confidence == 0.8
    assert len(response.issues) == 1
    assert response.issues[0].category == IssueCategory.MUSICALITY


def test_judge_response_hard_fail():
    """Test judge response with HARD_FAIL decision."""
    response = JudgeResponse(
        decision=JudgeDecision.HARD_FAIL,
        score=3.0,
        score_breakdown={"musicality": 2.0, "variety": 4.0, "flow": 3.0},
        confidence=0.95,
        feedback_for_planner="Major revision needed: rethink approach to match music structure",
        overall_assessment="Plan fundamentally flawed with no musical synchronization",
        strengths=[],
        issues=[
            Issue(
                issue_id="NO_MUSIC_SYNC_GLOBAL",
                category=IssueCategory.MUSICALITY,
                severity=IssueSeverity.ERROR,
                estimated_effort=IssueEffort.HIGH,
                scope=IssueScope.GLOBAL,
                location=IssueLocation(),
                message="No musical synchronization throughout the plan",
                fix_hint="Rethink entire approach to align with song structure and energy",
                acceptance_test="Musical synchronization score >= 6.0/10",
                suggested_action=SuggestedAction.REPLAN_GLOBAL,
            )
        ],
    )

    assert response.decision == JudgeDecision.HARD_FAIL
    assert response.score == 3.0
    assert response.confidence == 0.95
    assert response.issues[0].severity == IssueSeverity.ERROR


def test_judge_decision_enum():
    """Test judge decision enum values."""
    assert JudgeDecision.APPROVE == "APPROVE"
    assert JudgeDecision.SOFT_FAIL == "SOFT_FAIL"
    assert JudgeDecision.HARD_FAIL == "HARD_FAIL"

    # Should have exactly 3 decisions
    decisions = list(JudgeDecision)
    assert len(decisions) == 3


def test_issue_enums():
    """Test issue-related enum values."""
    # Test IssueCategory
    assert IssueCategory.SCHEMA == "SCHEMA"
    assert IssueCategory.TIMING == "TIMING"
    assert IssueCategory.MUSICALITY == "MUSICALITY"

    # Test IssueSeverity
    assert IssueSeverity.ERROR == "ERROR"
    assert IssueSeverity.WARN == "WARN"
    assert IssueSeverity.NIT == "NIT"

    # Test IssueEffort
    assert IssueEffort.LOW == "LOW"
    assert IssueEffort.MEDIUM == "MEDIUM"
    assert IssueEffort.HIGH == "HIGH"

    # Test IssueScope
    assert IssueScope.GLOBAL == "GLOBAL"
    assert IssueScope.SECTION == "SECTION"

    # Test SuggestedAction
    assert SuggestedAction.PATCH == "PATCH"
    assert SuggestedAction.REPLAN_SECTION == "REPLAN_SECTION"
    assert SuggestedAction.REPLAN_GLOBAL == "REPLAN_GLOBAL"


def test_issue_location_model():
    """Test issue location model."""
    # Full location
    location = IssueLocation(
        section_id="verse_1",
        group_id="front",
        effect_id="sweep",
        bar_start=8,
        bar_end=16,
    )
    assert location.section_id == "verse_1"
    assert location.bar_start == 8

    # Minimal location (all fields optional)
    location_minimal = IssueLocation()
    assert location_minimal.section_id is None
    assert location_minimal.bar_start is None


def test_judge_response_confidence_validation():
    """Test judge confidence validation."""
    # Valid confidence
    response = JudgeResponse(
        decision=JudgeDecision.APPROVE,
        score=8.0,
        score_breakdown={},
        confidence=0.85,
        feedback_for_planner="Good",
        overall_assessment="Approved",
    )
    assert response.confidence == 0.85

    # Invalid confidence (< 0)
    with pytest.raises(ValidationError):
        JudgeResponse(
            decision=JudgeDecision.APPROVE,
            score=8.0,
            score_breakdown={},
            confidence=-0.1,
            feedback_for_planner="",
            overall_assessment="",
        )

    # Invalid confidence (> 1)
    with pytest.raises(ValidationError):
        JudgeResponse(
            decision=JudgeDecision.APPROVE,
            score=8.0,
            score_breakdown={},
            confidence=1.5,
            feedback_for_planner="",
            overall_assessment="",
        )


def test_judge_response_score_validation():
    """Test judge score validation."""
    # Valid scores
    response1 = JudgeResponse(
        decision=JudgeDecision.APPROVE,
        score=10.0,
        score_breakdown={},
        confidence=1.0,
        feedback_for_planner="Perfect",
        overall_assessment="Excellent",
        strengths=[],
        issues=[],
    )
    assert response1.score == 10.0

    response2 = JudgeResponse(
        decision=JudgeDecision.HARD_FAIL,
        score=0.0,
        score_breakdown={},
        confidence=1.0,
        feedback_for_planner="Failed",
        overall_assessment="Poor",
        strengths=[],
        issues=[],
    )
    assert response2.score == 0.0

    # Invalid scores
    with pytest.raises(ValidationError):
        JudgeResponse(
            decision=JudgeDecision.APPROVE,
            score=-1.0,  # Too low
            score_breakdown={},
            confidence=1.0,
            feedback_for_planner="",
            overall_assessment="",
            strengths=[],
            issues=[],
        )

    with pytest.raises(ValidationError):
        JudgeResponse(
            decision=JudgeDecision.APPROVE,
            score=11.0,  # Too high
            score_breakdown={},
            confidence=1.0,
            feedback_for_planner="",
            overall_assessment="",
            strengths=[],
            issues=[],
        )


def test_models_are_serializable():
    """Test all models can be serialized."""
    plan = ChoreographyPlan(
        sections=[
            PlanSection(
                section_name="intro",
                start_bar=1,
                end_bar=8,
                template_id="sweep_lr_fan_pulse",
            )
        ]
    )

    judge = JudgeResponse(
        decision=JudgeDecision.APPROVE,
        score=8.0,
        score_breakdown={"musicality": 8.0},
        confidence=0.9,
        feedback_for_planner="Good",
        overall_assessment="Approved",
        strengths=[],
        issues=[],
    )

    # All should serialize
    assert plan.model_dump()
    assert judge.model_dump()
