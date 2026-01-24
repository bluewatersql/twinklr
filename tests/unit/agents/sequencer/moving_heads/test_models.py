"""Tests for moving heads agent response models."""

from pydantic import ValidationError
import pytest

from blinkb0t.core.agents.sequencer.moving_heads.models import (
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
    """Test judge issue model."""
    issue = JudgeIssue(
        severity="minor",
        location="verse_1",
        issue="Repetitive movement",
        suggestion="Add variety",
    )

    assert issue.severity == "minor"
    assert issue.location == "verse_1"


def test_judge_response_approve():
    """Test judge response with APPROVE decision."""
    response = JudgeResponse(
        decision=JudgeDecision.APPROVE,
        score=8.5,
        strengths=["Good energy match", "Creative variety"],
        issues=[],
        feedback_for_planner="Excellent work",
        overall_assessment="Ready to render",
    )

    assert response.decision == JudgeDecision.APPROVE
    assert response.score == 8.5
    assert len(response.strengths) == 2


def test_judge_response_soft_fail():
    """Test judge response with SOFT_FAIL decision."""
    response = JudgeResponse(
        decision=JudgeDecision.SOFT_FAIL,
        score=6.5,
        strengths=["Good foundation"],
        issues=[
            JudgeIssue(
                severity="moderate",
                location="chorus",
                issue="Energy mismatch",
                suggestion="Increase intensity",
            )
        ],
        feedback_for_planner="Address chorus energy",
        overall_assessment="Needs minor improvements",
    )

    assert response.decision == JudgeDecision.SOFT_FAIL
    assert response.score == 6.5
    assert len(response.issues) == 1


def test_judge_response_hard_fail():
    """Test judge response with HARD_FAIL decision."""
    response = JudgeResponse(
        decision=JudgeDecision.HARD_FAIL,
        score=3.0,
        strengths=[],
        issues=[
            JudgeIssue(
                severity="critical",
                location="overall",
                issue="No musical synchronization",
                suggestion="Rethink entire approach",
            )
        ],
        feedback_for_planner="Major revision needed",
        overall_assessment="Plan fundamentally flawed",
    )

    assert response.decision == JudgeDecision.HARD_FAIL
    assert response.score == 3.0


def test_judge_decision_enum():
    """Test judge decision enum values."""
    assert JudgeDecision.APPROVE == "APPROVE"
    assert JudgeDecision.SOFT_FAIL == "SOFT_FAIL"
    assert JudgeDecision.HARD_FAIL == "HARD_FAIL"

    # Should have exactly 3 decisions
    decisions = list(JudgeDecision)
    assert len(decisions) == 3


def test_judge_response_score_validation():
    """Test judge score validation."""
    # Valid scores
    response1 = JudgeResponse(
        decision=JudgeDecision.APPROVE,
        score=10.0,
        strengths=[],
        issues=[],
        feedback_for_planner="",
        overall_assessment="",
    )
    assert response1.score == 10.0

    response2 = JudgeResponse(
        decision=JudgeDecision.HARD_FAIL,
        score=0.0,
        strengths=[],
        issues=[],
        feedback_for_planner="",
        overall_assessment="",
    )
    assert response2.score == 0.0

    # Invalid scores
    with pytest.raises(ValidationError):
        JudgeResponse(
            decision=JudgeDecision.APPROVE,
            score=-1.0,  # Too low
            strengths=[],
            issues=[],
            feedback_for_planner="",
            overall_assessment="",
        )

    with pytest.raises(ValidationError):
        JudgeResponse(
            decision=JudgeDecision.APPROVE,
            score=11.0,  # Too high
            strengths=[],
            issues=[],
            feedback_for_planner="",
            overall_assessment="",
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
        strengths=[],
        issues=[],
        feedback_for_planner="Good",
        overall_assessment="Approved",
    )

    # All should serialize
    assert plan.model_dump()
    assert judge.model_dump()
