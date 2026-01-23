"""Agent orchestration system."""

# Phase 1: Foundation (Complete)
from blinkb0t.core.agents.context import (
    BaseContextShaper,
    ContextShaper,
    IdentityContextShaper,
    ShapedContext,
    TokenEstimator,
)
from blinkb0t.core.agents.feedback import FeedbackEntry, FeedbackManager, FeedbackType
from blinkb0t.core.agents.prompts import PromptPackLoader, PromptRenderer
from blinkb0t.core.agents.providers import (
    LLMProvider,
    LLMProviderError,
    LLMResponse,
    OpenAIProvider,
    ProviderType,
    ResponseMetadata,
    TokenUsage,
)

# Phase 2: Agent Runner (Complete)
from blinkb0t.core.agents.result import AgentResult
from blinkb0t.core.agents.runner import AgentRunner, RunError
from blinkb0t.core.agents.spec import AgentMode, AgentSpec
from blinkb0t.core.agents.state import AgentState
from blinkb0t.core.agents.state_machine import (
    InvalidTransitionError,
    OrchestrationState,
    OrchestrationStateMachine,
    StateMetrics,
    StateTransition,
)

__all__ = [
    # Providers
    "LLMProvider",
    "OpenAIProvider",
    "ProviderType",
    "LLMResponse",
    "ResponseMetadata",
    "TokenUsage",
    "LLMProviderError",
    # State Machine
    "OrchestrationState",
    "OrchestrationStateMachine",
    "StateTransition",
    "StateMetrics",
    "InvalidTransitionError",
    # Feedback
    "FeedbackManager",
    "FeedbackEntry",
    "FeedbackType",
    # Context
    "ContextShaper",
    "BaseContextShaper",
    "IdentityContextShaper",
    "ShapedContext",
    "TokenEstimator",
    # Prompts
    "PromptPackLoader",
    "PromptRenderer",
    # Agent Runner
    "AgentSpec",
    "AgentMode",
    "AgentState",
    "AgentResult",
    "AgentRunner",
    "RunError",
]
