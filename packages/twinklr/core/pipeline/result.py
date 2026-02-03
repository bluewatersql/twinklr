"""Result types for pipeline execution.

Provides immutable result types with success/failure semantics.
"""

from __future__ import annotations

from typing import Any, Generic, TypeVar

from pydantic import BaseModel, ConfigDict, Field

TOutput = TypeVar("TOutput")


class StageResult(BaseModel, Generic[TOutput]):
    """Result from a single stage execution.

    Immutable result type with success/failure semantics.
    Never raises exceptions - errors are captured in result.

    Attributes:
        success: Whether stage executed successfully
        output: Stage output (if success=True)
        error: Error message (if success=False)
        stage_name: Name of stage that produced result
        metadata: Optional metadata (timing, tokens, etc.)

    Example:
        >>> # Success case
        >>> from twinklr.core.pipeline.result import success_result
        >>> result = success_result(audio_bundle, stage_name="audio")
        >>> if result.success:
        ...     print(f"Output: {result.output}")
        >>>
        >>> # Failure case
        >>> from twinklr.core.pipeline.result import failure_result
        >>> result = failure_result("File not found", stage_name="audio")
        >>> if not result.success:
        ...     print(f"Error: {result.error}")
    """

    success: bool = Field(description="Whether stage executed successfully")
    stage_name: str = Field(description="Name of stage that produced result")
    output: TOutput | None = Field(default=None, description="Stage output (if success)")
    error: str | None = Field(default=None, description="Error message (if failure)")
    metadata: dict[str, Any] = Field(
        default_factory=dict, description="Optional metadata (timing, tokens, etc.)"
    )

    model_config = ConfigDict(frozen=True, extra="forbid", arbitrary_types_allowed=True)


# Helper functions to create results (avoids Pydantic classmethod issues)


def success_result(
    output: TOutput,
    stage_name: str = "unknown",
    metadata: dict[str, Any] | None = None,
) -> StageResult[TOutput]:
    """Create success result.

    Args:
        output: Stage output
        stage_name: Name of stage
        metadata: Optional metadata

    Returns:
        StageResult with success=True

    Example:
        >>> result = success_result(audio_bundle, stage_name="audio")
    """
    return StageResult(
        success=True,
        output=output,
        stage_name=stage_name,
        metadata=metadata or {},
    )


def failure_result(
    error: str,
    stage_name: str = "unknown",
    metadata: dict[str, Any] | None = None,
) -> StageResult[Any]:
    """Create failure result.

    Args:
        error: Error message
        stage_name: Name of stage
        metadata: Optional metadata

    Returns:
        StageResult with success=False

    Example:
        >>> result = failure_result("File not found", stage_name="audio")
    """
    return StageResult(
        success=False,
        error=error,
        stage_name=stage_name,
        metadata=metadata or {},
    )


def cancelled_result(
    reason: str = "Cancelled by user",
    stage_name: str = "unknown",
) -> StageResult[Any]:
    """Create cancelled result.

    Args:
        reason: Cancellation reason
        stage_name: Name of stage

    Returns:
        StageResult with success=False and cancellation error
    """
    return failure_result(f"[CANCELLED] {reason}", stage_name=stage_name)


def skipped_result(
    stage_name: str = "unknown",
    reason: str = "Condition not met",
) -> StageResult[Any]:
    """Create skipped result for conditional stages.

    Used when a conditional stage's condition evaluates to False.
    Treated as success (does not fail pipeline) but with no output.

    Args:
        stage_name: Name of stage
        reason: Reason for skipping

    Returns:
        StageResult with success=True but no output, with skip metadata
    """
    return StageResult(
        success=True,
        output=None,
        stage_name=stage_name,
        metadata={"skipped": True, "skip_reason": reason},
    )


class PipelineResult(BaseModel):
    """Result from complete pipeline execution.

    Contains all stage outputs and metadata from pipeline run.

    Attributes:
        success: Whether pipeline completed successfully
        outputs: Map of stage_id -> stage output
        stage_results: Map of stage_id -> StageResult
        failed_stages: List of stage IDs that failed
        total_duration_ms: Total pipeline duration
        metadata: Pipeline-level metadata

    Example:
        >>> result = await executor.execute(pipeline, input, context)
        >>> if result.success:
        ...     audio_bundle = result.outputs["audio"]
        ...     macro_plan = result.outputs["macro"]
        >>> else:
        ...     print(f"Failed stages: {result.failed_stages}")
    """

    success: bool = Field(description="Whether pipeline completed successfully")
    outputs: dict[str, Any] = Field(default_factory=dict, description="Map of stage_id -> output")
    stage_results: dict[str, StageResult[Any]] = Field(
        default_factory=dict, description="Map of stage_id -> StageResult"
    )
    failed_stages: list[str] = Field(
        default_factory=list, description="List of stage IDs that failed"
    )
    total_duration_ms: float = Field(default=0.0, description="Total pipeline duration (ms)")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Pipeline-level metadata")

    model_config = ConfigDict(frozen=True, extra="forbid")

    def get_output(self, stage_id: str) -> Any:
        """Get output from specific stage.

        Args:
            stage_id: Stage ID

        Returns:
            Stage output

        Raises:
            KeyError: If stage ID not found or stage failed
        """
        if stage_id not in self.outputs:
            raise KeyError(f"Stage '{stage_id}' not found in outputs")
        return self.outputs[stage_id]

    def get_result(self, stage_id: str) -> StageResult[Any]:
        """Get full result from specific stage.

        Args:
            stage_id: Stage ID

        Returns:
            StageResult for stage

        Raises:
            KeyError: If stage ID not found
        """
        if stage_id not in self.stage_results:
            raise KeyError(f"Stage '{stage_id}' not found in results")
        return self.stage_results[stage_id]
