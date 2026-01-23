"""Agent result model."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class AgentResult(BaseModel):
    """Generic agent result envelope.

    Standardized result format for all agents.
    """

    success: bool = Field(description="Whether agent succeeded")

    data: Any | None = Field(
        default=None,
        description="Response data (parsed and validated)",
    )

    error_message: str | None = Field(
        default=None,
        description="Error message if failed",
    )

    # Observability
    duration_seconds: float = Field(
        ge=0.0,
        description="Execution duration",
    )

    tokens_used: int = Field(
        ge=0,
        description="Tokens consumed",
    )

    conversation_id: str | None = Field(
        default=None,
        description="Conversation ID (for conversational agents)",
    )

    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Additional metadata (schema repair attempts, etc.)",
    )

    model_config = ConfigDict(frozen=True)
