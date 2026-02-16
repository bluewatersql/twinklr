"""Pipeline orchestration framework for Twinklr.

Provides declarative pipeline definition with automatic dependency resolution,
parallel execution, and error handling.

Core concepts:
- PipelineStage: Unit of work (audio analysis, agent, rendering)
- PipelineDefinition: Declarative stage dependencies and execution config
- PipelineExecutor: Orchestrates execution with dep tracking
- PipelineContext: Shared state and dependencies across stages

Example:
    >>> from twinklr.core.pipeline import (
    ...     PipelineDefinition,
    ...     PipelineExecutor,
    ...     PipelineContext,
    ...     StageDefinition,
    ...     ExecutionPattern,
    ... )
    >>>
    >>> # Define pipeline
    >>> pipeline = PipelineDefinition(
    ...     name="audio_analysis",
    ...     stages=[
    ...         StageDefinition("analyze", AudioStage()),
    ...         StageDefinition("profile", ProfileStage(), inputs=["analyze"]),
    ...     ]
    ... )
    >>>
    >>> # Execute
    >>> ctx = PipelineContext(provider=provider, config=config)
    >>> executor = PipelineExecutor()
    >>> result = await executor.execute(pipeline, audio_path, ctx)
"""

from twinklr.core.pipeline.context import PipelineContext
from twinklr.core.pipeline.definition import (
    ExecutionPattern,
    PipelineDefinition,
    StageDefinition,
)
from twinklr.core.pipeline.executor import PipelineExecutor
from twinklr.core.pipeline.result import (
    PipelineResult,
    StageResult,
    cancelled_result,
    failure_result,
    skipped_result,
    success_result,
)
from twinklr.core.pipeline.stage import PipelineStage, resolve_typed_input

__all__ = [
    "ExecutionPattern",
    "PipelineContext",
    "PipelineDefinition",
    "PipelineExecutor",
    "PipelineResult",
    "PipelineStage",
    "StageDefinition",
    "StageResult",
    "cancelled_result",
    "failure_result",
    "resolve_typed_input",
    "skipped_result",
    "success_result",
]
