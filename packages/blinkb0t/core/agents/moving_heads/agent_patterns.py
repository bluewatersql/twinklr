"""Common patterns and protocols for agent implementations.

Extracted from 5 agent modules to reduce duplication and standardize interfaces.
Provides:
- PromptBuilder protocol for prompt construction
- ResponseParser protocol for LLM response handling
- AgentResult base model for consistent result structures
- StageExecutor base class for common LLM execution logic
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Generic, Protocol, TypeVar

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from blinkb0t.core.agents.moving_heads.context import ContextShaper, Stage
from blinkb0t.core.api.llm.openai.client import OpenAIClient, Verbosity
from blinkb0t.core.config.models import JobConfig

logger = logging.getLogger(__name__)

# Type variable for parsed results (covariant for Protocol)
T_co = TypeVar("T_co", bound=BaseModel, covariant=True)
T = TypeVar("T", bound=BaseModel)


# ============================================================================
# Common Result Model
# ============================================================================


class AgentResult(BaseModel, Generic[T]):
    """Base result model for agent operations.

    Provides consistent structure across all agents:
    - success flag
    - data payload (generic type)
    - error message
    - token usage tracking
    - optional metadata
    """

    success: bool = Field(description="Whether operation succeeded")
    data: T | None = Field(default=None, description="Result data if successful")
    error: str | None = Field(default=None, description="Error message if failed")
    tokens_used: int = Field(default=0, ge=0, description="Number of tokens used")
    metadata: dict[str, Any] | None = Field(default=None, description="Optional metadata")

    model_config = ConfigDict(
        frozen=False,
        extra="forbid",
        arbitrary_types_allowed=True,
    )


# ============================================================================
# Protocols
# ============================================================================


class PromptBuilder(Protocol):
    """Protocol for building prompts from context.

    Implementers must provide:
    - get_system_prompt(): Return system/developer prompt
    - build_user_prompt(context): Build user prompt from shaped context
    """

    def get_system_prompt(self) -> str:
        """Get system/developer prompt for this agent.

        Returns:
            System prompt string (from file or inline)
        """
        ...

    def build_user_prompt(self, context: dict[str, Any]) -> str:
        """Build user prompt from shaped context.

        Args:
            context: Shaped context data from ContextShaper

        Returns:
            User prompt string (typically JSON-formatted)
        """
        ...


class ResponseParser(Protocol[T_co]):
    """Protocol for parsing LLM responses.

    Implementers must provide:
    - parse_response(response): Parse and validate LLM response
    """

    def parse_response(self, response: str) -> T_co:
        """Parse and validate LLM response.

        Args:
            response: Raw LLM response string

        Returns:
            Validated Pydantic model instance

        Raises:
            json.JSONDecodeError: If response is not valid JSON
            ValidationError: If response doesn't match schema
        """
        ...


# ============================================================================
# Base Executor Class
# ============================================================================


class StageExecutor:
    """Base class for LLM-based agent stage execution.

    Provides common functionality:
    - Context shaping
    - Prompt building (delegates to PromptBuilder)
    - LLM calling with retries
    - Response parsing (delegates to ResponseParser)
    - Error handling and logging
    - Token tracking

    Subclasses must implement:
    - get_system_prompt()
    - build_user_prompt(context)
    - parse_response(response)

    Attributes:
        job_config: Job configuration
        openai_client: OpenAI API client
        context_shaper: Context shaping utility
        agent_config: Agent-specific configuration
    """

    def __init__(
        self,
        job_config: JobConfig,
        openai_client: OpenAIClient,
        agent_config_attr: str,
    ) -> None:
        """Initialize stage executor.

        Args:
            job_config: Job configuration
            openai_client: OpenAI API client
            agent_config_attr: Attribute name in job_config.agent for this agent's config
                             (e.g., "plan_agent", "judge_agent", etc.)
        """
        self.job_config = job_config
        self.openai_client = openai_client
        self.context_shaper = ContextShaper(job_config=job_config)

        # Extract agent-specific config
        self.agent_config = getattr(job_config.agent, agent_config_attr)

        logger.debug(f"{self.__class__.__name__} initialized")

    def load_system_prompt_from_file(self, prompt_path: Path) -> str:
        """Load system prompt from file.

        Args:
            prompt_path: Path to prompt file

        Returns:
            System prompt content

        Raises:
            FileNotFoundError: If prompt file doesn't exist
        """
        if not prompt_path.exists():
            raise FileNotFoundError(f"System prompt not found: {prompt_path}")

        return prompt_path.read_text()

    def shape_context(
        self,
        stage: Stage,
        song_features: dict[str, Any],
        seq_fingerprint: dict[str, Any],
        template_metadata: list[dict[str, Any]],
        **kwargs: Any,
    ) -> dict[str, Any]:
        """Shape context for this stage.

        Args:
            stage: Agent stage (PLAN, IMPLEMENTATION, JUDGE, etc.)
            song_features: Audio analysis features
            seq_fingerprint: Sequence fingerprint
            template_metadata: Template library metadata
            **kwargs: Additional context data (plan, implementation, etc.)

        Returns:
            Shaped context data dictionary
        """
        shaped_context = self.context_shaper.shape_for_stage(
            stage=stage,
            song_features=song_features,
            seq_fingerprint=seq_fingerprint,
            template_metadata=template_metadata,
            **kwargs,
        )

        logger.info(
            f"Context shaped for {stage.value}: {shaped_context.token_estimate} tokens "
            f"(reduced {shaped_context.reduction_pct:.1f}%)"
        )

        return shaped_context.data

    def execute_llm_call(
        self,
        system_prompt: str,
        user_prompt: str,
        response_model: type[T],
        verbosity: Verbosity = Verbosity.LOW,
    ) -> tuple[T | None, int, str | None, list[dict[str, str]] | None]:
        """Execute LLM call with parsing and error handling.

        Args:
            system_prompt: System/developer prompt
            user_prompt: User prompt with context
            response_model: Pydantic model for response validation
            verbosity: LLM verbosity level

        Returns:
            Tuple of (parsed_result, tokens_used, error_message, original_messages)
            - parsed_result: Validated model instance or None if failed
            - tokens_used: Number of tokens consumed
            - error_message: Error description or None if successful
            - original_messages: Original messages for conversational refinement
        """
        try:
            # Build messages list
            messages: list[dict[str, str]] = [
                {"role": "developer", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ]

            logger.debug(f"Calling LLM with {len(messages)} messages")

            # Get token usage before call
            tokens_before = self.openai_client.get_total_token_usage().total_tokens

            # Call LLM - generate_json returns parsed JSON directly (dict)
            response_data = self.openai_client.generate_json(
                messages=messages,
                model=self.agent_config.model,
                temperature=self.agent_config.temperature,
                verbosity=verbosity,
            )

            # Get token usage after call
            tokens_after = self.openai_client.get_total_token_usage().total_tokens
            tokens_used = tokens_after - tokens_before
            logger.info(f"LLM response received: {tokens_used} tokens")

            # Validate response (generate_json already parsed JSON)
            try:
                parsed = response_model.model_validate(response_data)
                return parsed, tokens_used, None, messages

            except ValidationError as e:
                error_msg = f"Failed to validate response: {e}"
                logger.error(error_msg)
                logger.debug(f"Invalid response: {json.dumps(response_data)[:500]}...")
                return None, tokens_used, error_msg, messages

        except Exception as e:
            error_msg = f"LLM call failed: {e}"
            logger.error(error_msg, exc_info=True)
            return None, 0, error_msg, None

    def _parse_and_validate(self, response_text: str, model: type[T]) -> T:
        """Parse JSON and validate against Pydantic model.

        Args:
            response_text: Raw LLM response
            model: Pydantic model class

        Returns:
            Validated model instance

        Raises:
            json.JSONDecodeError: If response is not valid JSON
            ValidationError: If response doesn't match schema
        """
        # Try to parse JSON
        data = json.loads(response_text)

        # Validate with Pydantic
        validated = model.model_validate(data)

        return validated

    # Subclasses should implement these if using PromptBuilder/ResponseParser protocols
    def get_system_prompt(self) -> str:
        """Get system prompt for this agent.

        Must be implemented by subclasses.
        """
        raise NotImplementedError("Subclass must implement get_system_prompt()")

    def build_user_prompt(self, context: dict[str, Any]) -> str:
        """Build user prompt from context.

        Must be implemented by subclasses.
        """
        raise NotImplementedError("Subclass must implement build_user_prompt()")

    def parse_response(self, response: str) -> Any:
        """Parse LLM response.

        Must be implemented by subclasses.
        """
        raise NotImplementedError("Subclass must implement parse_response()")
