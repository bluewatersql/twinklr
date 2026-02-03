"""Async agent runner - async-native execution engine for agents.

This is the primary implementation. For sync usage, use AgentRunner wrapper.
"""

from __future__ import annotations

import logging
import time
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from twinklr.core.agents.logging import LLMCallLogger, NullLLMCallLogger
from twinklr.core.agents.prompts import PromptPackLoader
from twinklr.core.agents.providers.base import LLMProvider
from twinklr.core.agents.providers.conversation import generate_conversation_id
from twinklr.core.agents.providers.errors import LLMProviderError
from twinklr.core.agents.result import AgentResult
from twinklr.core.agents.schema_utils import get_json_schema_example
from twinklr.core.agents.spec import AgentMode, AgentSpec
from twinklr.core.agents.state import AgentState
from twinklr.core.agents.taxonomy_utils import inject_taxonomy

logger = logging.getLogger(__name__)


class RunError(Exception):
    """Raised when agent execution fails."""

    pass


class AsyncAgentRunner:
    """Async-native agent execution engine.

    This is the primary implementation. All operations are async.
    For sync usage, use the AgentRunner wrapper.

    Responsibilities:
    - Load and render prompts
    - Call LLM provider (async)
    - Validate responses
    - Handle schema repair loop (async)
    - Log LLM calls (async)
    - Return standardized results

    Example:
        runner = AsyncAgentRunner(provider, prompts_path, llm_logger)
        result = await runner.run(spec, variables, state)
    """

    def __init__(
        self,
        provider: LLMProvider,
        prompt_base_path: str | Path,
        llm_logger: LLMCallLogger | None = None,
    ):
        """Initialize async agent runner.

        Args:
            provider: LLM provider (must support async methods)
            prompt_base_path: Base directory for prompt packs
            llm_logger: Optional LLM call logger (uses NullLLMCallLogger if not provided)
        """
        self.provider = provider
        self.prompt_loader = PromptPackLoader(base_path=prompt_base_path)
        self.llm_logger: LLMCallLogger = llm_logger or NullLLMCallLogger()

        logger.debug(f"AsyncAgentRunner initialized with {provider.provider_type.value} provider")

    async def run(
        self,
        spec: AgentSpec,
        variables: dict[str, Any],
        state: AgentState | None = None,
    ) -> AgentResult:
        """Execute agent with spec and variables (async).

        Args:
            spec: Agent specification
            variables: Variables for prompt rendering
            state: Optional state (required for conversational agents)

        Returns:
            AgentResult with execution outcome
        """
        start_time = time.time()
        start_usage = self.provider.get_token_usage()

        try:
            # Merge default variables
            merged_vars = {**spec.default_variables, **variables}

            # Auto-inject response schema to avoid drift between prompts and models
            if spec.response_model and hasattr(spec.response_model, "model_json_schema"):
                merged_vars["response_schema"] = get_json_schema_example(spec.response_model)

            # Auto-inject taxonomy enum values to avoid drift between prompts and enums
            merged_vars = inject_taxonomy(merged_vars)

            # Load and render prompts (sync, but fast)
            prompts = self.prompt_loader.load_and_render(spec.prompt_pack, merged_vars)

            # Build messages
            messages = self._build_messages(prompts, spec)

            # Start logging (async)
            call_id = await self._safe_log_start(
                spec=spec,
                variables=merged_vars,
                prompts=prompts,
                state=state,
            )

            # Execute with schema repair loop (async)
            response_data, repair_attempts = await self._execute_with_repair_async(
                spec, messages, state
            )

            # Calculate duration and tokens
            duration = time.time() - start_time
            end_usage = self.provider.get_token_usage()
            tokens = end_usage.total_tokens - start_usage.total_tokens

            # Track state if provided
            if state:
                state.attempt_count += 1

            # Complete logging (async)
            await self._safe_log_complete(
                call_id=call_id,
                raw_response=response_data,
                validated_response=response_data,
                validation_errors=[],
                start_usage=start_usage,
                end_usage=end_usage,
                duration=duration,
                success=True,
                repair_attempts=repair_attempts,
            )

            # Build result
            metadata: dict[str, Any] = {"schema_repair_attempts": repair_attempts}
            if state and state.conversation_id:
                metadata["conversation_id"] = state.conversation_id

            return AgentResult(
                success=True,
                data=response_data,
                duration_seconds=duration,
                tokens_used=tokens,
                conversation_id=state.conversation_id if state else None,
                metadata=metadata,
            )

        except LLMProviderError as e:
            duration = time.time() - start_time
            end_usage = self.provider.get_token_usage()
            tokens = end_usage.total_tokens - start_usage.total_tokens

            logger.error(f"Provider error in {spec.name}: {e}")

            return AgentResult(
                success=False,
                data=None,
                error_message=f"Provider error: {e}",
                duration_seconds=duration,
                tokens_used=tokens,
            )

        except RunError as e:
            duration = time.time() - start_time
            end_usage = self.provider.get_token_usage()
            tokens = end_usage.total_tokens - start_usage.total_tokens

            logger.error(f"Run error in {spec.name}: {e}")

            repair_attempts = spec.max_schema_repair_attempts
            metadata = {"schema_repair_attempts": repair_attempts}

            return AgentResult(
                success=False,
                data=None,
                error_message=str(e),
                duration_seconds=duration,
                tokens_used=tokens,
                metadata=metadata,
            )

        except Exception as e:
            duration = time.time() - start_time
            end_usage = self.provider.get_token_usage()
            tokens = end_usage.total_tokens - start_usage.total_tokens

            logger.error(f"Unexpected error in {spec.name}: {e}")

            return AgentResult(
                success=False,
                data=None,
                error_message=f"Execution error: {e}",
                duration_seconds=duration,
                tokens_used=tokens,
            )

    def _build_messages(self, prompts: dict[str, Any], spec: AgentSpec) -> list[dict[str, str]]:
        """Build message list for LLM provider.

        Args:
            prompts: Rendered prompts (system, developer, user, examples)
            spec: Agent specification

        Returns:
            List of message dicts
        """
        messages = []

        if "developer" in prompts:
            messages.append({"role": "developer", "content": prompts["developer"]})

        if "system" in prompts:
            messages.append({"role": "system", "content": prompts["system"]})

        if "examples" in prompts:
            messages.extend(prompts["examples"])

        if "user" in prompts:
            messages.append({"role": "user", "content": prompts["user"]})

        return messages

    async def _execute_with_repair_async(
        self,
        spec: AgentSpec,
        messages: list[dict[str, str]],
        state: AgentState | None,
    ) -> tuple[Any, int]:
        """Execute agent with schema repair loop (async).

        Args:
            spec: Agent specification
            messages: Messages for LLM
            state: Optional state (for conversation tracking)

        Returns:
            Tuple of (validated_data, repair_attempts)

        Raises:
            RunError: If schema validation exhausted attempts
            LLMProviderError: If provider fails
        """
        repair_attempts = 0

        for attempt in range(spec.max_schema_repair_attempts + 1):
            # Call provider (async, oneshot or conversational)
            if spec.mode == AgentMode.CONVERSATIONAL:
                response = await self._call_conversational_async(spec, messages, state)
            else:
                response = await self._call_oneshot_async(spec, messages)

            # Skip validation if response_model is dict
            if spec.response_model is dict:
                return response.content, 0

            # Try to validate response
            try:
                validated = spec.response_model(**response.content)
                logger.debug(f"Agent {spec.name} succeeded (repair attempts: {repair_attempts})")
                return validated, repair_attempts

            except ValidationError as e:
                repair_attempts += 1

                # Format validation error
                error_details = self._format_validation_error(e)

                # Log the failed response for debugging (first attempt only)
                if attempt == 0:
                    import json

                    try:
                        raw_json = json.dumps(response.content, indent=2)
                    except Exception:
                        raw_json = str(response.content)

                    logger.warning(
                        f"Agent {spec.name} FIRST schema validation failure:\n"
                        f"===== VALIDATION ERROR =====\n"
                        f"{error_details}\n"
                        f"===== RAW RESPONSE =====\n"
                        f"{raw_json}"
                    )
                else:
                    logger.warning(
                        f"Agent {spec.name} schema validation failed "
                        f"(attempt {attempt + 1}/{spec.max_schema_repair_attempts + 1})"
                    )

                if attempt >= spec.max_schema_repair_attempts:
                    logger.error(
                        f"Agent {spec.name} exhausted schema repair attempts "
                        f"({spec.max_schema_repair_attempts})"
                    )
                    raise RunError(
                        f"Schema validation failed after {repair_attempts} attempts: {e}"
                    ) from e

                # Add repair feedback to messages
                repair_message = (
                    f"Schema validation failed. Error:\n{error_details}\n\n"
                    f"Expected schema:\n{get_json_schema_example(spec.response_model)}\n\n"
                    f"Please fix the response to match the schema exactly."
                )

                messages.append({"role": "user", "content": repair_message})

        raise RunError("Schema repair loop exited unexpectedly")

    async def _call_oneshot_async(self, spec: AgentSpec, messages: list[dict[str, str]]) -> Any:
        """Call provider in oneshot mode (async).

        Args:
            spec: Agent specification
            messages: Messages for LLM

        Returns:
            LLM response
        """
        return await self.provider.generate_json_async(
            messages=messages,
            model=spec.model,
            temperature=spec.temperature,
        )

    async def _call_conversational_async(
        self,
        spec: AgentSpec,
        messages: list[dict[str, str]],
        state: AgentState | None,
    ) -> Any:
        """Call provider in conversational mode (async).

        Args:
            spec: Agent specification
            messages: Messages for LLM
            state: Agent state (for conversation tracking)

        Returns:
            LLM response
        """
        if not state:
            raise RunError(f"Conversational agent {spec.name} requires state but none provided")

        # Create or reuse conversation
        if not state.conversation_id:
            state.conversation_id = generate_conversation_id(spec.name, state.attempt_count)
            logger.debug(f"Created conversation: {state.conversation_id}")

        # Build system prompt (only for first message)
        system_prompt = None
        if state.attempt_count == 0:
            system_parts = []
            if any(m["role"] == "developer" for m in messages):
                system_parts.append(
                    next(m["content"] for m in messages if m["role"] == "developer")
                )
            if any(m["role"] == "system" for m in messages):
                system_parts.append(next(m["content"] for m in messages if m["role"] == "system"))

            system_prompt = "\n\n".join(system_parts) if system_parts else None

        # Get user message (last message should be user)
        user_messages = [m for m in messages if m["role"] == "user"]
        if not user_messages:
            raise RunError(f"No user message found in prompts for {spec.name}")

        user_message = user_messages[-1]["content"]

        return await self.provider.generate_json_with_conversation_async(
            user_message=user_message,
            conversation_id=state.conversation_id,
            model=spec.model,
            system_prompt=system_prompt,
            temperature=spec.temperature,
        )

    def _format_validation_error(self, error: ValidationError) -> str:
        """Format validation error for repair message.

        Args:
            error: Pydantic validation error

        Returns:
            Formatted error string
        """
        error_lines = []
        for err in error.errors():
            loc = ".".join(str(loc_part) for loc_part in err["loc"])
            msg = err["msg"]
            error_lines.append(f"- {loc}: {msg}")

        return "\n".join(error_lines)

    async def _safe_log_start(
        self,
        spec: AgentSpec,
        variables: dict[str, Any],
        prompts: dict[str, Any],
        state: AgentState | None,
    ) -> str:
        """Safely log call start (async).

        Never raises - logs errors and returns empty string on failure.
        """
        try:
            return await self.llm_logger.start_call_async(
                agent_name=spec.name,
                agent_mode=spec.mode.value,
                iteration=variables.get("iteration"),
                model=spec.model,
                temperature=spec.temperature,
                prompts=prompts,
                context=variables.get("context", {}),
                conversation_id=state.conversation_id if state else None,
                run_id=variables.get("run_id"),
                provider=self.provider.provider_type.value,
            )
        except Exception as e:
            logger.warning(f"Failed to log call start: {e}")
            return ""

    async def _safe_log_complete(
        self,
        call_id: str,
        raw_response: Any,
        validated_response: Any,
        validation_errors: list[str],
        start_usage: Any,
        end_usage: Any,
        duration: float,
        success: bool,
        repair_attempts: int,
    ) -> None:
        """Safely log call completion (async).

        Calculates per-call token deltas from start and end usage.
        Never raises - logs errors silently.

        Args:
            call_id: Call identifier from start_call_async
            raw_response: Raw LLM response
            validated_response: Validated response (after Pydantic parsing)
            validation_errors: List of validation error messages
            start_usage: TokenUsage before the call (cumulative)
            end_usage: TokenUsage after the call (cumulative)
            duration: Call duration in seconds
            success: Whether the call succeeded
            repair_attempts: Number of schema repair attempts
        """
        try:
            # Calculate per-call token deltas
            tokens_used = end_usage.total_tokens - start_usage.total_tokens
            prompt_tokens = end_usage.prompt_tokens - start_usage.prompt_tokens
            completion_tokens = end_usage.completion_tokens - start_usage.completion_tokens

            await self.llm_logger.complete_call_async(
                call_id=call_id,
                raw_response=raw_response,
                validated_response=validated_response,
                validation_errors=validation_errors,
                tokens_used=tokens_used,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                duration_seconds=duration,
                success=success,
                repair_attempts=repair_attempts,
            )
        except Exception as e:
            logger.warning(f"Failed to log call completion: {e}")
