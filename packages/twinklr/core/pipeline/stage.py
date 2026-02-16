"""Pipeline stage protocol and base types.

Defines the contract for pipeline stages using Protocol pattern for extensibility.
Includes the :func:`resolve_typed_input` helper for standardised stage input handling.
"""

from __future__ import annotations

from typing import Any, Protocol, TypeVar

from twinklr.core.pipeline.context import PipelineContext
from twinklr.core.pipeline.result import StageResult

# Generic input/output types for stages
TInput = TypeVar("TInput")
TOutput = TypeVar("TOutput")
T = TypeVar("T")


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


def resolve_typed_input(
    input: Any,
    model_type: type[T],
    dict_key: str | None = None,
) -> tuple[T, dict[str, Any]]:
    """Extract a typed value from pipeline stage input.

    Handles the two standard input modes that pipeline stages receive:

    1. **Pipeline mode** — the executor passes the upstream stage's output
       directly (already the expected model type).
    2. **Multi-input / direct mode** — the executor (or test code) passes a
       ``dict`` mapping stage IDs to their outputs; the target model is
       extracted via *dict_key*.

    Args:
        input: Raw stage input (model instance or ``dict``).
        model_type: Expected model class (used for ``isinstance`` check).
        dict_key: Key to extract from *input* when it is a ``dict``.
            Required when dict inputs are expected.

    Returns:
        Tuple of ``(model, extras)``.

        *model* is the resolved instance of *model_type*.

        *extras* is an empty ``dict`` when *input* was already the model,
        or the remaining dict entries (excluding *dict_key*) when *input*
        was a ``dict``.

    Raises:
        TypeError: If *input* cannot be resolved to *model_type*.

    Examples:
        >>> from twinklr.core.pipeline.stage import resolve_typed_input
        >>> plan, extras = resolve_typed_input(group_plan_set, GroupPlanSet, "aggregate")
        >>> catalog = extras.get("catalog") or context.get_state("asset_catalog")
    """
    if isinstance(input, model_type):
        return input, {}

    if isinstance(input, dict) and dict_key is not None:
        value = input.get(dict_key)
        if value is not None:
            extras = {k: v for k, v in input.items() if k != dict_key}
            return value, extras
        raise TypeError(
            f"Dict input missing key '{dict_key}' "
            f"(expected {model_type.__name__})"
        )

    raise TypeError(
        f"Expected {model_type.__name__}"
        + (f" or dict with key '{dict_key}'" if dict_key else "")
        + f", got {type(input).__name__}"
    )
