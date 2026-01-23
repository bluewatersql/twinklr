"""Tests for moving heads agent response models."""

from pydantic import ValidationError
import pytest

from blinkb0t.core.agents.sequencer.moving_heads.models import (
    ChoreographyPlan,
    JudgeDecision,
    JudgeIssue,
    JudgeResponse,
    PlanSection,
    PlanSequence,
    SequenceTiming,
    ValidationIssue,
    ValidationResponse,
)


def test_sequence_timing_model():
    """Test sequence timing model."""
    timing = SequenceTiming(start="0.1", duration_bars=4)

    assert timing.start == "0.1"
    assert timing.duration_bars == 4


def test_plan_sequence_model():
    """Test plan sequence model."""
    sequence = PlanSequence(
        template="sweep_lr_fan_pulse",
        timing=SequenceTiming(start="0.1", duration_bars=8),
        movement="sweep_lr",
        geometry="fan",
        dimmer="pulse",
    )

    assert sequence.template == "sweep_lr_fan_pulse"
    assert sequence.movement == "sweep_lr"
    assert sequence.timing.duration_bars == 8


def test_plan_section_model():
    """Test plan section model."""
    section = PlanSection(
        name="intro",
        start_bar=0,
        end_bar=8,
        energy="low",
        sequences=[
            PlanSequence(
                template="test",
                timing=SequenceTiming(start="0.1", duration_bars=4),
                movement="sweep_lr",
                geometry="fan",
                dimmer="pulse",
            )
        ],
    )

    assert section.name == "intro"
    assert section.start_bar == 0
    assert section.end_bar == 8
    assert section.energy == "low"
    assert len(section.sequences) == 1


def test_choreography_plan_model():
    """Test complete choreography plan model."""
    plan = ChoreographyPlan(
        sections=[
            PlanSection(
                name="intro",
                start_bar=0,
                end_bar=8,
                energy="low",
                sequences=[],
            )
        ]
    )

    assert len(plan.sections) == 1
    assert plan.sections[0].name == "intro"


def test_choreography_plan_validation():
    """Test choreography plan validation."""
    # Missing required fields should fail
    with pytest.raises(ValidationError):
        ChoreographyPlan(sections=[])  # Empty sections

    # Valid plan
    plan = ChoreographyPlan(
        sections=[
            PlanSection(
                name="intro",
                start_bar=0,
                end_bar=8,
                energy="medium",
                sequences=[],
            )
        ]
    )
    assert plan.sections is not None


def test_validation_issue_model():
    """Test validation issue model."""
    issue = ValidationIssue(
        location="intro.sequence_0",
        message="Missing required field",
        severity="error",
    )

    assert issue.location == "intro.sequence_0"
    assert issue.message == "Missing required field"
    assert issue.severity == "error"


def test_validation_response_valid():
    """Test validation response for valid plan."""
    response = ValidationResponse(
        valid=True,
        errors=[],
        warnings=[ValidationIssue(location="verse", message="Short sequence", severity="warning")],
        summary="Plan is valid with 1 warning",
    )

    assert response.valid is True
    assert len(response.errors) == 0
    assert len(response.warnings) == 1


def test_validation_response_invalid():
    """Test validation response for invalid plan."""
    response = ValidationResponse(
        valid=False,
        errors=[ValidationIssue(location="intro", message="Template not found", severity="error")],
        warnings=[],
        summary="Plan has critical errors",
    )

    assert response.valid is False
    assert len(response.errors) == 1
    assert len(response.warnings) == 0


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
                name="intro",
                start_bar=0,
                end_bar=8,
                energy="low",
                sequences=[],
            )
        ]
    )

    validation = ValidationResponse(valid=True, errors=[], warnings=[], summary="OK")

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
    assert validation.model_dump()
    assert judge.model_dump()
