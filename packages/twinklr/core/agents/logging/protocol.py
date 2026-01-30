"""Protocol definition for LLM call logging."""

from typing import Any, Protocol


class LLMCallLogger(Protocol):
    """Protocol for LLM call logging (async-native).

    This protocol defines the interface for logging LLM calls with
    comprehensive capture of prompts, responses, metrics, and errors.

    Implementations should be async-native with sync wrappers for
    backward compatibility.

    Example:
        logger = AsyncFileLogger(output_dir, run_id)
        call_id = await logger.start_call_async(
            agent_name="planner",
            agent_mode="conversational",
            iteration=1,
            model="gpt-4",
            temperature=0.7,
            prompts={"system": "...", "user": "..."},
            context={"song_features": {...}},
        )
        # ... LLM call happens ...
        await logger.complete_call_async(
            call_id=call_id,
            raw_response=response_data,
            validated_response=validated_data,
            validation_errors=[],
            tokens_used=1500,
            prompt_tokens=1000,
            completion_tokens=500,
            duration_seconds=2.5,
            success=True,
            repair_attempts=0,
        )
        await logger.flush_async()
    """

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
            agent_mode: Agent execution mode (oneshot, conversational)
            iteration: Current iteration number (if in refinement loop)
            model: LLM model identifier
            temperature: Sampling temperature
            prompts: Dict of prompts (system, developer, user, examples)
            context: Context data passed to the agent
            **metadata: Additional metadata (run_id, conversation_id, etc.)

        Returns:
            Unique call ID for tracking this call
        """
        ...

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

        Implementations should log validated_response when validation succeeds,
        and fallback to raw_response when validation fails to avoid redundancy.

        Args:
            call_id: Unique call ID from start_call_async
            raw_response: Raw response from LLM (logged only if validation fails)
            validated_response: Validated response (logged only if validation succeeds, None if failed)
            validation_errors: List of validation error messages
            tokens_used: Total tokens used
            prompt_tokens: Tokens used for prompt
            completion_tokens: Tokens used for completion
            duration_seconds: Total call duration
            success: Whether the call was successful
            repair_attempts: Number of schema repair attempts
        """
        ...

    async def flush_async(self) -> None:
        """Flush buffered logs and write summary (async)."""
        ...

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
        """Log the start of an LLM call (sync wrapper).

        DEPRECATED: Use start_call_async() for new code.

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
        ...

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
        """Log the completion of an LLM call (sync wrapper).

        DEPRECATED: Use complete_call_async() for new code.

        Implementations should log validated_response when validation succeeds,
        and fallback to raw_response when validation fails to avoid redundancy.

        Args:
            call_id: Unique call ID from start_call
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
        ...

    def flush(self) -> None:
        """Flush buffered logs (sync wrapper).

        DEPRECATED: Use flush_async() for new code.
        """
        ...
