"""Agent runner - execution engine for agents."""

from __future__ import annotations

import logging
import time
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from blinkb0t.core.agents.prompts import PromptPackLoader
from blinkb0t.core.agents.providers.base import LLMProvider
from blinkb0t.core.agents.providers.conversation import generate_conversation_id
from blinkb0t.core.agents.providers.errors import LLMProviderError
from blinkb0t.core.agents.result import AgentResult
from blinkb0t.core.agents.schema_utils import get_json_schema_example
from blinkb0t.core.agents.spec import AgentMode, AgentSpec
from blinkb0t.core.agents.state import AgentState

logger = logging.getLogger(__name__)


class RunError(Exception):
    """Raised when agent execution fails."""

    pass


class AgentRunner:
    """Agent execution engine.

    Responsibilities:
    - Load and render prompts
    - Call LLM provider
    - Validate responses
    - Handle schema repair loop
    - Return standardized results
    """

    def __init__(
        self,
        provider: LLMProvider,
        prompt_base_path: str | Path,
    ):
        """Initialize agent runner.

        Args:
            provider: LLM provider for API calls
            prompt_base_path: Base directory for prompt packs
        """
        self.provider = provider
        self.prompt_loader = PromptPackLoader(base_path=prompt_base_path)

        logger.debug(f"AgentRunner initialized with {provider.provider_type.value} provider")

    def run(
        self,
        spec: AgentSpec,
        variables: dict[str, Any],
        state: AgentState | None = None,
    ) -> AgentResult:
        """Execute agent with spec and variables.

        Args:
            spec: Agent specification
            variables: Variables for prompt rendering
            state: Optional state (required for conversational agents)

        Returns:
            AgentResult with execution outcome
        """
        start_time = time.time()
        start_tokens = self.provider.get_token_usage().total_tokens

        try:
            # Merge default variables
            merged_vars = {**spec.default_variables, **variables}

            # Auto-inject response schema to avoid drift between prompts and models
            # Only for Pydantic models (not dict or other types)
            if spec.response_model and hasattr(spec.response_model, "model_json_schema"):
                merged_vars["response_schema"] = get_json_schema_example(spec.response_model)

            # Load and render prompts
            prompts = self.prompt_loader.load_and_render(spec.prompt_pack, merged_vars)

            # Build messages
            messages = self._build_messages(prompts, spec)

            # Execute with schema repair loop
            response_data, repair_attempts = self._execute_with_repair(spec, messages, state)

            # Calculate duration and tokens
            duration = time.time() - start_time
            tokens = self.provider.get_token_usage().total_tokens - start_tokens

            # Track state if provided
            if state:
                state.attempt_count += 1

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
            tokens = self.provider.get_token_usage().total_tokens - start_tokens

            logger.error(f"Provider error in {spec.name}: {e}")

            return AgentResult(
                success=False,
                data=None,
                error_message=f"Provider error: {e}",
                duration_seconds=duration,
                tokens_used=tokens,
            )

        except RunError as e:
            # RunError from schema validation exhaustion - extract repair attempts
            duration = time.time() - start_time
            tokens = self.provider.get_token_usage().total_tokens - start_tokens

            logger.error(f"Run error in {spec.name}: {e}")

            # Extract repair attempts from error message
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
            tokens = self.provider.get_token_usage().total_tokens - start_tokens

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

        # Add developer prompt (system-level instructions)
        if "developer" in prompts:
            messages.append({"role": "developer", "content": prompts["developer"]})

        # Add system prompt
        if "system" in prompts:
            messages.append({"role": "system", "content": prompts["system"]})

        # Add examples (few-shot)
        if "examples" in prompts:
            messages.extend(prompts["examples"])

        # Add user message
        if "user" in prompts:
            messages.append({"role": "user", "content": prompts["user"]})

        return messages

    def _execute_with_repair(
        self,
        spec: AgentSpec,
        messages: list[dict[str, str]],
        state: AgentState | None,
    ) -> tuple[Any, int]:
        """Execute agent with schema repair loop.

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
            # Call provider (oneshot or conversational)
            if spec.mode == AgentMode.CONVERSATIONAL:
                response = self._call_conversational(spec, messages, state)
            else:
                response = self._call_oneshot(spec, messages)

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

                if attempt >= spec.max_schema_repair_attempts:
                    # Exhausted attempts
                    logger.error(
                        f"Agent {spec.name} exhausted schema repair attempts "
                        f"({spec.max_schema_repair_attempts})"
                    )
                    raise RunError(
                        f"Schema validation failed after {repair_attempts} attempts: {e}"
                    ) from e

                # Add repair feedback to messages
                error_details = self._format_validation_error(e)
                repair_message = (
                    f"Schema validation failed. Error:\n{error_details}\n\n"
                    f"Expected schema:\n{get_json_schema_example(spec.response_model)}\n\n"
                    f"Please fix the response to match the schema exactly."
                )

                messages.append({"role": "user", "content": repair_message})
                logger.warning(
                    f"Agent {spec.name} schema validation failed "
                    f"(attempt {attempt + 1}/{spec.max_schema_repair_attempts + 1})"
                )

        # Should never reach here
        raise RunError("Schema repair loop exited unexpectedly")

    def _call_oneshot(self, spec: AgentSpec, messages: list[dict[str, str]]) -> Any:
        """Call provider in oneshot mode.

        Args:
            spec: Agent specification
            messages: Messages for LLM

        Returns:
            LLM response
        """
        return self.provider.generate_json(
            messages=messages,
            model=spec.model,
            temperature=spec.temperature,
        )

    def _call_conversational(
        self,
        spec: AgentSpec,
        messages: list[dict[str, str]],
        state: AgentState | None,
    ) -> Any:
        """Call provider in conversational mode.

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
            # Combine developer + system for first message
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

        return self.provider.generate_json_with_conversation(
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
