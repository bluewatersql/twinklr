# Orchestration State Machine Specification

**Status:** Design Phase  
**Date:** 2026-01-20  
**Updated:** 2026-01-21  
**Related:** `design.md`

## Overview

This document specifies the state machine pattern for managing orchestration flow with enhanced observability metrics, replacing the manual iteration loop in `Orchestrator`.

## State Definitions

### State Enum

```python
from enum import Enum

class OrchestrationState(str, Enum):
    """Orchestration state machine states."""
    INITIALIZED = "initialized"
    PLANNING = "planning"
    VALIDATING = "validating"
    IMPLEMENTING = "implementing"
    JUDGING = "judging"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    BUDGET_EXHAUSTED = "budget_exhausted"
```

### State Descriptions

- **INITIALIZED**: Initial state before pipeline starts
- **PLANNING**: Generating choreography plan
- **VALIDATING**: Running heuristic validation on plan
- **IMPLEMENTING**: Expanding plan to detailed implementation
- **JUDGING**: Evaluating plan and implementation quality
- **SUCCEEDED**: Pipeline completed successfully (evaluation passed)
- **FAILED**: Pipeline failed (error occurred)
- **BUDGET_EXHAUSTED**: Token budget exhausted (integrated with existing budget system)

## State Transitions

### Valid Transitions

```
INITIALIZED
  → PLANNING
  → FAILED

PLANNING
  → VALIDATING
  → FAILED
  → BUDGET_EXHAUSTED

VALIDATING
  → IMPLEMENTING (success)
  → PLANNING (failure - retry with feedback)
  → FAILED

IMPLEMENTING
  → JUDGING
  → FAILED
  → BUDGET_EXHAUSTED

JUDGING
  → SUCCEEDED (pass_threshold=True)
  → IMPLEMENTING (soft failure - refine implementation)
  → PLANNING (hard failure - replan)
  → FAILED
```

### Transition Rules

1. **Validation Failure**: Always transitions back to PLANNING (with feedback)
2. **Judge Soft Failure**: Transitions to IMPLEMENTING (refine implementation)
3. **Judge Hard Failure**: Transitions to PLANNING (replan)
4. **Budget Exhausted**: Can occur from PLANNING or IMPLEMENTING (uses existing budget system)
5. **Success**: Only from JUDGING when `pass_threshold=True`

## Implementation

### Enhanced State Transition with Metrics

```python
from dataclasses import dataclass, field
from enum import Enum
import time
import logging
from typing import Any

logger = logging.getLogger(__name__)

@dataclass
class StateTransition:
    """Record of state transition with observability metrics."""
    from_state: OrchestrationState
    to_state: OrchestrationState
    timestamp: float
    context: dict[str, Any]
    reason: str | None = None
    
    # Observability metrics
    duration_seconds: float = 0.0
    tokens_consumed: int = 0

@dataclass
class StateMetrics:
    """Aggregated metrics for a state."""
    state: OrchestrationState
    visit_count: int = 0
    total_duration_seconds: float = 0.0
    total_tokens: int = 0
    avg_duration_seconds: float = 0.0
    avg_tokens: float = 0.0
    min_duration_seconds: float = float('inf')
    max_duration_seconds: float = 0.0
```

### State Machine Class

```python
class InvalidTransitionError(Exception):
    """Raised when invalid state transition is attempted."""
    pass

class OrchestrationStateMachine:
    """State machine for orchestration flow with observability."""
    
    VALID_TRANSITIONS: dict[OrchestrationState, list[OrchestrationState]] = {
        OrchestrationState.INITIALIZED: [
            OrchestrationState.PLANNING,
            OrchestrationState.FAILED,
        ],
        OrchestrationState.PLANNING: [
            OrchestrationState.VALIDATING,
            OrchestrationState.FAILED,
            OrchestrationState.BUDGET_EXHAUSTED,
        ],
        OrchestrationState.VALIDATING: [
            OrchestrationState.IMPLEMENTING,
            OrchestrationState.PLANNING,  # Retry on failure
            OrchestrationState.FAILED,
        ],
        OrchestrationState.IMPLEMENTING: [
            OrchestrationState.JUDGING,
            OrchestrationState.FAILED,
            OrchestrationState.BUDGET_EXHAUSTED,
        ],
        OrchestrationState.JUDGING: [
            OrchestrationState.SUCCEEDED,
            OrchestrationState.IMPLEMENTING,  # Soft failure
            OrchestrationState.PLANNING,  # Hard failure
            OrchestrationState.FAILED,
        ],
    }
    
    # Terminal states (no transitions out)
    TERMINAL_STATES = {
        OrchestrationState.SUCCEEDED,
        OrchestrationState.FAILED,
        OrchestrationState.BUDGET_EXHAUSTED,
    }
    
    def __init__(self):
        """Initialize state machine."""
        self.current_state = OrchestrationState.INITIALIZED
        self.history: list[StateTransition] = []
        self.iteration_count = 0
        self.max_iterations = 3
    
    def transition(
        self,
        to_state: OrchestrationState,
        context: dict[str, Any] | None = None,
        reason: str | None = None,
        duration_seconds: float = 0.0,
        tokens_consumed: int = 0
    ) -> bool:
        """Transition to new state with metrics tracking.
        
        Args:
            to_state: Target state
            context: Optional context data for transition
            reason: Optional reason for transition
            duration_seconds: Time spent in previous state
            tokens_consumed: Tokens used in previous state
        
        Returns:
            True if transition succeeded
        
        Raises:
            InvalidTransitionError: If transition is invalid
        """
        # Check if transition is valid
        if not self.can_transition_to(to_state):
            raise InvalidTransitionError(
                f"Invalid transition: {self.current_state.value} → {to_state.value}. "
                f"Valid transitions: {[s.value for s in self.VALID_TRANSITIONS.get(self.current_state, [])]}"
            )
        
        # Check if already in terminal state
        if self.current_state in self.TERMINAL_STATES:
            logger.warning(
                f"Attempted transition from terminal state {self.current_state.value} → {to_state.value}"
            )
            return False
        
        # Record transition with metrics
        transition = StateTransition(
            from_state=self.current_state,
            to_state=to_state,
            timestamp=time.time(),
            context=context or {},
            reason=reason,
            duration_seconds=duration_seconds,
            tokens_consumed=tokens_consumed
        )
        
        self.history.append(transition)
        
        # Update state
        old_state = self.current_state
        self.current_state = to_state
        
        # Increment iteration count when leaving planning
        if old_state == OrchestrationState.PLANNING:
            self.iteration_count += 1
        
        logger.info(
            f"State transition: {old_state.value} → {to_state.value} "
            f"(iteration {self.iteration_count}, duration: {duration_seconds:.2f}s, "
            f"tokens: {tokens_consumed}, reason: {reason or 'none'})"
        )
        
        return True
    
    def can_transition_to(self, state: OrchestrationState) -> bool:
        """Check if transition to state is valid.
        
        Args:
            state: Target state
        
        Returns:
            True if transition is valid
        """
        valid_targets = self.VALID_TRANSITIONS.get(self.current_state, [])
        return state in valid_targets
    
    def is_terminal(self) -> bool:
        """Check if current state is terminal.
        
        Returns:
            True if in terminal state
        """
        return self.current_state in self.TERMINAL_STATES
    
    def get_transition_history(self) -> list[StateTransition]:
        """Get transition history.
        
        Returns:
            List of state transitions
        """
        return self.history.copy()
    
    def reset(self) -> None:
        """Reset state machine to initial state."""
        self.current_state = OrchestrationState.INITIALIZED
        self.history.clear()
        self.iteration_count = 0
    
    def exceeded_max_iterations(self) -> bool:
        """Check if max iterations exceeded.
        
        Returns:
            True if iteration count exceeds max
        """
        return self.iteration_count >= self.max_iterations
    
    # ========== OBSERVABILITY METHODS ==========
    
    def get_state_metrics(self, state: OrchestrationState) -> StateMetrics:
        """Get aggregated metrics for a specific state.
        
        Args:
            state: State to get metrics for
        
        Returns:
            StateMetrics with aggregated data
        """
        # Find all transitions FROM this state
        state_transitions = [
            t for t in self.history
            if t.from_state == state
        ]
        
        if not state_transitions:
            return StateMetrics(
                state=state,
                visit_count=0,
                total_duration_seconds=0.0,
                total_tokens=0,
                avg_duration_seconds=0.0,
                avg_tokens=0.0
            )
        
        durations = [t.duration_seconds for t in state_transitions]
        tokens = [t.tokens_consumed for t in state_transitions]
        
        return StateMetrics(
            state=state,
            visit_count=len(state_transitions),
            total_duration_seconds=sum(durations),
            total_tokens=sum(tokens),
            avg_duration_seconds=sum(durations) / len(durations),
            avg_tokens=sum(tokens) / len(tokens),
            min_duration_seconds=min(durations),
            max_duration_seconds=max(durations)
        )
    
    def get_all_state_metrics(self) -> dict[OrchestrationState, StateMetrics]:
        """Get metrics for all states.
        
        Returns:
            Dict mapping state to its metrics
        """
        return {
            state: self.get_state_metrics(state)
            for state in OrchestrationState
            if state not in self.TERMINAL_STATES
        }
    
    def get_total_metrics(self) -> dict[str, Any]:
        """Get total pipeline metrics.
        
        Returns:
            Dict with total duration, tokens, and visit counts
        """
        total_duration = sum(t.duration_seconds for t in self.history)
        total_tokens = sum(t.tokens_consumed for t in self.history)
        
        # Count visits per state
        state_visits = {}
        for transition in self.history:
            state = transition.from_state
            state_visits[state.value] = state_visits.get(state.value, 0) + 1
        
        return {
            "total_duration_seconds": total_duration,
            "total_tokens": total_tokens,
            "total_transitions": len(self.history),
            "iteration_count": self.iteration_count,
            "state_visits": state_visits,
            "current_state": self.current_state.value
        }
    
    def get_transition_metrics(self) -> dict[str, Any]:
        """Get metrics about transition patterns.
        
        Returns:
            Dict with transition counts and patterns
        """
        transition_counts = {}
        
        for t in self.history:
            key = f"{t.from_state.value} → {t.to_state.value}"
            transition_counts[key] = transition_counts.get(key, 0) + 1
        
        # Find most common transition
        most_common = max(transition_counts.items(), key=lambda x: x[1]) if transition_counts else None
        
        return {
            "transition_counts": transition_counts,
            "most_common_transition": most_common[0] if most_common else None,
            "most_common_count": most_common[1] if most_common else 0,
            "unique_transitions": len(transition_counts)
        }
    
    def get_bottleneck_analysis(self) -> dict[str, Any]:
        """Identify bottlenecks in the pipeline.
        
        Returns:
            Dict with slowest states and highest token consumers
        """
        all_metrics = self.get_all_state_metrics()
        
        # Find states with data
        states_with_data = [
            m for m in all_metrics.values()
            if m.visit_count > 0
        ]
        
        if not states_with_data:
            return {
                "slowest_state": None,
                "highest_token_state": None,
                "avg_duration_per_iteration": 0.0,
                "avg_tokens_per_iteration": 0.0
            }
        
        # Find bottlenecks
        slowest = max(states_with_data, key=lambda m: m.avg_duration_seconds)
        highest_tokens = max(states_with_data, key=lambda m: m.avg_tokens)
        
        total_metrics = self.get_total_metrics()
        
        return {
            "slowest_state": {
                "state": slowest.state.value,
                "avg_duration_seconds": slowest.avg_duration_seconds,
                "total_duration_seconds": slowest.total_duration_seconds,
                "visit_count": slowest.visit_count
            },
            "highest_token_state": {
                "state": highest_tokens.state.value,
                "avg_tokens": highest_tokens.avg_tokens,
                "total_tokens": highest_tokens.total_tokens,
                "visit_count": highest_tokens.visit_count
            },
            "avg_duration_per_iteration": (
                total_metrics["total_duration_seconds"] / self.iteration_count
                if self.iteration_count > 0 else 0.0
            ),
            "avg_tokens_per_iteration": (
                total_metrics["total_tokens"] / self.iteration_count
                if self.iteration_count > 0 else 0.0
            )
        }
    
    def format_metrics_report(self) -> str:
        """Generate human-readable metrics report.
        
        Returns:
            Formatted metrics string
        """
        total = self.get_total_metrics()
        bottlenecks = self.get_bottleneck_analysis()
        transition_metrics = self.get_transition_metrics()
        
        report = [
            "=== Orchestration Metrics Report ===",
            f"\nFinal State: {total['current_state']}",
            f"Iterations: {total['iteration_count']} / {self.max_iterations}",
            f"Total Duration: {total['total_duration_seconds']:.2f}s",
            f"Total Tokens: {total['total_tokens']:,}",
            f"Total Transitions: {total['total_transitions']}",
            "\n--- State Visit Counts ---"
        ]
        
        for state, count in sorted(total['state_visits'].items()):
            report.append(f"  {state}: {count}")
        
        if bottlenecks['slowest_state']:
            report.extend([
                "\n--- Bottleneck Analysis ---",
                f"Slowest State: {bottlenecks['slowest_state']['state']}",
                f"  Avg Duration: {bottlenecks['slowest_state']['avg_duration_seconds']:.2f}s",
                f"  Total Duration: {bottlenecks['slowest_state']['total_duration_seconds']:.2f}s",
                f"  Visits: {bottlenecks['slowest_state']['visit_count']}",
                f"\nHighest Token State: {bottlenecks['highest_token_state']['state']}",
                f"  Avg Tokens: {bottlenecks['highest_token_state']['avg_tokens']:.0f}",
                f"  Total Tokens: {bottlenecks['highest_token_state']['total_tokens']:,}",
                f"  Visits: {bottlenecks['highest_token_state']['visit_count']}",
            ])
        
        if transition_metrics['most_common_transition']:
            report.extend([
                "\n--- Transition Patterns ---",
                f"Most Common: {transition_metrics['most_common_transition']} ({transition_metrics['most_common_count']}x)",
                f"Unique Transitions: {transition_metrics['unique_transitions']}"
            ])
        
        return "\n".join(report)
```

## Integration with Orchestrator

### Usage Pattern

```python
class AgentOrchestrator:
    def __init__(self, job_config: JobConfig):
        self.state_machine = OrchestrationStateMachine()
        self.state_machine.max_iterations = job_config.agent.max_iterations
        
        # Integrate with existing token budget system
        self.token_budget_manager = job_config.token_budget_manager
    
    def run(self, audio_path: str, xsq_path: str | None = None) -> OrchestratorResult:
        """Run pipeline with state machine and metrics tracking."""
        # Transition to planning
        self.state_machine.transition(OrchestrationState.PLANNING)
        
        while not self.state_machine.is_terminal():
            state = self.state_machine.current_state
            
            # Track time and tokens for this state
            start_time = time.time()
            tokens_before = self.llm_provider.get_token_usage().total_tokens
            
            if state == OrchestrationState.PLANNING:
                result = self._execute_planning()
                
                # Calculate metrics
                duration = time.time() - start_time
                tokens = self.llm_provider.get_token_usage().total_tokens - tokens_before
                
                if result.success:
                    self.state_machine.transition(
                        OrchestrationState.VALIDATING,
                        context={"plan": result},
                        duration_seconds=duration,
                        tokens_consumed=tokens
                    )
                else:
                    self.state_machine.transition(
                        OrchestrationState.FAILED,
                        reason="Plan generation failed",
                        duration_seconds=duration,
                        tokens_consumed=tokens
                    )
            
            elif state == OrchestrationState.VALIDATING:
                passed = self._execute_validation()
                duration = time.time() - start_time
                
                if passed:
                    self.state_machine.transition(
                        OrchestrationState.IMPLEMENTING,
                        duration_seconds=duration,
                        tokens_consumed=0  # Validation is non-LLM
                    )
                else:
                    self._add_validation_feedback()
                    self.state_machine.transition(
                        OrchestrationState.PLANNING,
                        reason="Validation failed, retrying with feedback",
                        duration_seconds=duration,
                        tokens_consumed=0
                    )
            
            elif state == OrchestrationState.IMPLEMENTING:
                result = self._execute_implementation()
                duration = time.time() - start_time
                tokens = self.llm_provider.get_token_usage().total_tokens - tokens_before
                
                if result.success:
                    self.state_machine.transition(
                        OrchestrationState.JUDGING,
                        duration_seconds=duration,
                        tokens_consumed=tokens
                    )
                else:
                    self.state_machine.transition(
                        OrchestrationState.FAILED,
                        reason="Implementation expansion failed",
                        duration_seconds=duration,
                        tokens_consumed=tokens
                    )
            
            elif state == OrchestrationState.JUDGING:
                evaluation = self._execute_judging()
                duration = time.time() - start_time
                tokens = self.llm_provider.get_token_usage().total_tokens - tokens_before
                
                if evaluation.pass_threshold:
                    self.state_machine.transition(
                        OrchestrationState.SUCCEEDED,
                        context={"evaluation": evaluation},
                        duration_seconds=duration,
                        tokens_consumed=tokens
                    )
                else:
                    failure_analysis = self._analyze_failure(evaluation)
                    if failure_analysis.fix_strategy == "refine_implementation":
                        self._add_implementation_feedback(evaluation, failure_analysis)
                        self.state_machine.transition(
                            OrchestrationState.IMPLEMENTING,
                            reason="Soft failure, refining implementation",
                            duration_seconds=duration,
                            tokens_consumed=tokens
                        )
                    else:
                        self._add_planning_feedback(evaluation, failure_analysis)
                        self.state_machine.transition(
                            OrchestrationState.PLANNING,
                            reason="Hard failure, replanning",
                            duration_seconds=duration,
                            tokens_consumed=tokens
                        )
            
            # Check existing budget system
            if self.token_budget_manager.is_exhausted():
                self.state_machine.transition(
                    OrchestrationState.BUDGET_EXHAUSTED,
                    reason="Token budget exhausted"
                )
        
        # Log metrics report
        logger.info("\n" + self.state_machine.format_metrics_report())
        
        # Build result based on final state
        return self._build_result()
```

## Checkpointing Integration

### State Machine Checkpointing with Metrics

```python
class CheckpointManager:
    def save_state_machine(self, state_machine: OrchestrationStateMachine) -> None:
        """Save state machine with metrics to checkpoint."""
        checkpoint_data = {
            "current_state": state_machine.current_state.value,
            "iteration_count": state_machine.iteration_count,
            "history": [
                {
                    "from_state": t.from_state.value,
                    "to_state": t.to_state.value,
                    "timestamp": t.timestamp,
                    "reason": t.reason,
                    "duration_seconds": t.duration_seconds,
                    "tokens_consumed": t.tokens_consumed
                }
                for t in state_machine.history
            ]
        }
        self.write_checkpoint(CheckpointType.STATE_MACHINE, checkpoint_data)
    
    def load_state_machine(self) -> OrchestrationStateMachine | None:
        """Load state machine with metrics from checkpoint."""
        checkpoint = self.read_checkpoint(CheckpointType.STATE_MACHINE)
        if not checkpoint:
            return None
        
        state_machine = OrchestrationStateMachine()
        state_machine.current_state = OrchestrationState(checkpoint["current_state"])
        state_machine.iteration_count = checkpoint["iteration_count"]
        
        # Restore history with metrics
        for t_data in checkpoint["history"]:
            transition = StateTransition(
                from_state=OrchestrationState(t_data["from_state"]),
                to_state=OrchestrationState(t_data["to_state"]),
                timestamp=t_data["timestamp"],
                context={},
                reason=t_data.get("reason"),
                duration_seconds=t_data.get("duration_seconds", 0.0),
                tokens_consumed=t_data.get("tokens_consumed", 0)
            )
            state_machine.history.append(transition)
        
        return state_machine
```

## Observability

### State Machine Observer Protocol

```python
class StateMachineObserver(Protocol):
    """Observer for state machine events."""
    
    def on_state_transition(
        self,
        transition: StateTransition
    ) -> None:
        """Called when state transitions."""
        ...
    
    def on_metrics_update(
        self,
        metrics: dict[str, Any]
    ) -> None:
        """Called when metrics are updated."""
        ...

# Usage
class MetricsLogger(StateMachineObserver):
    """Log metrics to external system."""
    
    def on_state_transition(self, transition: StateTransition) -> None:
        logger.info(
            f"Transition: {transition.from_state.value} → {transition.to_state.value}, "
            f"Duration: {transition.duration_seconds:.2f}s, "
            f"Tokens: {transition.tokens_consumed}"
        )
    
    def on_metrics_update(self, metrics: dict[str, Any]) -> None:
        # Send to monitoring system
        monitoring_client.send_metrics(metrics)

class Orchestrator:
    def __init__(self, ...):
        self.state_machine = OrchestrationStateMachine()
        self.observers: list[StateMachineObserver] = []
        
        # Add observers
        self.add_observer(MetricsLogger())
    
    def add_observer(self, observer: StateMachineObserver) -> None:
        """Add state machine observer."""
        self.observers.append(observer)
    
    def _notify_transition(self, transition: StateTransition) -> None:
        """Notify observers of transition."""
        for observer in self.observers:
            observer.on_state_transition(transition)
```

## Benefits

1. **Explicit Flow Control**: State transitions are explicit and validated
2. **Error Recovery**: Clear paths for error recovery
3. **Observability**: Comprehensive metrics for debugging and optimization
4. **Bottleneck Detection**: Identify slow states and high token consumers
5. **Checkpointing**: State and metrics can be saved/restored
6. **Testability**: State machine can be tested independently
7. **Budget Integration**: Works with existing token budget system
8. **Performance Analysis**: Duration and token tracking per state

## Testing

### Unit Tests

```python
def test_state_machine_transitions():
    sm = OrchestrationStateMachine()
    
    # Valid transition
    assert sm.can_transition_to(OrchestrationState.PLANNING)
    sm.transition(OrchestrationState.PLANNING)
    assert sm.current_state == OrchestrationState.PLANNING
    
    # Invalid transition
    assert not sm.can_transition_to(OrchestrationState.SUCCEEDED)
    with pytest.raises(InvalidTransitionError):
        sm.transition(OrchestrationState.SUCCEEDED)

def test_terminal_states():
    sm = OrchestrationStateMachine()
    sm.current_state = OrchestrationState.SUCCEEDED
    
    assert sm.is_terminal()
    assert not sm.can_transition_to(OrchestrationState.PLANNING)

def test_metrics_tracking():
    sm = OrchestrationStateMachine()
    
    # Transition with metrics
    sm.transition(
        OrchestrationState.PLANNING,
        duration_seconds=10.5,
        tokens_consumed=500
    )
    
    # Get metrics
    metrics = sm.get_state_metrics(OrchestrationState.INITIALIZED)
    assert metrics.total_duration_seconds == 10.5
    assert metrics.total_tokens == 500
    assert metrics.visit_count == 1

def test_bottleneck_analysis():
    sm = OrchestrationStateMachine()
    
    # Simulate multiple transitions
    sm.transition(OrchestrationState.PLANNING, duration_seconds=5.0, tokens_consumed=100)
    sm.transition(OrchestrationState.VALIDATING, duration_seconds=1.0, tokens_consumed=0)
    sm.transition(OrchestrationState.IMPLEMENTING, duration_seconds=15.0, tokens_consumed=800)
    
    bottlenecks = sm.get_bottleneck_analysis()
    assert bottlenecks['slowest_state']['state'] == 'implementing'
    assert bottlenecks['highest_token_state']['state'] == 'implementing'
```

## Migration Notes

- State machine is additive (doesn't break existing code)
- Metrics tracking is optional (defaults to 0.0 if not provided)
- Integrates with existing token budget system
- Can be feature-flagged during rollout
- Old iteration loop can coexist until migration complete