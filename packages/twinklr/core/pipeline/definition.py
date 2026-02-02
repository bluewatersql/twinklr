"""Pipeline definition models.

Declarative pipeline structure with stage dependencies and execution configuration.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from twinklr.core.pipeline.context import PipelineContext


class ExecutionPattern(str, Enum):
    """Execution pattern for stage.

    Defines how stage should be executed relative to inputs.

    Values:
        SEQUENTIAL: Execute once with single input (default)
        PARALLEL: Execute alongside other stages with same deps
        FAN_OUT: Execute N times in parallel (one per input item)
        CONDITIONAL: Execute only if condition is met
    """

    SEQUENTIAL = "sequential"
    PARALLEL = "parallel"
    FAN_OUT = "fan_out"
    CONDITIONAL = "conditional"


@dataclass(frozen=True)
class RetryConfig:
    """Retry configuration for stage execution.

    Attributes:
        max_attempts: Maximum number of attempts (default: 1, no retry)
        initial_delay_ms: Initial delay before first retry (milliseconds)
        backoff_multiplier: Exponential backoff multiplier
        max_delay_ms: Maximum delay between retries (milliseconds)
        retryable_errors: Optional list of error substrings to retry on
    """

    max_attempts: int = 1
    initial_delay_ms: float = 1000.0
    backoff_multiplier: float = 2.0
    max_delay_ms: float = 60000.0
    retryable_errors: list[str] | None = None


@dataclass
class StageDefinition:
    """Definition of a single pipeline stage.

    Declarative configuration for stage execution including dependencies,
    execution pattern, retry logic, and conditional execution.

    Attributes:
        id: Unique stage identifier
        stage: Stage implementation (must implement PipelineStage protocol)
        pattern: Execution pattern (default: SEQUENTIAL)
        inputs: List of stage IDs this stage depends on
        condition: Optional condition function (for CONDITIONAL pattern)
        retry_config: Optional retry configuration
        timeout_ms: Optional timeout in milliseconds
        critical: Whether failure should fail entire pipeline (default: True)
        max_concurrent_fan_out: Max concurrent executions for FAN_OUT (default: 4, None=unlimited)
        description: Optional human-readable description

    Example:
        >>> # Simple sequential stage
        >>> audio_stage = StageDefinition(
        ...     id="audio",
        ...     stage=AudioAnalysisStage(),
        ...     description="Analyze audio file"
        ... )
        >>>
        >>> # Parallel stages
        >>> profile_stage = StageDefinition(
        ...     id="profile",
        ...     stage=AudioProfileStage(),
        ...     pattern=ExecutionPattern.PARALLEL,
        ...     inputs=["audio"],
        ... )
        >>>
        >>> # Conditional stage
        >>> lyrics_stage = StageDefinition(
        ...     id="lyrics",
        ...     stage=LyricsStage(),
        ...     pattern=ExecutionPattern.CONDITIONAL,
        ...     inputs=["audio"],
        ...     condition=lambda ctx: ctx.get_state("has_lyrics", False),
        ... )
        >>>
        >>> # Fan-out stage with concurrency limit
        >>> group_stage = StageDefinition(
        ...     id="groups",
        ...     stage=GroupPlannerStage(),
        ...     pattern=ExecutionPattern.FAN_OUT,
        ...     inputs=["macro", "fixtures"],
        ...     max_concurrent_fan_out=4,  # Max 4 sections in parallel
        ...     retry_config=RetryConfig(max_attempts=2),
        ... )
    """

    id: str
    stage: Any  # PipelineStage[Any, Any] - use Any to avoid Pydantic Protocol issues
    pattern: ExecutionPattern = ExecutionPattern.SEQUENTIAL
    inputs: list[str] = field(default_factory=list)
    condition: Callable[[PipelineContext], bool] | None = None
    retry_config: RetryConfig | None = None
    timeout_ms: float | None = None
    critical: bool = True
    max_concurrent_fan_out: int | None = 4
    description: str | None = None

    def should_execute(self, context: PipelineContext) -> bool:
        """Check if stage should execute based on condition.

        Args:
            context: Pipeline context

        Returns:
            True if stage should execute
        """
        if self.condition is None:
            return True
        return self.condition(context)

    def validate_inputs(self, available_stages: set[str]) -> list[str]:
        """Validate that all input stages exist.

        Args:
            available_stages: Set of all stage IDs in pipeline

        Returns:
            List of error messages (empty if valid)
        """
        errors = []
        for input_id in self.inputs:
            if input_id not in available_stages:
                errors.append(f"Stage '{self.id}' depends on unknown stage '{input_id}'")
        return errors


class PipelineDefinition(BaseModel):
    """Declarative pipeline definition.

    Defines complete pipeline structure with stages, dependencies, and execution config.

    Attributes:
        name: Pipeline name (for logging/tracking)
        stages: List of stage definitions (order not significant, deps define order)
        description: Optional human-readable description
        fail_fast: Whether to stop on first failure (default: True)

    Example:
        >>> pipeline = PipelineDefinition(
        ...     name="twinklr_sequencer",
        ...     description="Complete sequencer pipeline",
        ...     stages=[
        ...         StageDefinition("audio", AudioAnalysisStage()),
        ...         StageDefinition("profile", AudioProfileStage(), inputs=["audio"]),
        ...         StageDefinition("lyrics", LyricsStage(), inputs=["audio"]),
        ...         StageDefinition("macro", MacroPlannerStage(), inputs=["profile", "lyrics"]),
        ...         StageDefinition("groups", GroupPlannerStage(), inputs=["macro"],
        ...                        pattern=ExecutionPattern.FAN_OUT),
        ...     ],
        ... )
    """

    name: str = Field(description="Pipeline name")
    stages: list[StageDefinition] = Field(description="List of stage definitions")
    description: str | None = Field(default=None, description="Optional description")
    fail_fast: bool = Field(default=True, description="Stop on first failure")

    model_config = ConfigDict(frozen=True, extra="forbid", arbitrary_types_allowed=True)

    def validate_pipeline(self) -> list[str]:
        """Validate pipeline definition.

        Checks:
        - All stage IDs are unique
        - All input dependencies reference valid stages
        - No circular dependencies
        - At least one stage has no dependencies (entry point)

        Returns:
            List of error messages (empty if valid)

        Example:
            >>> errors = pipeline.validate()
            >>> if errors:
            ...     for error in errors:
            ...         print(f"Error: {error}")
        """
        errors = []

        # Check unique IDs
        stage_ids = [s.id for s in self.stages]
        if len(stage_ids) != len(set(stage_ids)):
            duplicates = [sid for sid in stage_ids if stage_ids.count(sid) > 1]
            errors.append(f"Duplicate stage IDs: {set(duplicates)}")

        available_stages = set(stage_ids)

        # Check input dependencies exist
        for stage_def in self.stages:
            errors.extend(stage_def.validate_inputs(available_stages))

        # Check for circular dependencies
        try:
            self._detect_cycles()
        except ValueError as e:
            errors.append(str(e))

        # Check for at least one entry point (stage with no deps)
        entry_points = [s.id for s in self.stages if not s.inputs]
        if not entry_points:
            errors.append("Pipeline has no entry points (all stages have dependencies)")

        return errors

    def _detect_cycles(self) -> None:
        """Detect circular dependencies using DFS.

        Raises:
            ValueError: If circular dependency detected
        """
        # Build adjacency list
        graph: dict[str, list[str]] = {s.id: [] for s in self.stages}
        for stage_def in self.stages:
            for input_id in stage_def.inputs:
                if input_id in graph:  # Might not exist if validation failed
                    graph[input_id].append(stage_def.id)

        # DFS cycle detection
        WHITE, GRAY, BLACK = 0, 1, 2
        color: dict[str, int] = {s.id: WHITE for s in self.stages}

        def dfs(node: str, path: list[str]) -> None:
            if color[node] == GRAY:
                cycle = " -> ".join(path + [node])
                raise ValueError(f"Circular dependency detected: {cycle}")

            if color[node] == BLACK:
                return

            color[node] = GRAY
            for neighbor in graph[node]:
                dfs(neighbor, path + [node])
            color[node] = BLACK

        for stage_id in graph:
            if color[stage_id] == WHITE:
                dfs(stage_id, [])

    def get_stage(self, stage_id: str) -> StageDefinition | None:
        """Get stage definition by ID.

        Args:
            stage_id: Stage ID

        Returns:
            StageDefinition or None if not found
        """
        for stage_def in self.stages:
            if stage_def.id == stage_id:
                return stage_def
        return None

    def get_entry_points(self) -> list[StageDefinition]:
        """Get stages with no dependencies (entry points).

        Returns:
            List of stage definitions with no inputs
        """
        return [s for s in self.stages if not s.inputs]
