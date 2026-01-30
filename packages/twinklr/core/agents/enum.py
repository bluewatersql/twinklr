from enum import Enum


class ValidationSeverity(str, Enum):
    """Validation issue severity."""

    ERROR = "error"  # Blocks progress
    WARNING = "warning"  # Noted but not blocking
    INFO = "info"  # Informational only


class OrchestratorStatus(Enum):
    """Orchestrator execution status."""

    SUCCESS = "success"  # Passed evaluation
    INCOMPLETE = "incomplete"  # Max iterations/budget without passing
    FAILED = "failed"  # Error occurred


class RefineStrategy(Enum):
    """Refinement strategy."""

    REPLAN = "replan"
    REFINE = "refine"
    FULL_REPLAN = "full_replan"


class Stage(str, Enum):
    """Agent stages for context shaping."""

    PLAN = "plan"
    VALIDATE = "validate"
    IMPLEMENTATION = "implementation"
    JUDGE = "judge"
    REFINEMENT = "refinement"
