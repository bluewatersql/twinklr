"""Pipeline stage execution helpers with caching support.

Provides execute_step() helper that reduces stage boilerplate by handling:
- Deterministic caching (long-lived)
- Default state storage
- Default metrics tracking (iterations, tokens, scores, cache hits)
- Custom handlers extend defaults
"""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING, TypeVar

from pydantic import BaseModel

if TYPE_CHECKING:
    from twinklr.core.pipeline.context import PipelineContext
    from twinklr.core.pipeline.result import StageResult

from twinklr.core.caching import CacheKey
from twinklr.core.pipeline.result import failure_result, success_result

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)
OutputT = TypeVar("OutputT")


async def execute_step(
    stage_name: str,
    context: PipelineContext,
    compute: Callable[[], Awaitable[T]],
    result_extractor: Callable[[T], OutputT],
    result_type: type[T],
    cache_key_fn: Callable[[], Awaitable[str]] | None = None,
    cache_version: str = "1",
    state_handler: Callable[[T, PipelineContext], None] | None = None,
    metrics_handler: Callable[[T, PipelineContext], None] | None = None,
) -> StageResult[OutputT]:
    """Execute orchestrator with caching, state, and metrics handling.

    Reduces stage boilerplate by ~30% by handling common patterns:
    - Deterministic caching (if cache_key_fn provided)
    - Default state storage (full orchestration result)
    - Default metrics (iterations, tokens, score, cache hits)
    - Custom handlers EXTEND defaults (not override)

    Args:
        stage_name: Stage identifier (for logging, state keys, metrics)
        context: Pipeline context (cache, state, metrics)
        compute: Async function that runs orchestrator
        result_extractor: Extract final stage output from orchestrator result
        result_type: Type of orchestrator result (for cache deserialization)
        cache_key_fn: Optional cache key generator (enables caching)
        cache_version: Cache version string (bump to invalidate cache)
        state_handler: Optional handler for additional state (extends defaults)
        metrics_handler: Optional handler for additional metrics (extends defaults)

    Returns:
        StageResult with extracted output

    Default Behavior:
        State Storage:
            - f"{stage_name}_result": Full orchestration result

        Metrics Tracked:
            - f"{stage_name}_iterations": Iteration count (if result.context exists)
            - f"{stage_name}_tokens": Token usage (if result.context exists)
            - f"{stage_name}_score": Final score (if result.context.final_verdict exists)
            - f"{stage_name}_from_cache": True if cache hit, False if computed

    Example:
        >>> # Minimal usage
        >>> return await execute_step(
        ...     stage_name="macro_plan",
        ...     context=context,
        ...     compute=lambda: orchestrator.run(planning_context),
        ...     result_extractor=lambda r: r.plan.section_plans,
        ...     result_type=OrchestrationResult,
        ...     cache_key_fn=lambda: orchestrator.get_cache_key(planning_context),
        ... )
        >>>
        >>> # With custom metrics (extends defaults)
        >>> return await execute_step(
        ...     stage_name="macro_plan",
        ...     context=context,
        ...     compute=lambda: orchestrator.run(planning_context),
        ...     result_extractor=lambda r: r.plan.section_plans,
        ...     result_type=OrchestrationResult,
        ...     cache_key_fn=lambda: orchestrator.get_cache_key(planning_context),
        ...     metrics_handler=lambda r, ctx: ctx.add_metric("section_count", len(r.plan.section_plans)),
        ... )
    """
    from_cache = False
    result = None

    # Check cache if enabled
    if cache_key_fn and context.cache:
        try:
            cache_key_hash = await cache_key_fn()
            cache_key = CacheKey(
                step_id=stage_name,
                step_version=cache_version,
                input_fingerprint=cache_key_hash,
            )

            # Try load from cache
            cached_result = await context.cache.load(cache_key, result_type)
            if cached_result:
                logger.debug(f"✓ Cache hit: {stage_name}")
                result = cached_result
                from_cache = True
            else:
                logger.debug(f"Cache miss: {stage_name}")
        except Exception as e:
            logger.warning(f"Cache check failed for {stage_name}: {e}")

    # Execute orchestrator if not cached
    if not from_cache:
        logger.debug(f"Executing {stage_name}")
        result = await compute()

        # Null check
        if result is None:
            logger.error(f"{stage_name} returned None")
            return failure_result("Execution returned None", stage_name=stage_name)

        # Check for orchestration failure
        if hasattr(result, "success") and not getattr(result, "success", True):
            error_ctx = getattr(result, "context", None)
            if error_ctx and hasattr(error_ctx, "termination_reason"):
                error_msg = getattr(error_ctx, "termination_reason", "Execution failed")
            else:
                error_msg = "Execution failed"
            logger.error(f"{stage_name} failed: {error_msg}")
            return failure_result(str(error_msg), stage_name=stage_name)

        # Store in cache if enabled
        if cache_key_fn and context.cache:
            try:
                await context.cache.store(cache_key, result)
                logger.debug(f"Cached {stage_name}")
            except Exception as e:
                logger.warning(f"Cache store failed for {stage_name}: {e}")

    # Ensure result is not None (for type checker)
    if result is None:
        logger.error(f"{stage_name} result is None after execution")
        return failure_result("Result is None", stage_name=stage_name)

    # DEFAULT STATE: Store full result
    context.set_state(f"{stage_name}_result", result)

    # DEFAULT METRICS: Iterations, tokens, score
    if hasattr(result, "context"):
        result_context = getattr(result, "context", None)
        if result_context:
            # Iteration count: current_iteration is 0-based but incremented at start of each loop
            # So iteration 0 = 1 attempt, iteration 1 = 2 attempts, etc.
            # Report the actual number of attempts made
            if hasattr(result_context, "current_iteration"):
                iterations = result_context.current_iteration  # type: ignore[attr-defined]
                # Add 1 to convert from 0-based to human-readable count
                # BUT: controller.increment_iteration() is called at loop start,
                # so current_iteration already represents attempts made
                context.add_metric(f"{stage_name}_iterations", iterations)
            if hasattr(result_context, "total_tokens_used"):
                context.add_metric(f"{stage_name}_tokens", result_context.total_tokens_used)  # type: ignore[attr-defined]
            final_verdict = getattr(result_context, "final_verdict", None)
            if final_verdict:
                context.add_metric(f"{stage_name}_score", final_verdict.score)  # type: ignore[attr-defined]

    # CACHE HIT METRIC
    context.add_metric(f"{stage_name}_from_cache", from_cache)

    # CUSTOM STATE HANDLER (extends defaults)
    if state_handler:
        try:
            state_handler(result, context)
        except Exception as e:
            logger.warning(f"Custom state handler failed for {stage_name}: {e}")

    # CUSTOM METRICS HANDLER (extends defaults)
    if metrics_handler:
        try:
            metrics_handler(result, context)
        except Exception as e:
            logger.warning(f"Custom metrics handler failed for {stage_name}: {e}")

    # Extract final output for stage result
    try:
        output = result_extractor(result)
    except Exception as e:
        logger.error(f"Result extraction failed for {stage_name}: {e}")
        return failure_result(f"Result extraction failed: {e}", stage_name=stage_name)

    logger.debug(f"{stage_name} complete (cached={from_cache})")
    return success_result(output, stage_name=stage_name)
