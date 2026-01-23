"""Agent specification model."""

from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class AgentMode(str, Enum):
    """Agent execution mode."""

    ONESHOT = "oneshot"  # Single request/response
    CONVERSATIONAL = "conversational"  # Multi-turn with state


class AgentSpec(BaseModel):
    """Agent specification (configuration).

    Data-only configuration for agent execution.
    AgentRunner uses this spec to execute agents without separate classes.
    """

    # Identity
    name: str = Field(description="Agent name (for logging, conversation IDs)")

    # Prompt configuration
    prompt_pack: str = Field(
        description="Name of prompt pack directory (system.j2, developer.j2, user.j2, examples.jsonl)"
    )

    # Response configuration
    response_model: type[Any] = Field(
        description="Pydantic model for response validation (or dict for unstructured)"
    )

    # Execution mode
    mode: AgentMode = Field(
        default=AgentMode.ONESHOT,
        description="Execution mode: oneshot (stateless) or conversational (multi-turn)",
    )

    # LLM settings
    model: str = Field(
        default="gpt-5.2",
        description="LLM model identifier",
    )

    temperature: float = Field(
        default=0.7,
        ge=0.0,
        le=2.0,
        description="Sampling temperature",
    )

    # Schema repair
    max_schema_repair_attempts: int = Field(
        default=2,
        ge=0,
        description="Max attempts to auto-repair schema validation failures",
    )

    # Variables and budgets
    default_variables: dict[str, Any] = Field(
        default_factory=dict,
        description="Default variables for prompt rendering",
    )

    token_budget: int | None = Field(
        default=None,
        ge=0,
        description="Optional token budget for this agent",
    )

    model_config = ConfigDict(frozen=True, arbitrary_types_allowed=True)
