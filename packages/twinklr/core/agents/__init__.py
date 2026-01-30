"""Agent orchestration system."""

# Phase 1: Foundation (Complete)
# Phase 2: Agent Runner (Complete)
from twinklr.core.agents.async_runner import AsyncAgentRunner
from twinklr.core.agents.context import (
    BaseContextShaper,
    ContextShaper,
    IdentityContextShaper,
    ShapedContext,
    TokenEstimator,
)
from twinklr.core.agents.feedback import FeedbackEntry, FeedbackManager, FeedbackType
from twinklr.core.agents.issues import (
    Issue,
    IssueCategory,
    IssueEffort,
    IssueLocation,
    IssueScope,
    IssueSeverity,
    SuggestedAction,
)

# Phase 0: Async Infrastructure + LLM Logging
from twinklr.core.agents.logging import (
    AsyncFileLogger,
    CallSummary,
    LLMCallLog,
    LLMCallLogger,
    NullLLMCallLogger,
    create_llm_logger,
)
from twinklr.core.agents.prompts import PromptPackLoader, PromptRenderer
from twinklr.core.agents.providers import (
    LLMProvider,
    LLMProviderError,
    LLMResponse,
    OpenAIProvider,
    ProviderType,
    ResponseMetadata,
    TokenUsage,
)
from twinklr.core.agents.result import AgentResult
from twinklr.core.agents.runner import AgentRunner, RunError
from twinklr.core.agents.spec import AgentMode, AgentSpec
from twinklr.core.agents.state import AgentState
from twinklr.core.agents.state_machine import (
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
    # Issues
    "Issue",
    "IssueCategory",
    "IssueSeverity",
    "IssueEffort",
    "IssueScope",
    "IssueLocation",
    "SuggestedAction",
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
    "AsyncAgentRunner",
    "RunError",
    # LLM Logging (Phase 0)
    "LLMCallLogger",
    "AsyncFileLogger",
    "NullLLMCallLogger",
    "create_llm_logger",
    "LLMCallLog",
    "CallSummary",
]
