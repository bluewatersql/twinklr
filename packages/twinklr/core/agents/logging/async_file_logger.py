"""Async file-based LLM call logger.

Uses aiofiles for non-blocking file I/O.
"""

import asyncio
import hashlib
import json
import uuid
from pathlib import Path
from typing import Any

import aiofiles  # type: ignore[import-untyped]
import yaml

from twinklr.core.agents.logging.models import AgentCallSummary, CallSummary, LLMCallLog
from twinklr.core.logging.sanitize import sanitize_dict


class AsyncFileLogger:
    """Async file-based LLM call logger.

    Writes detailed log files for each LLM call in YAML or JSON format.
    Uses aiofiles for non-blocking I/O.

    Directory structure:
        {output_dir}/logs/llm/{run_id}/
            ├── planner/
            │   ├── iter_00_call_001.yaml
            │   ├── iter_01_call_002.yaml
            │   └── ...
            ├── validator/
            │   └── ...
            ├── judge/
            │   └── ...
            └── summary.yaml

    Example:
        logger = AsyncFileLogger(
            output_dir=Path("artifacts/my_run"),
            run_id="run_2024_01_27_123456",
            log_level="standard",
            format="yaml",
        )
        call_id = await logger.start_call_async(...)
        # ... LLM call ...
        await logger.complete_call_async(call_id, ...)
        await logger.flush_async()
    """

    def __init__(
        self,
        output_dir: Path | str,
        run_id: str,
        log_level: str = "standard",
        format: str = "yaml",
        sanitize: bool = True,
    ):
        """Initialize async file logger.

        Args:
            output_dir: Base output directory
            run_id: Unique run identifier
            log_level: Log level ("minimal", "standard", "full")
            format: Output format ("yaml", "json")
            sanitize: Whether to sanitize sensitive data
        """
        self.output_dir = Path(output_dir)
        self.run_id = run_id
        self.log_level = log_level
        self.format = format
        self.sanitize_enabled = sanitize

        # Log directory
        self.log_dir = self.output_dir / "llm"
        self.log_dir.mkdir(parents=True, exist_ok=True)

        # Counters and buffers
        self.call_counters: dict[str, int] = {}
        self.pending_logs: dict[str, dict[str, Any]] = {}
        self.completed_logs: list[LLMCallLog] = []

        # Async lock for thread-safe operations
        self._lock = asyncio.Lock()

    # =========================================================================
    # Async Methods (PRIMARY)
    # =========================================================================

    async def start_call_async(
        self,
        agent_name: str,
        agent_mode: str,
        iteration: int | None,
        model: str,
        temperature: float,
        prompts: dict[str, Any],
        context: dict[str, Any],
        **metadata: Any,
    ) -> str:
        """Log the start of an LLM call (async).

        Args:
            agent_name: Name of the agent making the call
            agent_mode: Agent execution mode
            iteration: Current iteration number
            model: LLM model identifier
            temperature: Sampling temperature
            prompts: Dict of prompts
            context: Context data
            **metadata: Additional metadata

        Returns:
            Unique call ID
        """
        # Generate call ID
        call_id = f"{agent_name}_iter{iteration or 0}_{uuid.uuid4().hex[:8]}"

        # Increment counter
        async with self._lock:
            if agent_name not in self.call_counters:
                self.call_counters[agent_name] = 0
            self.call_counters[agent_name] += 1
            call_num = self.call_counters[agent_name]

        # Build log entry
        log_entry = LLMCallLog(
            call_id=call_id,
            agent_name=agent_name,
            agent_mode=agent_mode,
            iteration=iteration,
            model=model,
            temperature=temperature,
            system_prompt=prompts.get("system"),
            developer_prompt=prompts.get("developer"),
            user_prompt=prompts.get("user", ""),
            examples=prompts.get("examples", []),
            context_summary=self._format_context_summary(context),
            context_full=context if self.log_level == "full" else None,
            context_tokens=self._estimate_tokens(context),
            prompt_hashes=self._compute_prompt_hashes(prompts),
            run_id=metadata.get("run_id"),
            conversation_id=metadata.get("conversation_id"),
            provider=metadata.get("provider"),
        )

        # Store pending
        async with self._lock:
            self.pending_logs[call_id] = {
                "log_entry": log_entry,
                "agent_name": agent_name,
                "iteration": iteration,
                "call_num": call_num,
            }

        return call_id

    async def complete_call_async(
        self,
        call_id: str,
        raw_response: Any,
        validated_response: Any | None,
        validation_errors: list[str],
        tokens_used: int,
        prompt_tokens: int,
        completion_tokens: int,
        duration_seconds: float,
        success: bool,
        repair_attempts: int,
    ) -> None:
        """Log the completion of an LLM call (async).

        Logs only validated_response if validation succeeded, otherwise logs
        raw_response to avoid redundancy (they're identical 99% of the time).

        Args:
            call_id: Unique call ID from start_call_async
            raw_response: Raw response from LLM (logged only if validation fails)
            validated_response: Validated response (logged only if validation succeeds)
            validation_errors: List of validation errors
            tokens_used: Total tokens used
            prompt_tokens: Prompt tokens
            completion_tokens: Completion tokens
            duration_seconds: Call duration
            success: Whether successful
            repair_attempts: Schema repair attempts
        """
        async with self._lock:
            pending = self.pending_logs.get(call_id)
            if not pending:
                return

        log_entry: LLMCallLog = pending["log_entry"]

        # Update with response data
        # Only log validated_response if validation succeeded, otherwise log raw_response
        # This avoids redundancy since they're identical 99% of the time
        if validated_response is not None:
            log_entry.validated_response = validated_response
            log_entry.raw_response = None
        else:
            log_entry.raw_response = raw_response
            log_entry.validated_response = None
        log_entry.validation_errors = validation_errors
        log_entry.tokens_used = tokens_used
        log_entry.prompt_tokens = prompt_tokens
        log_entry.completion_tokens = completion_tokens
        log_entry.duration_seconds = round(duration_seconds, 3)
        log_entry.success = success
        log_entry.repair_attempts = repair_attempts

        # Sanitize if enabled
        if self.sanitize_enabled:
            log_entry = self._sanitize_log(log_entry)

        # Write to file (async)
        await self._write_log_file_async(
            agent_name=pending["agent_name"],
            iteration=pending["iteration"],
            call_num=pending["call_num"],
            log_entry=log_entry,
        )

        # Move to completed
        async with self._lock:
            self.completed_logs.append(log_entry)
            del self.pending_logs[call_id]

    async def flush_async(self) -> None:
        """Flush logs and write summary (async)."""
        await self._write_summary_async()
        await self._create_latest_symlink_async()

    # =========================================================================
    # Sync Wrappers (BACKWARD COMPATIBILITY)
    # =========================================================================

    def start_call(
        self,
        agent_name: str,
        agent_mode: str,
        iteration: int | None,
        model: str,
        temperature: float,
        prompts: dict[str, Any],
        context: dict[str, Any],
        **metadata: Any,
    ) -> str:
        """Log call start (sync wrapper).

        DEPRECATED: Use start_call_async() for new code.
        """
        return asyncio.run(
            self.start_call_async(
                agent_name,
                agent_mode,
                iteration,
                model,
                temperature,
                prompts,
                context,
                **metadata,
            )
        )

    def complete_call(
        self,
        call_id: str,
        raw_response: Any,
        validated_response: Any | None,
        validation_errors: list[str],
        tokens_used: int,
        prompt_tokens: int,
        completion_tokens: int,
        duration_seconds: float,
        success: bool,
        repair_attempts: int,
    ) -> None:
        """Log call completion (sync wrapper).

        DEPRECATED: Use complete_call_async() for new code.

        Logs validated_response when validation succeeds, otherwise logs
        raw_response to avoid redundancy.
        """
        asyncio.run(
            self.complete_call_async(
                call_id,
                raw_response,
                validated_response,
                validation_errors,
                tokens_used,
                prompt_tokens,
                completion_tokens,
                duration_seconds,
                success,
                repair_attempts,
            )
        )

    def flush(self) -> None:
        """Flush logs (sync wrapper).

        DEPRECATED: Use flush_async() for new code.
        """
        asyncio.run(self.flush_async())

    # =========================================================================
    # Private Helper Methods
    # =========================================================================

    async def _write_log_file_async(
        self,
        agent_name: str,
        iteration: int | None,
        call_num: int,
        log_entry: LLMCallLog,
    ) -> None:
        """Write log entry to file (async)."""
        # Create agent directory
        agent_dir = self.log_dir / agent_name / self.run_id
        agent_dir.mkdir(parents=True, exist_ok=True)

        # Generate filename
        ext = self.format
        filename = f"iter_{iteration or 0:02d}_call_{call_num:03d}.{ext}"
        filepath = agent_dir / filename

        # Convert to dict
        log_dict = log_entry.model_dump(exclude_none=True, mode="json")

        # Write based on format
        if self.format == "yaml":
            async with aiofiles.open(filepath, "w") as f:
                await f.write("---\n")
                await f.write(
                    yaml.dump(
                        log_dict, default_flow_style=False, sort_keys=False, allow_unicode=True
                    )
                )

        elif self.format == "json":
            async with aiofiles.open(filepath, "w") as f:
                await f.write(json.dumps(log_dict, indent=2, default=str))

    async def _write_summary_async(self) -> None:
        """Write summary file (async)."""
        if not self.completed_logs:
            return

        # Aggregate metrics
        total_calls = len(self.completed_logs)
        successful_calls = sum(1 for log in self.completed_logs if log.success)
        failed_calls = total_calls - successful_calls
        total_tokens = sum(log.tokens_used for log in self.completed_logs)
        total_prompt_tokens = sum(log.prompt_tokens for log in self.completed_logs)
        total_completion_tokens = sum(log.completion_tokens for log in self.completed_logs)
        total_duration = sum(log.duration_seconds for log in self.completed_logs)
        max_iteration = max((log.iteration or 0) for log in self.completed_logs)

        # Build per-agent summaries
        agent_stats: dict[str, dict[str, Any]] = {}
        for log in self.completed_logs:
            if log.agent_name not in agent_stats:
                agent_stats[log.agent_name] = {
                    "total_calls": 0,
                    "successful_calls": 0,
                    "failed_calls": 0,
                    "total_tokens": 0,
                    "total_duration": 0.0,
                    "repair_attempts": 0,
                }
            stats = agent_stats[log.agent_name]
            stats["total_calls"] += 1
            if log.success:
                stats["successful_calls"] += 1
            else:
                stats["failed_calls"] += 1
            stats["total_tokens"] += log.tokens_used
            stats["total_duration"] += log.duration_seconds
            stats["repair_attempts"] += log.repair_attempts

        agent_summaries = [
            AgentCallSummary(
                agent_name=agent_name,
                total_calls=stats["total_calls"],
                successful_calls=stats["successful_calls"],
                failed_calls=stats["failed_calls"],
                total_tokens=stats["total_tokens"],
                total_duration_seconds=round(stats["total_duration"], 2),
                avg_tokens_per_call=(
                    stats["total_tokens"] / stats["total_calls"] if stats["total_calls"] > 0 else 0
                ),
                avg_duration_seconds=(
                    stats["total_duration"] / stats["total_calls"]
                    if stats["total_calls"] > 0
                    else 0
                ),
                repair_attempts=stats["repair_attempts"],
            )
            for agent_name, stats in agent_stats.items()
        ]

        # Collect errors
        errors = []
        for log in self.completed_logs:
            if log.validation_errors:
                errors.extend(log.validation_errors)

        # Determine status
        if failed_calls == 0:
            status = "succeeded"
        elif successful_calls == 0:
            status = "failed"
        else:
            status = "partial"

        # Build summary
        summary = CallSummary(
            run_id=self.run_id,
            status=status,
            iterations=max_iteration,
            total_calls=total_calls,
            successful_calls=successful_calls,
            failed_calls=failed_calls,
            total_tokens=total_tokens,
            total_prompt_tokens=total_prompt_tokens,
            total_completion_tokens=total_completion_tokens,
            total_duration_seconds=round(total_duration, 2),
            agents=agent_summaries,
            errors=errors[:10],  # Limit to first 10 errors
            log_level=self.log_level,
            format=self.format,
        )

        # Write summary
        summary_path = self.log_dir / f"summary.{self.format}"
        summary_dict = summary.model_dump(exclude_none=True, mode="json")

        if self.format == "yaml":
            async with aiofiles.open(summary_path, "w") as f:
                await f.write("---\n")
                await f.write(
                    yaml.dump(
                        summary_dict, default_flow_style=False, sort_keys=False, allow_unicode=True
                    )
                )
        elif self.format == "json":
            async with aiofiles.open(summary_path, "w") as f:
                await f.write(json.dumps(summary_dict, indent=2, default=str))

    async def _create_latest_symlink_async(self) -> None:
        """Create 'latest' symlink (async)."""
        latest_link = self.output_dir / "logs" / "llm" / "latest"

        # Run in executor (symlink operations not async-native)
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, lambda: self._create_symlink_sync(latest_link))

    def _create_symlink_sync(self, latest_link: Path) -> None:
        """Create symlink (sync helper)."""
        if latest_link.exists() or latest_link.is_symlink():
            latest_link.unlink()
        latest_link.symlink_to(self.run_id)

    def _format_context_summary(self, context: dict[str, Any]) -> str:
        """Format context summary for logging."""
        if not context:
            return "No context provided"

        lines = []
        for key, value in context.items():
            if isinstance(value, dict):
                lines.append(f"  {key}: <dict with {len(value)} keys>")
            elif isinstance(value, list):
                lines.append(f"  {key}: <list with {len(value)} items>")
            elif isinstance(value, str) and len(value) > 100:
                lines.append(f"  {key}: <string {len(value)} chars>")
            else:
                lines.append(f"  {key}: {value}")

        return "\n".join(lines)

    def _estimate_tokens(self, context: dict[str, Any]) -> int:
        """Estimate token count for context (rough approximation)."""
        # Rough estimate: ~4 chars per token
        context_str = json.dumps(context, default=str)
        return len(context_str) // 4

    def _compute_prompt_hashes(self, prompts: dict[str, Any]) -> dict[str, str]:
        """Compute SHA256 hashes for prompts."""
        hashes = {}
        for key, value in prompts.items():
            if isinstance(value, str):
                hashes[key] = hashlib.sha256(value.encode()).hexdigest()[:16]
            elif isinstance(value, list):
                combined = json.dumps(value, sort_keys=True)
                hashes[key] = hashlib.sha256(combined.encode()).hexdigest()[:16]
        return hashes

    def _sanitize_log(self, log_entry: LLMCallLog) -> LLMCallLog:
        """Sanitize sensitive data from log entry."""
        # Convert to dict, sanitize, convert back
        log_dict = log_entry.model_dump()
        sanitized_dict = sanitize_dict(log_dict)
        return LLMCallLog(**sanitized_dict)
