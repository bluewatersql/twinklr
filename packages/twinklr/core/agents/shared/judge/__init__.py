"""Shared judge infrastructure for agent iteration and quality control."""

from twinklr.core.agents.shared.judge.controller import (
    IterationConfig,
    IterationContext,
    IterationResult,
    StandardIterationController,
)
from twinklr.core.agents.shared.judge.feedback import (
    FeedbackEntry,
    FeedbackManager,
    FeedbackType,
)
from twinklr.core.agents.shared.judge.models import (
    IterationState,
    JudgeVerdict,
    RevisionPriority,
    RevisionRequest,
    VerdictStatus,
)

__version__ = "1.0.0"

__all__ = [
    # Models
    "IterationState",
    "JudgeVerdict",
    "RevisionPriority",
    "RevisionRequest",
    "VerdictStatus",
    # Controller
    "IterationConfig",
    "IterationContext",
    "IterationResult",
    "StandardIterationController",
    # Feedback
    "FeedbackEntry",
    "FeedbackManager",
    "FeedbackType",
]
