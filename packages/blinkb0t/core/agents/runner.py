"""Agent runner - synchronous wrapper for backward compatibility.

For new code, prefer using AsyncAgentRunner directly.
"""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path
from typing import Any

from blinkb0t.core.agents.async_runner import AsyncAgentRunner, RunError
from blinkb0t.core.agents.logging import LLMCallLogger
from blinkb0t.core.agents.providers.base import LLMProvider
from blinkb0t.core.agents.result import AgentResult
from blinkb0t.core.agents.spec import AgentSpec
from blinkb0t.core.agents.state import AgentState

logger = logging.getLogger(__name__)

# Re-export RunError for backward compatibility
__all__ = ["AgentRunner", "RunError"]


class AgentRunner:
    """Synchronous wrapper around AsyncAgentRunner.

    This is a thin wrapper for backward compatibility.
    For new code, prefer using AsyncAgentRunner directly.

    Responsibilities:
    - Provide sync interface for existing code
    - Delegate to AsyncAgentRunner for actual execution
    - Maintain backward compatibility

    Example:
        # Existing sync code continues to work
        runner = AgentRunner(provider, prompts_path)
        result = runner.run(spec, variables)

        # New async code should use AsyncAgentRunner
        async_runner = AsyncAgentRunner(provider, prompts_path, llm_logger)
        result = await async_runner.run(spec, variables)
    """

    def __init__(
        self,
        provider: LLMProvider,
        prompt_base_path: str | Path,
        llm_logger: LLMCallLogger | None = None,
    ):
        """Initialize agent runner (sync wrapper).

        Args:
            provider: LLM provider for API calls
            prompt_base_path: Base directory for prompt packs
            llm_logger: Optional LLM call logger (for observability)
        """
        self._async_runner = AsyncAgentRunner(
            provider=provider,
            prompt_base_path=prompt_base_path,
            llm_logger=llm_logger,
        )

        logger.debug(f"AgentRunner initialized with {provider.provider_type.value} provider")

    def run(
        self,
        spec: AgentSpec,
        variables: dict[str, Any],
        state: AgentState | None = None,
    ) -> AgentResult:
        """Execute agent with spec and variables (sync wrapper).

        This is a thin wrapper around AsyncAgentRunner.run().
        For new code, prefer using AsyncAgentRunner directly.

        Args:
            spec: Agent specification
            variables: Variables for prompt rendering
            state: Optional state (required for conversational agents)

        Returns:
            AgentResult with execution outcome
        """
        return asyncio.run(self._async_runner.run(spec, variables, state))

    @property
    def provider(self) -> LLMProvider:
        """Access underlying provider."""
        return self._async_runner.provider

    @property
    def prompt_loader(self):
        """Access underlying prompt loader."""
        return self._async_runner.prompt_loader

    @property
    def llm_logger(self) -> LLMCallLogger:
        """Access underlying LLM logger."""
        return self._async_runner.llm_logger
