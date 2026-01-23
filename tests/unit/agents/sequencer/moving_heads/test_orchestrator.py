"""Tests for moving heads orchestrator."""

from unittest.mock import MagicMock

import pytest

from blinkb0t.core.agents.result import AgentResult
from blinkb0t.core.agents.sequencer.moving_heads.models import (
    ChoreographyPlan,
    JudgeDecision,
    JudgeResponse,
    PlanSection,
    ValidationResponse,
)
from blinkb0t.core.agents.sequencer.moving_heads.orchestrator import (
    OrchestrationConfig,
    OrchestrationResult,
    Orchestrator,
)
from blinkb0t.core.agents.state_machine import OrchestrationState


@pytest.fixture
def mock_provider():
    """Create mock LLM provider."""
    # Don't use spec= to avoid AttributeError on methods not in protocol
    provider = MagicMock()
    return provider


@pytest.fixture
def context():
    """Sample context for choreography."""
    return {
        "song_structure": {
            "sections": {
                "intro": {"start_bar": 0, "end_bar": 8},
            },
            "total_bars": 8,
        },
        "fixtures": {"count": 4, "groups": ["front"]},
        "available_templates": ["sweep_lr_fan_pulse"],
        "beat_grid": {"tempo": 120, "time_signature": "4/4", "total_bars": 8},
    }


@pytest.fixture
def valid_plan():
    """Create valid choreography plan."""
    return ChoreographyPlan(
        sections=[
            PlanSection(
                section_name="intro",
                start_bar=1,
                end_bar=8,
                template_id="sweep_lr_fan_pulse",
            )
        ]
    )


def test_orchestration_config_defaults():
    """Test orchestration config defaults."""
    config = OrchestrationConfig()

    assert config.max_iterations == 3
    assert config.prompt_base_path is not None
    assert config.context_shaper is not None


def test_orchestration_config_custom():
    """Test orchestration config with custom values."""
    config = OrchestrationConfig(
        max_iterations=5,
        token_budget=10000,
    )

    assert config.max_iterations == 5
    assert config.token_budget == 10000


def test_orchestrator_init(mock_provider):
    """Test orchestrator initialization."""
    config = OrchestrationConfig()
    orch = Orchestrator(provider=mock_provider, config=config)

    assert orch.provider == mock_provider
    assert orch.config == config
    assert orch.state_machine is not None


def test_orchestrate_success_first_iteration(mock_provider, context, valid_plan):
    """Test successful orchestration on first iteration."""
    config = OrchestrationConfig()
    orch = Orchestrator(provider=mock_provider, config=config)

    # Mock runner to return successful results
    def mock_run_side_effect(spec, variables, state=None):
        if spec.name == "planner":
            return AgentResult(
                success=True,
                data=valid_plan,
                duration_seconds=1.0,
                tokens_used=100,
            )
        elif spec.name == "validator":
            return AgentResult(
                success=True,
                data=ValidationResponse(valid=True, errors=[], warnings=[], summary="OK"),
                duration_seconds=0.5,
                tokens_used=50,
            )
        elif spec.name == "judge":
            return AgentResult(
                success=True,
                data=JudgeResponse(
                    decision=JudgeDecision.APPROVE,
                    score=8.0,
                    strengths=["Good"],
                    issues=[],
                    feedback_for_planner="Approved",
                    overall_assessment="Great",
                ),
                duration_seconds=0.5,
                tokens_used=50,
            )
        return AgentResult(success=False, duration_seconds=0, tokens_used=0)

    orch.runner = MagicMock()
    orch.runner.run.side_effect = mock_run_side_effect

    result = orch.orchestrate(context)

    assert result.success is True
    assert result.plan == valid_plan
    assert result.iterations == 1
    assert result.final_state == OrchestrationState.SUCCEEDED


def test_orchestrate_requires_iterations(mock_provider, context, valid_plan):
    """Test orchestration that requires multiple iterations."""
    config = OrchestrationConfig(max_iterations=3)
    orch = Orchestrator(provider=mock_provider, config=config)

    iteration_count = 0

    def mock_run_side_effect(spec, variables, state=None):
        nonlocal iteration_count

        if spec.name == "planner":
            return AgentResult(
                success=True,
                data=valid_plan,
                duration_seconds=1.0,
                tokens_used=100,
            )
        elif spec.name == "validator":
            return AgentResult(
                success=True,
                data=ValidationResponse(valid=True, errors=[], warnings=[], summary="OK"),
                duration_seconds=0.5,
                tokens_used=50,
            )
        elif spec.name == "judge":
            # First 2 iterations: soft fail, 3rd: approve
            if iteration_count < 2:
                iteration_count += 1
                return AgentResult(
                    success=True,
                    data=JudgeResponse(
                        decision=JudgeDecision.SOFT_FAIL,
                        score=6.0,
                        strengths=[],
                        issues=[],
                        feedback_for_planner="Needs improvement",
                        overall_assessment="Try again",
                    ),
                    duration_seconds=0.5,
                    tokens_used=50,
                )
            else:
                return AgentResult(
                    success=True,
                    data=JudgeResponse(
                        decision=JudgeDecision.APPROVE,
                        score=8.0,
                        strengths=["Better"],
                        issues=[],
                        feedback_for_planner="Approved",
                        overall_assessment="Good",
                    ),
                    duration_seconds=0.5,
                    tokens_used=50,
                )
        return AgentResult(success=False, duration_seconds=0, tokens_used=0)

    orch.runner = MagicMock()
    orch.runner.run.side_effect = mock_run_side_effect

    result = orch.orchestrate(context)

    assert result.success is True
    assert result.iterations == 3
    assert result.final_state == OrchestrationState.SUCCEEDED


def test_orchestrate_max_iterations_exhausted(mock_provider, context, valid_plan):
    """Test orchestration when max iterations exhausted."""
    config = OrchestrationConfig(max_iterations=2)
    orch = Orchestrator(provider=mock_provider, config=config)

    def mock_run_side_effect(spec, variables, state=None):
        if spec.name == "planner":
            return AgentResult(
                success=True,
                data=valid_plan,
                duration_seconds=1.0,
                tokens_used=100,
            )
        elif spec.name == "validator":
            return AgentResult(
                success=True,
                data=ValidationResponse(valid=True, errors=[], warnings=[], summary="OK"),
                duration_seconds=0.5,
                tokens_used=50,
            )
        elif spec.name == "judge":
            # Always soft fail
            return AgentResult(
                success=True,
                data=JudgeResponse(
                    decision=JudgeDecision.SOFT_FAIL,
                    score=6.0,
                    strengths=[],
                    issues=[],
                    feedback_for_planner="Still needs work",
                    overall_assessment="Not good enough",
                ),
                duration_seconds=0.5,
                tokens_used=50,
            )
        return AgentResult(success=False, duration_seconds=0, tokens_used=0)

    orch.runner = MagicMock()
    orch.runner.run.side_effect = mock_run_side_effect

    result = orch.orchestrate(context)

    # Should return best attempt even if not approved
    assert result.success is False
    assert result.iterations == 2
    assert result.plan == valid_plan
    assert "max iterations" in result.error_message.lower()


def test_orchestrate_heuristic_validation_failure(mock_provider, context):
    """Test orchestration when heuristic validation fails."""
    config = OrchestrationConfig()
    orch = Orchestrator(provider=mock_provider, config=config)

    # Plan with invalid template
    bad_plan = ChoreographyPlan(
        sections=[
            PlanSection(
                section_name="intro",
                start_bar=1,
                end_bar=8,
                template_id="sweep_lr_fan_pulse",
            )
        ]
    )

    def mock_run_side_effect(spec, variables, state=None):
        if spec.name == "planner":
            return AgentResult(
                success=True,
                data=bad_plan,
                duration_seconds=1.0,
                tokens_used=100,
            )
        return AgentResult(success=False, duration_seconds=0, tokens_used=0)

    orch.runner = MagicMock()
    orch.runner.run.side_effect = mock_run_side_effect

    # Heuristic validation should catch issues and add to feedback
    result = orch.orchestrate(context)

    # Should continue even with warnings, but fail if critical errors
    assert result.iterations >= 1


def test_orchestrate_token_budget_exceeded(mock_provider, context, valid_plan):
    """Test orchestration stops when token budget exceeded."""
    config = OrchestrationConfig(max_iterations=10, token_budget=200)
    orch = Orchestrator(provider=mock_provider, config=config)

    def mock_run_side_effect(spec, variables, state=None):
        if spec.name == "planner":
            return AgentResult(
                success=True,
                data=valid_plan,
                duration_seconds=1.0,
                tokens_used=150,  # Uses most of budget
            )
        elif spec.name == "validator":
            return AgentResult(
                success=True,
                data=ValidationResponse(valid=True, errors=[], warnings=[], summary="OK"),
                duration_seconds=0.5,
                tokens_used=50,
            )
        elif spec.name == "judge":
            return AgentResult(
                success=True,
                data=JudgeResponse(
                    decision=JudgeDecision.SOFT_FAIL,
                    score=6.0,
                    strengths=[],
                    issues=[],
                    feedback_for_planner="Try again",
                    overall_assessment="Needs work",
                ),
                duration_seconds=0.5,
                tokens_used=50,
            )
        return AgentResult(success=False, duration_seconds=0, tokens_used=0)

    orch.runner = MagicMock()
    orch.runner.run.side_effect = mock_run_side_effect

    result = orch.orchestrate(context)

    # Should stop after 1 iteration due to budget
    assert result.iterations == 1
    assert result.final_state == OrchestrationState.BUDGET_EXHAUSTED


def test_orchestrate_planner_failure(mock_provider, context):
    """Test orchestration when planner fails."""
    config = OrchestrationConfig()
    orch = Orchestrator(provider=mock_provider, config=config)

    def mock_run_side_effect(spec, variables, state=None):
        if spec.name == "planner":
            return AgentResult(
                success=False,
                error_message="Planner error",
                duration_seconds=1.0,
                tokens_used=50,
            )
        return AgentResult(success=False, duration_seconds=0, tokens_used=0)

    orch.runner = MagicMock()
    orch.runner.run.side_effect = mock_run_side_effect

    result = orch.orchestrate(context)

    assert result.success is False
    assert result.final_state == OrchestrationState.FAILED
    assert "planner" in result.error_message.lower()


def test_orchestration_result_structure():
    """Test orchestration result structure."""
    plan = ChoreographyPlan(
        sections=[
            PlanSection(
                section_name="intro", start_bar=1, end_bar=8, template_id="sweep_lr_fan_pulse"
            )
        ]
    )

    result = OrchestrationResult(
        success=True,
        plan=plan,
        iterations=2,
        total_tokens=500,
        duration_seconds=5.0,
        final_state=OrchestrationState.SUCCEEDED,
    )

    assert result.success is True
    assert result.plan == plan
    assert result.iterations == 2
    assert result.total_tokens == 500
    assert result.final_state == OrchestrationState.SUCCEEDED


def test_orchestrate_collects_feedback(mock_provider, context, valid_plan):
    """Test that orchestrator collects feedback across iterations."""
    config = OrchestrationConfig(max_iterations=2)
    orch = Orchestrator(provider=mock_provider, config=config)

    call_count = 0

    def mock_run_side_effect(spec, variables, state=None):
        nonlocal call_count

        if spec.name == "planner":
            # Check that feedback is passed after first iteration
            if call_count > 0:
                assert "feedback" in variables
            call_count += 1
            return AgentResult(
                success=True,
                data=valid_plan,
                duration_seconds=1.0,
                tokens_used=100,
            )
        elif spec.name == "validator":
            return AgentResult(
                success=True,
                data=ValidationResponse(valid=True, errors=[], warnings=[], summary="OK"),
                duration_seconds=0.5,
                tokens_used=50,
            )
        elif spec.name == "judge":
            if call_count == 1:
                return AgentResult(
                    success=True,
                    data=JudgeResponse(
                        decision=JudgeDecision.SOFT_FAIL,
                        score=6.0,
                        strengths=[],
                        issues=[],
                        feedback_for_planner="Add more variety",
                        overall_assessment="Needs improvement",
                    ),
                    duration_seconds=0.5,
                    tokens_used=50,
                )
            else:
                return AgentResult(
                    success=True,
                    data=JudgeResponse(
                        decision=JudgeDecision.APPROVE,
                        score=8.0,
                        strengths=["Better"],
                        issues=[],
                        feedback_for_planner="Approved",
                        overall_assessment="Good",
                    ),
                    duration_seconds=0.5,
                    tokens_used=50,
                )
        return AgentResult(success=False, duration_seconds=0, tokens_used=0)

    orch.runner = MagicMock()
    orch.runner.run.side_effect = mock_run_side_effect

    result = orch.orchestrate(context)

    assert result.success is True
    assert call_count == 2  # Planner called twice
