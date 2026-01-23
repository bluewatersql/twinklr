"""Tests for orchestration state machine."""

import pytest

from blinkb0t.core.agents.state_machine import (
    InvalidTransitionError,
    OrchestrationState,
    OrchestrationStateMachine,
    StateMetrics,
    StateTransition,
)


def test_state_machine_initial_state():
    """Test state machine initializes correctly."""
    sm = OrchestrationStateMachine(max_iterations=3)

    assert sm.current_state == OrchestrationState.INITIALIZED
    assert sm.iteration_count == 0
    assert sm.max_iterations == 3
    assert len(sm.history) == 0


def test_valid_transition():
    """Test valid state transition."""
    sm = OrchestrationStateMachine()

    # Valid transition: INITIALIZED → PLANNING
    assert sm.can_transition_to(OrchestrationState.PLANNING)
    success = sm.transition(OrchestrationState.PLANNING)

    assert success
    assert sm.current_state == OrchestrationState.PLANNING
    assert len(sm.history) == 1


def test_invalid_transition():
    """Test invalid state transition raises error."""
    sm = OrchestrationStateMachine()

    # Invalid transition: INITIALIZED → SUCCEEDED
    assert not sm.can_transition_to(OrchestrationState.SUCCEEDED)

    with pytest.raises(InvalidTransitionError) as exc_info:
        sm.transition(OrchestrationState.SUCCEEDED)

    assert "Invalid transition" in str(exc_info.value)
    assert "initialized → succeeded" in str(exc_info.value).lower()


def test_terminal_states():
    """Test terminal states cannot transition."""
    sm = OrchestrationStateMachine()

    # Transition to terminal state
    sm.current_state = OrchestrationState.SUCCEEDED

    assert sm.is_terminal()

    # Attempt transition from terminal state
    success = sm.transition(OrchestrationState.PLANNING)
    assert not success  # Should return False, not raise
    assert sm.current_state == OrchestrationState.SUCCEEDED  # State unchanged


def test_transition_with_metrics():
    """Test transition records metrics."""
    sm = OrchestrationStateMachine()

    sm.transition(
        OrchestrationState.PLANNING,
        duration_seconds=10.5,
        tokens_consumed=500,
        reason="Starting planning",
    )

    assert len(sm.history) == 1

    transition = sm.history[0]
    assert transition.from_state == OrchestrationState.INITIALIZED
    assert transition.to_state == OrchestrationState.PLANNING
    assert transition.duration_seconds == 10.5
    assert transition.tokens_consumed == 500
    assert transition.reason == "Starting planning"
    assert transition.timestamp > 0


def test_iteration_counting():
    """Test iteration count increments when leaving PLANNING."""
    sm = OrchestrationStateMachine()

    # INITIALIZED → PLANNING (no increment)
    sm.transition(OrchestrationState.PLANNING)
    assert sm.iteration_count == 0

    # PLANNING → VALIDATING (increment)
    sm.transition(OrchestrationState.VALIDATING)
    assert sm.iteration_count == 1

    # VALIDATING → PLANNING (no increment)
    sm.transition(OrchestrationState.PLANNING)
    assert sm.iteration_count == 1

    # PLANNING → VALIDATING (increment)
    sm.transition(OrchestrationState.VALIDATING)
    assert sm.iteration_count == 2


def test_exceeded_max_iterations():
    """Test max iterations check."""
    sm = OrchestrationStateMachine(max_iterations=2)

    assert not sm.exceeded_max_iterations()

    # Simulate 2 iterations
    sm.transition(OrchestrationState.PLANNING)
    sm.transition(OrchestrationState.VALIDATING)  # iteration 1
    sm.transition(OrchestrationState.PLANNING)
    sm.transition(OrchestrationState.VALIDATING)  # iteration 2

    assert sm.exceeded_max_iterations()


def test_get_state_metrics():
    """Test state metrics calculation."""
    sm = OrchestrationStateMachine()

    # Multiple transitions FROM PLANNING
    # INITIALIZED → PLANNING (duration=5.0, tokens=100)
    sm.transition(OrchestrationState.PLANNING, duration_seconds=5.0, tokens_consumed=100)
    # PLANNING → VALIDATING (duration=1.0, tokens=0) - metrics tracked for PLANNING
    sm.transition(OrchestrationState.VALIDATING, duration_seconds=1.0, tokens_consumed=0)
    # VALIDATING → PLANNING (duration=7.0, tokens=200)
    sm.transition(OrchestrationState.PLANNING, duration_seconds=7.0, tokens_consumed=200)
    # PLANNING → VALIDATING (duration=1.5, tokens=0) - metrics tracked for PLANNING
    sm.transition(OrchestrationState.VALIDATING, duration_seconds=1.5, tokens_consumed=0)

    # Get metrics for PLANNING state (transitions FROM planning)
    metrics = sm.get_state_metrics(OrchestrationState.PLANNING)

    assert metrics.state == OrchestrationState.PLANNING
    assert metrics.visit_count == 2  # Two transitions FROM planning
    assert metrics.total_duration_seconds == 2.5  # 1.0 + 1.5 (time spent IN planning)
    assert metrics.total_tokens == 0  # No tokens consumed leaving planning
    assert metrics.avg_duration_seconds == 1.25
    assert metrics.avg_tokens == 0.0


def test_get_all_state_metrics():
    """Test getting metrics for all states."""
    sm = OrchestrationStateMachine()

    sm.transition(OrchestrationState.PLANNING)
    sm.transition(OrchestrationState.VALIDATING)
    sm.transition(OrchestrationState.JUDGING)

    all_metrics = sm.get_all_state_metrics()

    # Should have metrics for all non-terminal states
    assert OrchestrationState.INITIALIZED in all_metrics
    assert OrchestrationState.PLANNING in all_metrics
    assert OrchestrationState.VALIDATING in all_metrics


def test_get_total_metrics():
    """Test total metrics calculation."""
    sm = OrchestrationStateMachine()

    sm.transition(OrchestrationState.PLANNING, duration_seconds=5.0, tokens_consumed=100)
    sm.transition(OrchestrationState.VALIDATING, duration_seconds=1.0, tokens_consumed=0)
    sm.transition(OrchestrationState.JUDGING, duration_seconds=3.0, tokens_consumed=50)

    total = sm.get_total_metrics()

    assert total["total_duration_seconds"] == 9.0
    assert total["total_tokens"] == 150
    assert total["total_transitions"] == 3
    assert total["iteration_count"] == 1
    assert total["current_state"] == "judging"


def test_get_transition_metrics():
    """Test transition pattern metrics."""
    sm = OrchestrationStateMachine()

    # Simulate validation failure loop
    sm.transition(OrchestrationState.PLANNING)
    sm.transition(OrchestrationState.VALIDATING)
    sm.transition(OrchestrationState.PLANNING)  # Retry
    sm.transition(OrchestrationState.VALIDATING)
    sm.transition(OrchestrationState.JUDGING)

    metrics = sm.get_transition_metrics()

    assert metrics["unique_transitions"] == 4
    assert "validating → planning" in metrics["transition_counts"]
    assert metrics["transition_counts"]["validating → planning"] == 1


def test_get_bottleneck_analysis():
    """Test bottleneck detection."""
    sm = OrchestrationStateMachine()

    # Transition with metrics (duration/tokens are for time spent IN that state)
    sm.transition(OrchestrationState.PLANNING, duration_seconds=5.0, tokens_consumed=100)
    sm.transition(OrchestrationState.VALIDATING, duration_seconds=8.0, tokens_consumed=500)
    sm.transition(OrchestrationState.JUDGING, duration_seconds=15.0, tokens_consumed=800)

    bottlenecks = sm.get_bottleneck_analysis()

    # Validating spent most time (8.0s in PLANNING, then transitioned to VALIDATING)
    # Wait, let me think about this more carefully...
    # When we call transition(PLANNING, duration=5.0, tokens=100),
    # we're saying "we spent 5.0s in INITIALIZED state"
    # So the metrics for INITIALIZED would be duration=5.0, tokens=100

    # Let me check what state spent the most time:
    # INITIALIZED → PLANNING: 5.0s, 100 tokens
    # PLANNING → VALIDATING: 8.0s, 500 tokens
    # VALIDATING → JUDGING: 15.0s, 800 tokens

    assert bottlenecks["slowest_state"]["state"] == "validating"  # Spent 15.0s
    assert bottlenecks["slowest_state"]["avg_duration_seconds"] == 15.0

    assert bottlenecks["highest_token_state"]["state"] == "validating"  # Used 800 tokens
    assert bottlenecks["highest_token_state"]["avg_tokens"] == 800.0


def test_format_metrics_report():
    """Test metrics report formatting."""
    sm = OrchestrationStateMachine()

    sm.transition(OrchestrationState.PLANNING, duration_seconds=5.0, tokens_consumed=100)
    sm.transition(OrchestrationState.VALIDATING)
    sm.transition(OrchestrationState.JUDGING, duration_seconds=3.0, tokens_consumed=50)
    sm.transition(OrchestrationState.SUCCEEDED)

    report = sm.format_metrics_report()

    assert "Orchestration Metrics Report" in report
    assert "Final State: succeeded" in report
    assert "Iterations: 1" in report
    assert "Total Duration:" in report
    assert "Total Tokens:" in report


def test_reset():
    """Test state machine reset."""
    sm = OrchestrationStateMachine()

    # Make some transitions
    sm.transition(OrchestrationState.PLANNING)
    sm.transition(OrchestrationState.VALIDATING)

    # Reset
    sm.reset()

    assert sm.current_state == OrchestrationState.INITIALIZED
    assert sm.iteration_count == 0
    assert len(sm.history) == 0


def test_complete_planning_flow():
    """Test complete planning flow: PLANNING → VALIDATING → JUDGING → SUCCEEDED."""
    sm = OrchestrationStateMachine()

    # Start planning
    sm.transition(OrchestrationState.PLANNING)
    assert sm.current_state == OrchestrationState.PLANNING

    # Validate
    sm.transition(OrchestrationState.VALIDATING)
    assert sm.current_state == OrchestrationState.VALIDATING
    assert sm.iteration_count == 1

    # Judge
    sm.transition(OrchestrationState.JUDGING)
    assert sm.current_state == OrchestrationState.JUDGING

    # Success
    sm.transition(OrchestrationState.SUCCEEDED)
    assert sm.current_state == OrchestrationState.SUCCEEDED
    assert sm.is_terminal()


def test_validation_failure_loop():
    """Test validation failure loop: PLANNING → VALIDATING → PLANNING."""
    sm = OrchestrationStateMachine()

    sm.transition(OrchestrationState.PLANNING)
    sm.transition(OrchestrationState.VALIDATING)
    assert sm.iteration_count == 1

    # Validation fails, back to planning
    sm.transition(OrchestrationState.PLANNING, reason="Validation failed")
    assert sm.current_state == OrchestrationState.PLANNING
    assert sm.iteration_count == 1  # Doesn't increment when entering PLANNING

    # Try again
    sm.transition(OrchestrationState.VALIDATING)
    assert sm.iteration_count == 2


def test_judge_failure_retry():
    """Test judge failure retry: JUDGING → PLANNING."""
    sm = OrchestrationStateMachine()

    sm.transition(OrchestrationState.PLANNING)
    sm.transition(OrchestrationState.VALIDATING)
    sm.transition(OrchestrationState.JUDGING)

    # Judge fails, retry planning
    sm.transition(OrchestrationState.PLANNING, reason="Judge failed")
    assert sm.current_state == OrchestrationState.PLANNING


def test_budget_exhausted_from_planning():
    """Test budget exhaustion during planning."""
    sm = OrchestrationStateMachine()

    sm.transition(OrchestrationState.PLANNING)

    # Budget exhausted
    sm.transition(OrchestrationState.BUDGET_EXHAUSTED, reason="Budget exhausted")
    assert sm.current_state == OrchestrationState.BUDGET_EXHAUSTED
    assert sm.is_terminal()


def test_budget_exhausted_from_judging():
    """Test budget exhaustion during judging."""
    sm = OrchestrationStateMachine()

    sm.transition(OrchestrationState.PLANNING)
    sm.transition(OrchestrationState.VALIDATING)
    sm.transition(OrchestrationState.JUDGING)

    # Budget exhausted
    sm.transition(OrchestrationState.BUDGET_EXHAUSTED)
    assert sm.current_state == OrchestrationState.BUDGET_EXHAUSTED
    assert sm.is_terminal()


def test_state_transition_dataclass():
    """Test StateTransition dataclass."""
    transition = StateTransition(
        from_state=OrchestrationState.INITIALIZED,
        to_state=OrchestrationState.PLANNING,
        timestamp=1234567890.0,
        context={"test": "data"},
        reason="Starting",
        duration_seconds=5.0,
        tokens_consumed=100,
    )

    assert transition.from_state == OrchestrationState.INITIALIZED
    assert transition.to_state == OrchestrationState.PLANNING
    assert transition.duration_seconds == 5.0
    assert transition.tokens_consumed == 100
    assert transition.reason == "Starting"


def test_state_metrics_dataclass():
    """Test StateMetrics dataclass."""
    metrics = StateMetrics(
        state=OrchestrationState.PLANNING,
        visit_count=3,
        total_duration_seconds=15.0,
        total_tokens=300,
        avg_duration_seconds=5.0,
        avg_tokens=100.0,
        min_duration_seconds=4.0,
        max_duration_seconds=6.0,
    )

    assert metrics.state == OrchestrationState.PLANNING
    assert metrics.visit_count == 3
    assert metrics.avg_duration_seconds == 5.0
