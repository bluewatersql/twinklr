"""Orchestration state machine with metrics tracking."""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


class OrchestrationState(str, Enum):
    """Orchestration state machine states.

    Note: Implementation step has been removed. The planner now generates
    complete implementation directly (simplified pipeline).
    """

    INITIALIZED = "initialized"
    PLANNING = "planning"
    VALIDATING = "validating"
    JUDGING = "judging"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    BUDGET_EXHAUSTED = "budget_exhausted"


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
    min_duration_seconds: float = float("inf")
    max_duration_seconds: float = 0.0


class InvalidTransitionError(Exception):
    """Raised when invalid state transition is attempted."""

    pass


class OrchestrationStateMachine:
    """State machine for orchestration flow with observability.

    Features:
    - Explicit state management with validation
    - Transition history with metrics
    - Bottleneck detection
    - Checkpointing support
    """

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
            OrchestrationState.PLANNING,  # Retry on failure
            OrchestrationState.JUDGING,
            OrchestrationState.FAILED,
        ],
        OrchestrationState.JUDGING: [
            OrchestrationState.SUCCEEDED,
            OrchestrationState.PLANNING,  # Soft/hard failure
            OrchestrationState.FAILED,
            OrchestrationState.BUDGET_EXHAUSTED,
        ],
    }

    # Terminal states (no transitions out)
    TERMINAL_STATES = {
        OrchestrationState.SUCCEEDED,
        OrchestrationState.FAILED,
        OrchestrationState.BUDGET_EXHAUSTED,
    }

    def __init__(self, max_iterations: int = 3):
        """Initialize state machine.

        Args:
            max_iterations: Maximum planning iterations
        """
        self.current_state = OrchestrationState.INITIALIZED
        self.history: list[StateTransition] = []
        self.iteration_count = 0
        self.max_iterations = max_iterations

    def transition(
        self,
        to_state: OrchestrationState,
        context: dict[str, Any] | None = None,
        reason: str | None = None,
        duration_seconds: float = 0.0,
        tokens_consumed: int = 0,
    ) -> bool:
        """Transition to new state with metrics tracking.

        Args:
            to_state: Target state
            context: Optional context data for transition
            reason: Optional reason for transition
            duration_seconds: Time spent in previous state
            tokens_consumed: Tokens used in previous state

        Returns:
            True if transition succeeded, False if already terminal

        Raises:
            InvalidTransitionError: If transition is invalid
        """
        # Check if already in terminal state FIRST
        if self.current_state in self.TERMINAL_STATES:
            logger.warning(
                f"Attempted transition from terminal state {self.current_state.value} → {to_state.value}"
            )
            return False

        # Check if transition is valid
        if not self.can_transition_to(to_state):
            raise InvalidTransitionError(
                f"Invalid transition: {self.current_state.value} → {to_state.value}. "
                f"Valid transitions: {[s.value for s in self.VALID_TRANSITIONS.get(self.current_state, [])]}"
            )

        # Record transition with metrics
        transition = StateTransition(
            from_state=self.current_state,
            to_state=to_state,
            timestamp=time.time(),
            context=context or {},
            reason=reason,
            duration_seconds=duration_seconds,
            tokens_consumed=tokens_consumed,
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
        state_transitions = [t for t in self.history if t.from_state == state]

        if not state_transitions:
            return StateMetrics(
                state=state,
                visit_count=0,
                total_duration_seconds=0.0,
                total_tokens=0,
                avg_duration_seconds=0.0,
                avg_tokens=0.0,
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
            min_duration_seconds=min(durations) if durations else 0.0,
            max_duration_seconds=max(durations) if durations else 0.0,
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
        state_visits: dict[str, int] = {}
        for transition in self.history:
            state_key: str = transition.from_state.value
            state_visits[state_key] = state_visits.get(state_key, 0) + 1

        return {
            "total_duration_seconds": total_duration,
            "total_tokens": total_tokens,
            "total_transitions": len(self.history),
            "iteration_count": self.iteration_count,
            "state_visits": state_visits,
            "current_state": self.current_state.value,
        }

    def get_transition_metrics(self) -> dict[str, Any]:
        """Get metrics about transition patterns.

        Returns:
            Dict with transition counts and patterns
        """
        transition_counts: dict[str, int] = {}

        for t in self.history:
            key: str = f"{t.from_state.value} → {t.to_state.value}"
            transition_counts[key] = transition_counts.get(key, 0) + 1

        # Find most common transition
        most_common = (
            max(transition_counts.items(), key=lambda x: x[1]) if transition_counts else None
        )

        return {
            "transition_counts": transition_counts,
            "most_common_transition": most_common[0] if most_common else None,
            "most_common_count": most_common[1] if most_common else 0,
            "unique_transitions": len(transition_counts),
        }

    def get_bottleneck_analysis(self) -> dict[str, Any]:
        """Identify bottlenecks in the pipeline.

        Returns:
            Dict with slowest states and highest token consumers
        """
        all_metrics = self.get_all_state_metrics()

        # Find states with data
        states_with_data = [m for m in all_metrics.values() if m.visit_count > 0]

        if not states_with_data:
            return {
                "slowest_state": None,
                "highest_token_state": None,
                "avg_duration_per_iteration": 0.0,
                "avg_tokens_per_iteration": 0.0,
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
                "visit_count": slowest.visit_count,
            },
            "highest_token_state": {
                "state": highest_tokens.state.value,
                "avg_tokens": highest_tokens.avg_tokens,
                "total_tokens": highest_tokens.total_tokens,
                "visit_count": highest_tokens.visit_count,
            },
            "avg_duration_per_iteration": (
                total_metrics["total_duration_seconds"] / self.iteration_count
                if self.iteration_count > 0
                else 0.0
            ),
            "avg_tokens_per_iteration": (
                total_metrics["total_tokens"] / self.iteration_count
                if self.iteration_count > 0
                else 0.0
            ),
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
            "\n--- State Visit Counts ---",
        ]

        for state, count in sorted(total["state_visits"].items()):
            report.append(f"  {state}: {count}")

        if bottlenecks["slowest_state"]:
            report.extend(
                [
                    "\n--- Bottleneck Analysis ---",
                    f"Slowest State: {bottlenecks['slowest_state']['state']}",
                    f"  Avg Duration: {bottlenecks['slowest_state']['avg_duration_seconds']:.2f}s",
                    f"  Total Duration: {bottlenecks['slowest_state']['total_duration_seconds']:.2f}s",
                    f"  Visits: {bottlenecks['slowest_state']['visit_count']}",
                    f"\nHighest Token State: {bottlenecks['highest_token_state']['state']}",
                    f"  Avg Tokens: {bottlenecks['highest_token_state']['avg_tokens']:.0f}",
                    f"  Total Tokens: {bottlenecks['highest_token_state']['total_tokens']:,}",
                    f"  Visits: {bottlenecks['highest_token_state']['visit_count']}",
                ]
            )

        if transition_metrics["most_common_transition"]:
            report.extend(
                [
                    "\n--- Transition Patterns ---",
                    f"Most Common: {transition_metrics['most_common_transition']} ({transition_metrics['most_common_count']}x)",
                    f"Unique Transitions: {transition_metrics['unique_transitions']}",
                ]
            )

        return "\n".join(report)
