"""Data models for LLM call logging."""

from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, Field


class LLMCallLog(BaseModel):
    """Complete log entry for an LLM call.

    Captures all information about an LLM call including prompts,
    responses, metrics, and errors.
    """

    # Call identification
    call_id: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    # Agent information
    agent_name: str
    agent_mode: str
    iteration: int | None = None

    # Model configuration
    model: str
    temperature: float

    # Prompts
    system_prompt: str | None = None
    developer_prompt: str | None = None
    user_prompt: str = ""
    examples: list[dict[str, str]] = Field(default_factory=list)

    # Context
    context_summary: str | None = None
    context_full: dict[str, Any] | None = None
    context_tokens: int | None = None

    # Prompt hashes (for detecting changes)
    prompt_hashes: dict[str, str] = Field(default_factory=dict)

    # Response (set on completion)
    raw_response: Any | None = None
    validated_response: Any | None = None
    validation_errors: list[str] = Field(default_factory=list)

    # Metrics (set on completion)
    tokens_used: int = 0
    prompt_tokens: int = 0
    completion_tokens: int = 0
    duration_seconds: float = 0.0

    # Status (set on completion)
    success: bool = False
    repair_attempts: int = 0

    # Additional metadata
    run_id: str | None = None
    conversation_id: str | None = None
    provider: str | None = None

    model_config = {"extra": "allow"}


class AgentCallSummary(BaseModel):
    """Summary of calls for a single agent."""

    agent_name: str
    total_calls: int = 0
    successful_calls: int = 0
    failed_calls: int = 0
    total_tokens: int = 0
    total_duration_seconds: float = 0.0
    avg_tokens_per_call: float = 0.0
    avg_duration_seconds: float = 0.0
    repair_attempts: int = 0


class CallSummary(BaseModel):
    """Summary of all LLM calls for a run.

    Written to summary.yaml at the end of a run.
    """

    # Run identification
    run_id: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    status: str = "succeeded"  # succeeded, failed, partial

    # High-level metrics
    iterations: int = 0
    total_calls: int = 0
    successful_calls: int = 0
    failed_calls: int = 0
    total_tokens: int = 0
    total_prompt_tokens: int = 0
    total_completion_tokens: int = 0
    total_duration_seconds: float = 0.0

    # Per-agent breakdown
    agents: list[AgentCallSummary] = Field(default_factory=list)

    # Error summary
    errors: list[str] = Field(default_factory=list)

    # Additional info
    log_level: str = "standard"
    format: str = "yaml"

    model_config = {"frozen": True}
