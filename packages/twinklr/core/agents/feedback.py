"""Feedback management (moved to shared/judge/feedback.py).

This module provides backward-compatible imports for code that imports from
the old location. All new code should import from:
    twinklr.core.agents.shared.judge.feedback
"""

from twinklr.core.agents.shared.judge.feedback import (
    FeedbackEntry,
    FeedbackManager,
    FeedbackType,
)

__all__ = ["FeedbackEntry", "FeedbackManager", "FeedbackType"]
