"""Async checkpoint adapter for agent orchestration (Phase 8).

Replaces utils/checkpoint.py with adapters using core.caching.FSCache.

Functions:
    save_checkpoint_async: Save agent checkpoint
    load_checkpoint_async: Load agent checkpoint

Example:
    >>> from twinklr.core.caching import FSCache
    >>> from twinklr.core.io import RealFileSystem, absolute_path
    >>>
    >>> fs = RealFileSystem()
    >>> cache = FSCache(fs, absolute_path("artifacts/my_project/cache"))
    >>> await cache.initialize()
    >>>
    >>> await save_checkpoint_async(
    ...     project_name="my_project",
    ...     checkpoint_type="final",
    ...     data=choreography_plan,
    ...     cache=cache
    ... )
"""

import logging
from typing import TypeVar

from pydantic import BaseModel

from twinklr.core.caching import CacheKey, FSCache

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)


async def save_checkpoint_async(
    project_name: str,
    checkpoint_type: str,  # "raw", "eval", "final"
    data: BaseModel,
    cache: FSCache,
    *,
    iteration: int | None = None,
    run_id: str | None = None,
    compute_ms: float | None = None,
) -> None:
    """Save agent checkpoint using core.caching.

    Args:
        project_name: Project name
        checkpoint_type: Checkpoint type (raw, eval, final)
        data: Pydantic model to save
        cache: FSCache instance
        iteration: Optional iteration number (1-indexed)
        run_id: Optional run ID for tracking
        compute_ms: Optional computation duration in milliseconds

    Example:
        >>> await save_checkpoint_async(
        ...     project_name="my_project",
        ...     checkpoint_type="final",
        ...     data=plan_model,
        ...     cache=cache,
        ...     run_id="abc123"
        ... )
    """
    try:
        # Compute identifier
        parts = [project_name]
        if run_id:
            parts.append(run_id)
        if iteration is not None:
            parts.append(f"iter{iteration:02d}")
        identifier = "_".join(parts)

        # Create cache key
        key = CacheKey(
            step_id=f"agent.{checkpoint_type}",
            step_version="1",
            input_fingerprint=identifier,
        )

        # Store with atomic commit
        await cache.store(key, data, compute_ms=compute_ms)
        logger.debug(f"Saved checkpoint: {checkpoint_type} for {project_name}")
    except Exception as e:
        logger.warning(f"Failed to save checkpoint: {e}")
        # Non-fatal - continue without checkpointing


async def load_checkpoint_async(
    project_name: str,
    checkpoint_type: str,
    model_cls: type[T],
    cache: FSCache,
    *,
    iteration: int | None = None,
    run_id: str | None = None,
) -> T | None:
    """Load agent checkpoint using core.caching.

    Args:
        project_name: Project name
        checkpoint_type: Checkpoint type (raw, eval, final)
        model_cls: Pydantic model class for validation
        cache: FSCache instance
        iteration: Optional iteration number
        run_id: Optional run ID

    Returns:
        Cached model or None if not found

    Example:
        >>> plan = await load_checkpoint_async(
        ...     project_name="my_project",
        ...     checkpoint_type="final",
        ...     model_cls=ChoreographyPlan,
        ...     cache=cache
        ... )
    """
    try:
        # Compute identifier
        parts = [project_name]
        if run_id:
            parts.append(run_id)
        if iteration is not None:
            parts.append(f"iter{iteration:02d}")
        identifier = "_".join(parts)

        # Create cache key
        key = CacheKey(
            step_id=f"agent.{checkpoint_type}",
            step_version="1",
            input_fingerprint=identifier,
        )

        # Load with validation
        result = await cache.load(key, model_cls)
        if result:
            logger.debug(f"Loaded checkpoint: {checkpoint_type} for {project_name}")
        return result
    except Exception as e:
        logger.warning(f"Failed to load checkpoint: {e}")
        return None
