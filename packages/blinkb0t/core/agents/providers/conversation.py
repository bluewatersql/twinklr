"""Conversation management utilities."""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field


def generate_conversation_id(agent_name: str, iteration: int) -> str:
    """Generate unique conversation ID for tracking.

    Pattern: {agent_name}_iter{iteration}_{uuid}

    Examples:
        - planner_iter1_a3f4b2c1
        - implementation_iter2_7d8e9f0a

    Args:
        agent_name: Name of the agent
        iteration: Current iteration number

    Returns:
        Unique conversation identifier
    """
    return f"{agent_name}_iter{iteration}_{uuid.uuid4().hex[:8]}"


@dataclass
class Conversation:
    """Conversation state."""

    id: str
    messages: list[dict[str, str]] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)
