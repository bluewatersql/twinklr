"""Pipeline executor with automatic dependency resolution.

Orchestrates pipeline execution with parallel execution, error handling, and metrics.
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any

from twinklr.core.pipeline.context import PipelineContext
from twinklr.core.pipeline.definition import (
    ExecutionPattern,
    PipelineDefinition,
    RetryConfig,
    StageDefinition,
)
from twinklr.core.pipeline.result import PipelineResult, StageResult, failure_result, success_result

logger = logging.getLogger(__name__)


class PipelineExecutor:
    """Executes pipelines with automatic dependency resolution.

    Handles:
    - Topological sorting for execution order
    - Automatic parallelism detection
    - Fan-out/fan-in pattern
    - Retry logic
    - Timeout handling
    - Cancellation support
    - Error propagation

    Example:
        >>> executor = PipelineExecutor()
        >>> result = await executor.execute(
        ...     pipeline=pipeline_def,
        ...     initial_input=audio_path,
        ...     context=context,
        ... )
        >>> if result.success:
        ...     print(f"Pipeline complete: {len(result.outputs)} stages")
    """

    def __init__(self) -> None:
        """Initialize pipeline executor."""
        pass

    async def execute(
        self,
        pipeline: PipelineDefinition,
        initial_input: Any,
        context: PipelineContext,
    ) -> PipelineResult:
        """Execute pipeline with automatic dependency resolution.

        Args:
            pipeline: Pipeline definition
            initial_input: Input for first stage(s)
            context: Shared pipeline context

        Returns:
            PipelineResult with all stage outputs and metadata

        Example:
            >>> result = await executor.execute(pipeline, audio_path, context)
        """
        start_time = time.perf_counter()

        # Validate pipeline
        errors = pipeline.validate_pipeline()
        if errors:
            logger.error(f"Pipeline validation failed: {errors}")
            return PipelineResult(
                success=False,
                failed_stages=["validation"],
                metadata={"validation_errors": errors},
            )

        logger.debug(f"Executing pipeline: {pipeline.name}")
        logger.debug(f"  Stages: {len(pipeline.stages)}")
        logger.debug(f"  Fail fast: {pipeline.fail_fast}")

        # Build execution plan (waves of stages that can run in parallel)
        execution_plan = self._build_execution_plan(pipeline, context)

        logger.debug(f"  Execution plan: {len(execution_plan)} waves")
        for i, wave in enumerate(execution_plan):
            logger.debug(f"    Wave {i}: {[s.id for s in wave]}")

        # Execute stages wave by wave
        outputs: dict[str, Any] = {}
        stage_results: dict[str, StageResult[Any]] = {}
        failed_stages: list[str] = []

        # First wave gets initial_input, others get from outputs
        for wave_idx, wave in enumerate(execution_plan):
            # Check for cancellation
            if context.is_cancelled():
                logger.warning("Pipeline cancelled by user")
                remaining = [s.id for wave in execution_plan[wave_idx:] for s in wave]
                return PipelineResult(
                    success=False,
                    outputs=outputs,
                    stage_results=stage_results,
                    failed_stages=failed_stages + remaining,
                    total_duration_ms=(time.perf_counter() - start_time) * 1000,
                    metadata={"cancellation": "User cancelled", "completed_waves": wave_idx},
                )

            logger.debug(
                f"Executing wave {wave_idx + 1}/{len(execution_plan)}: {[s.id for s in wave]}"
            )

            # Execute wave (stages in parallel)
            wave_results = await self._execute_wave(
                wave=wave,
                outputs=outputs,
                initial_input=initial_input,
                context=context,
            )

            # Update results
            for stage_id, result in wave_results.items():
                stage_results[stage_id] = result

                if result.success:
                    outputs[stage_id] = result.output
                    logger.debug(f"  ✓ {stage_id} completed")
                else:
                    failed_stages.append(stage_id)
                    logger.error(f"  ✗ {stage_id} failed: {result.error}")

                    # Check if critical failure
                    stage_def = pipeline.get_stage(stage_id)
                    if stage_def and stage_def.critical and pipeline.fail_fast:
                        logger.error(f"Critical stage '{stage_id}' failed, stopping pipeline")
                        end_time = time.perf_counter()
                        return PipelineResult(
                            success=False,
                            outputs=outputs,
                            stage_results=stage_results,
                            failed_stages=failed_stages,
                            total_duration_ms=(end_time - start_time) * 1000,
                            metadata={"fail_fast": True, "failed_stage": stage_id},
                        )

        # Pipeline complete
        end_time = time.perf_counter()
        duration_ms = (end_time - start_time) * 1000

        success = len(failed_stages) == 0
        logger.debug(
            f"Pipeline {'completed' if success else 'finished with errors'} in {duration_ms:.0f}ms"
        )

        if failed_stages:
            logger.warning(f"  Failed stages: {failed_stages}")

        return PipelineResult(
            success=success,
            outputs=outputs,
            stage_results=stage_results,
            failed_stages=failed_stages,
            total_duration_ms=duration_ms,
            metadata=context.metrics,
        )

    def _build_execution_plan(
        self,
        pipeline: PipelineDefinition,
        context: PipelineContext,
    ) -> list[list[StageDefinition]]:
        """Build execution plan with automatic parallelism detection.

        Groups stages into "waves" where each wave contains stages that:
        1. Have all dependencies satisfied by previous waves
        2. Can execute in parallel with each other

        Args:
            pipeline: Pipeline definition
            context: Pipeline context (for condition evaluation)

        Returns:
            List of waves (each wave is list of stages to run in parallel)
        """
        # NOTE: Conditions are now evaluated at execution time, not planning time.
        # This allows conditional stages to depend on state set by earlier stages.
        # We include all stages in planning and check conditions in _execute_stage().
        active_stages = list(pipeline.stages)

        # Topological sort into waves
        waves: list[list[StageDefinition]] = []
        completed: set[str] = set()
        remaining = active_stages.copy()

        while remaining:
            # Find stages whose dependencies are all completed
            ready = [
                s
                for s in remaining
                if all(
                    dep in completed or dep not in {st.id for st in active_stages}
                    for dep in s.inputs
                )
            ]

            if not ready:
                # Should not happen if validation passed
                logger.error("No ready stages but remaining stages exist - possible cycle")
                break

            waves.append(ready)
            completed.update(s.id for s in ready)
            remaining = [s for s in remaining if s not in ready]

        return waves

    async def _execute_wave(
        self,
        wave: list[StageDefinition],
        outputs: dict[str, Any],
        initial_input: Any,
        context: PipelineContext,
    ) -> dict[str, StageResult[Any]]:
        """Execute a wave of stages in parallel.

        Args:
            wave: List of stages to execute
            outputs: Outputs from previous stages
            initial_input: Initial pipeline input
            context: Pipeline context

        Returns:
            Map of stage_id -> StageResult
        """
        # Execute all stages in wave concurrently
        tasks = [
            self._execute_stage(stage_def, outputs, initial_input, context) for stage_def in wave
        ]

        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Build results map
        wave_results: dict[str, StageResult[Any]] = {}

        for stage_def, result_or_exc in zip(wave, results, strict=True):
            if isinstance(result_or_exc, Exception):
                # Unexpected exception (should not happen, stages should catch)
                logger.exception(
                    f"Unexpected exception in stage {stage_def.id}", exc_info=result_or_exc
                )
                wave_results[stage_def.id] = failure_result(
                    error=f"Unexpected error: {result_or_exc}",
                    stage_name=stage_def.stage.name,
                )
            elif isinstance(result_or_exc, StageResult):
                wave_results[stage_def.id] = result_or_exc
            else:
                wave_results[stage_def.id] = failure_result(
                    error="Invalid result type",
                    stage_name=stage_def.stage.name,
                )

        return wave_results

    async def _execute_stage(
        self,
        stage_def: StageDefinition,
        outputs: dict[str, Any],
        initial_input: Any,
        context: PipelineContext,
    ) -> StageResult[Any]:
        """Execute a single stage with retry and timeout.

        Args:
            stage_def: Stage definition
            outputs: Outputs from previous stages
            initial_input: Initial pipeline input
            context: Pipeline context

        Returns:
            StageResult from stage execution
        """
        from twinklr.core.pipeline.result import skipped_result

        stage_name = stage_def.stage.name

        # Evaluate condition at execution time (after dependencies have run)
        if not stage_def.should_execute(context):
            logger.debug(f"Skipping conditional stage '{stage_def.id}' (condition not met)")
            return skipped_result(stage_name=stage_name, reason="Condition not met")

        # Determine stage input
        if not stage_def.inputs:
            # Entry point - use initial input
            stage_input = initial_input
        elif len(stage_def.inputs) == 1:
            # Single input - use that output directly
            stage_input = outputs.get(stage_def.inputs[0])
        else:
            # Multiple inputs - package as dict
            stage_input = {input_id: outputs.get(input_id) for input_id in stage_def.inputs}

        # Handle fan-out pattern
        if stage_def.pattern == ExecutionPattern.FAN_OUT:
            # stage_input should be list/iterable
            if not isinstance(stage_input, (list, tuple)):
                logger.error(
                    f"FAN_OUT stage '{stage_def.id}' expected list input, got {type(stage_input)}"
                )
                return failure_result(
                    error=f"FAN_OUT requires list input, got {type(stage_input)}",
                    stage_name=stage_name,
                )

            # Convert tuple to list for type safety
            input_list = list(stage_input) if isinstance(stage_input, tuple) else stage_input
            return await self._execute_fan_out(stage_def, input_list, context)

        # Execute with retry and timeout
        retry_config = stage_def.retry_config
        max_attempts = retry_config.max_attempts if retry_config else 1

        last_error = None
        for attempt in range(max_attempts):
            if attempt > 0:
                delay_ms = self._calculate_backoff_delay(attempt, retry_config)
                logger.debug(
                    f"Retrying {stage_name} (attempt {attempt + 1}/{max_attempts}) after {delay_ms}ms"
                )
                await asyncio.sleep(delay_ms / 1000.0)

            try:
                # Execute with optional timeout
                if stage_def.timeout_ms:
                    result = await asyncio.wait_for(
                        stage_def.stage.execute(stage_input, context),
                        timeout=stage_def.timeout_ms / 1000.0,
                    )
                else:
                    result = await stage_def.stage.execute(stage_input, context)

                # Ensure result is StageResult
                if not isinstance(result, StageResult):
                    last_error = "Stage returned invalid result type"
                    continue

                # Success - return result
                if result.success:
                    return result

                # Stage returned failure - check if retryable
                last_error = result.error
                if not self._is_retryable_error(result.error, retry_config):
                    logger.warning(f"{stage_name} failed with non-retryable error: {result.error}")
                    return result

            except asyncio.TimeoutError:
                last_error = f"Stage timeout after {stage_def.timeout_ms}ms"
                logger.warning(f"{stage_name} timed out (attempt {attempt + 1}/{max_attempts})")
            except Exception as e:
                last_error = str(e)
                logger.exception(f"{stage_name} raised exception", exc_info=e)

        # All attempts exhausted
        return failure_result(
            error=f"Failed after {max_attempts} attempts. Last error: {last_error}",
            stage_name=stage_name,
        )

    async def _execute_fan_out(
        self,
        stage_def: StageDefinition,
        inputs: list[Any],
        context: PipelineContext,
    ) -> StageResult[list[Any]]:
        """Execute stage multiple times in parallel (fan-out pattern).

        Uses semaphore-based concurrency control if max_concurrent_fan_out is set.

        Args:
            stage_def: Stage definition
            inputs: List of inputs (one execution per input)
            context: Pipeline context

        Returns:
            StageResult containing list of outputs (or failure)
        """
        stage_name = stage_def.stage.name
        max_concurrent = stage_def.max_concurrent_fan_out

        if max_concurrent is not None:
            logger.debug(
                f"Fan-out: executing {stage_name} {len(inputs)} times "
                f"(max {max_concurrent} concurrent)"
            )
        else:
            logger.debug(f"Fan-out: executing {stage_name} {len(inputs)} times in parallel")

        # Execute with concurrency control if specified
        if max_concurrent is not None and max_concurrent > 0:
            semaphore = asyncio.Semaphore(max_concurrent)

            async def execute_with_limit(inp: Any) -> StageResult[Any]:
                async with semaphore:
                    return await stage_def.stage.execute(inp, context)

            tasks = [execute_with_limit(inp) for inp in inputs]
        else:
            # Unlimited concurrency
            tasks = [stage_def.stage.execute(inp, context) for inp in inputs]

        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Separate successes from failures
        successes = []
        failures = []

        for i, result in enumerate(results):
            if isinstance(result, Exception):
                failures.append((i, str(result)))
            elif isinstance(result, StageResult):
                if result.success:
                    successes.append(result.output)
                else:
                    error_msg = result.error if result.error is not None else "Unknown error"
                    failures.append((i, error_msg))
            else:
                failures.append((i, "Invalid result type"))

        if failures:
            logger.warning(f"Fan-out {stage_name}: {len(failures)}/{len(inputs)} executions failed")
            if stage_def.critical:
                # Critical stage - fail entire fan-out
                failure_details = "; ".join([f"[{i}]: {err}" for i, err in failures])
                return failure_result(
                    error=f"Fan-out failures: {failure_details}",
                    stage_name=stage_name,
                    metadata={"successes": len(successes), "failures": len(failures)},
                )

        logger.debug(f"Fan-out {stage_name}: {len(successes)}/{len(inputs)} succeeded")

        # Return list of successful outputs
        return success_result(
            output=successes,
            stage_name=stage_name,
            metadata={
                "total_executions": len(inputs),
                "successes": len(successes),
                "failures": len(failures),
            },
        )

    def _calculate_backoff_delay(
        self,
        attempt: int,
        retry_config: RetryConfig | None,
    ) -> float:
        """Calculate exponential backoff delay.

        Args:
            attempt: Current attempt number (0-based)
            retry_config: Retry configuration

        Returns:
            Delay in milliseconds
        """
        if not retry_config:
            return 0.0

        delay = retry_config.initial_delay_ms * (retry_config.backoff_multiplier ** (attempt - 1))
        return min(delay, retry_config.max_delay_ms)

    def _is_retryable_error(
        self,
        error: str | None,
        retry_config: RetryConfig | None,
    ) -> bool:
        """Check if error is retryable.

        Args:
            error: Error message
            retry_config: Retry configuration

        Returns:
            True if error should be retried
        """
        if not error or not retry_config or not retry_config.retryable_errors:
            return True  # Retry all errors by default

        # Check if error contains any retryable substring
        error_lower = error.lower()
        return any(retryable.lower() in error_lower for retryable in retry_config.retryable_errors)
