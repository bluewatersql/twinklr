"""Pipeline stage protocol and base types.

Defines the contract for pipeline stages using Protocol pattern for extensibility.
"""

from __future__ import annotations

from typing import Any, Protocol, TypeVar

from twinklr.core.pipeline.context import PipelineContext
from twinklr.core.pipeline.result import StageResult

# Generic input/output types for stages
TInput = TypeVar("TInput")
TOutput = TypeVar("TOutput")


class PipelineStage(Protocol):
    """Protocol for pipeline stages.

    Defines the interface all pipeline stages must implement.
    Uses Protocol pattern for structural subtyping (no inheritance required).

    Note: Uses invariant type variables to avoid mypy protocol variance issues.

    Example:
        >>> class AudioAnalysisStage:
        ...     '''Analyzes audio file.'''
        ...
        ...     @property
        ...     def name(self) -> str:
        ...         return "audio_analysis"
        ...
        ...     async def execute(
        ...         self,
        ...         input: str,  # audio file path
        ...         context: PipelineContext,
        ...     ) -> StageResult[AudioBundle]:
        ...         analyzer = AudioAnalyzer(context.config)
        ...         bundle = await analyzer.analyze(input)
        ...         return StageResult.success(bundle)
    """

    @property
    def name(self) -> str:
        """Stage name for logging and tracking.

        Returns:
            Human-readable stage name (e.g., "audio_analysis")
        """
        ...

    async def execute(
        self,
        input: Any,  # Use Any to avoid variance issues with Protocol
        context: PipelineContext,
    ) -> StageResult[Any]:
        """Execute stage with input and shared context.

        Args:
            input: Stage input (type varies by stage)
            context: Shared pipeline context with dependencies

        Returns:
            StageResult containing output or error

        Raises:
            Should not raise - wrap errors in StageResult.failure()
        """
        ...
