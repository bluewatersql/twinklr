"""Agent state tracking."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class AgentState:
    """Agent execution state (mutable).

    Tracks:
    - Conversation ID for conversational agents
    - Attempt count for schema repair
    - Metadata for arbitrary tracking
    """

    name: str
    conversation_id: str | None = None
    attempt_count: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)
