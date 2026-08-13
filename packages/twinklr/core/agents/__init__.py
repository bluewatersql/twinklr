"""Agent orchestration system."""

# Phase 1: Foundation (Complete)
# Phase 2: Agent Runner (Complete)
from twinklr.core.agents.async_runner import AsyncAgentRunner, RunError
from twinklr.core.agents.context import (
    BaseContextShaper,
    ContextShaper,
    IdentityContextShaper,
    ShapedContext,
    TokenEstimator,
)
from twinklr.core.agents.issues import (
    ActionType,
    Issue,
    IssueCategory,
    IssueEffort,
    IssueLocation,
    IssueScope,
    IssueSeverity,
    SuggestedAction,
    TargetedAction,
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
from twinklr.core.agents.shared.judge.feedback import FeedbackEntry, FeedbackManager, FeedbackType
from twinklr.core.agents.spec import AgentMode, AgentSpec
from twinklr.core.agents.state import AgentState

__all__ = [
    # Issues
    "ActionType",
    "AgentMode",
    "AgentResult",
    # Agent Runner
    "AgentSpec",
    "AgentState",
    "AsyncAgentRunner",
    "AsyncFileLogger",
    "BaseContextShaper",
    "CallSummary",
    # Context
    "ContextShaper",
    "FeedbackEntry",
    # Feedback
    "FeedbackManager",
    "FeedbackType",
    "IdentityContextShaper",
    "Issue",
    "IssueCategory",
    "IssueEffort",
    "IssueLocation",
    "IssueScope",
    "IssueSeverity",
    "LLMCallLog",
    # LLM Logging (Phase 0)
    "LLMCallLogger",
    # Providers
    "LLMProvider",
    "LLMProviderError",
    "LLMResponse",
    "NullLLMCallLogger",
    "OpenAIProvider",
    # Prompts
    "PromptPackLoader",
    "PromptRenderer",
    "ProviderType",
    "ResponseMetadata",
    "RunError",
    "ShapedContext",
    "SuggestedAction",
    "TargetedAction",
    "TokenEstimator",
    "TokenUsage",
    "create_llm_logger",
]
