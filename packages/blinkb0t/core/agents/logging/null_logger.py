"""Null logger that discards all LLM call logs.

Use for testing or when logging is disabled.
"""

import uuid
from typing import Any


class NullLLMCallLogger:
    """Logger that discards all LLM call logs.

    Useful for:
    - Testing (avoid cluttering test output)
    - Disabled logging configuration
    - Dependency injection default

    Example:
        logger = NullLLMCallLogger()
        call_id = await logger.start_call_async(...)  # Returns dummy ID
        await logger.complete_call_async(call_id, ...)  # No-op
    """

    # =========================================================================
    # Async Methods
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
        """Return dummy call ID (async).

        Args:
            agent_name: Ignored
            agent_mode: Ignored
            iteration: Ignored
            model: Ignored
            temperature: Ignored
            prompts: Ignored
            context: Ignored
            **metadata: Ignored

        Returns:
            Dummy call ID
        """
        return f"null_{uuid.uuid4().hex[:8]}"

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
        """No-op completion (async).

        Args:
            call_id: Ignored
            raw_response: Ignored
            validated_response: Ignored
            validation_errors: Ignored
            tokens_used: Ignored
            prompt_tokens: Ignored
            completion_tokens: Ignored
            duration_seconds: Ignored
            success: Ignored
            repair_attempts: Ignored
        """

    async def flush_async(self) -> None:
        """No-op flush (async)."""

    # =========================================================================
    # Sync Methods (Backward Compatibility)
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
        """Return dummy call ID (sync).

        Args:
            agent_name: Ignored
            agent_mode: Ignored
            iteration: Ignored
            model: Ignored
            temperature: Ignored
            prompts: Ignored
            context: Ignored
            **metadata: Ignored

        Returns:
            Dummy call ID
        """
        return f"null_{uuid.uuid4().hex[:8]}"

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
        """No-op completion (sync).

        Args:
            call_id: Ignored
            raw_response: Ignored
            validated_response: Ignored
            validation_errors: Ignored
            tokens_used: Ignored
            prompt_tokens: Ignored
            completion_tokens: Ignored
            duration_seconds: Ignored
            success: Ignored
            repair_attempts: Ignored
        """

    def flush(self) -> None:
        """No-op flush (sync)."""
