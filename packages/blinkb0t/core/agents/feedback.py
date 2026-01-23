"""Feedback management for agent iterations."""

from __future__ import annotations

import logging
import time
from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

logger = logging.getLogger(__name__)


class FeedbackType(str, Enum):
    """Type of feedback."""

    VALIDATION_FAILURE = "validation_failure"
    JUDGE_SOFT_FAILURE = "judge_soft_failure"
    JUDGE_HARD_FAILURE = "judge_hard_failure"


class FeedbackEntry(BaseModel):
    """Single feedback entry.

    Represents one piece of feedback from validation or judge.
    """

    type: FeedbackType = Field(description="Feedback type")
    message: str = Field(description="Feedback message")
    iteration: int = Field(ge=0, description="Iteration number when feedback generated")
    timestamp: float = Field(description="Unix timestamp when feedback generated")

    # Optional metadata
    metadata: dict[str, Any] = Field(
        default_factory=dict, description="Additional metadata (scores, issues, etc.)"
    )

    model_config = ConfigDict(frozen=True)


class FeedbackManager:
    """Manages feedback collection and trimming.

    Responsibilities:
    - Collect feedback from validation and judge
    - Trim to N most recent entries
    - Format feedback for prompt inclusion
    - Track feedback history
    """

    def __init__(self, max_entries: int = 25):
        """Initialize feedback manager.

        Args:
            max_entries: Maximum number of feedback entries to keep (default 2)
        """
        self.max_entries = max_entries
        self.entries: list[FeedbackEntry] = []

        logger.debug(f"FeedbackManager initialized: max_entries={max_entries}")

    def add_validation_failure(
        self, message: str, iteration: int, metadata: dict[str, Any] | None = None
    ) -> None:
        """Add validation failure feedback.

        Args:
            message: Feedback message
            iteration: Current iteration number
            metadata: Optional metadata (validation issues, etc.)
        """
        entry = FeedbackEntry(
            type=FeedbackType.VALIDATION_FAILURE,
            message=message,
            iteration=iteration,
            timestamp=time.time(),
            metadata=metadata or {},
        )

        self._add_entry(entry)
        logger.info(f"Added validation failure feedback (iteration {iteration})")

    def add_judge_soft_failure(
        self,
        message: str,
        iteration: int,
        score: float | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """Add judge soft failure feedback (refinement needed).

        Args:
            message: Feedback message
            iteration: Current iteration number
            score: Optional evaluation score
            metadata: Optional metadata
        """
        meta = metadata or {}
        if score is not None:
            meta["score"] = score

        entry = FeedbackEntry(
            type=FeedbackType.JUDGE_SOFT_FAILURE,
            message=message,
            iteration=iteration,
            timestamp=time.time(),
            metadata=meta,
        )

        self._add_entry(entry)
        logger.info(f"Added judge soft failure feedback (iteration {iteration}, score={score})")

    def add_judge_hard_failure(
        self,
        message: str,
        iteration: int,
        score: float | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """Add judge hard failure feedback (replan needed).

        Args:
            message: Feedback message
            iteration: Current iteration number
            score: Optional evaluation score
            metadata: Optional metadata
        """
        meta = metadata or {}
        if score is not None:
            meta["score"] = score

        entry = FeedbackEntry(
            type=FeedbackType.JUDGE_HARD_FAILURE,
            message=message,
            iteration=iteration,
            timestamp=time.time(),
            metadata=meta,
        )

        self._add_entry(entry)
        logger.info(f"Added judge hard failure feedback (iteration {iteration}, score={score})")

    def _add_entry(self, entry: FeedbackEntry) -> None:
        """Add entry and trim to max_entries (FIFO).

        Args:
            entry: Feedback entry to add
        """
        self.entries.append(entry)

        # Trim to max_entries (keep most recent)
        if len(self.entries) > self.max_entries:
            removed = len(self.entries) - self.max_entries
            self.entries = self.entries[-self.max_entries :]
            logger.debug(
                f"Trimmed {removed} old feedback entries (keeping {self.max_entries} most recent)"
            )

    def get_all(self) -> list[FeedbackEntry]:
        """Get all current feedback entries.

        Returns:
            List of feedback entries (most recent last)
        """
        return self.entries.copy()

    def get_by_type(self, feedback_type: FeedbackType) -> list[FeedbackEntry]:
        """Get feedback entries by type.

        Args:
            feedback_type: Feedback type to filter by

        Returns:
            List of feedback entries matching type
        """
        return [e for e in self.entries if e.type == feedback_type]

    def format_for_prompt(
        self, filter_type: FeedbackType | None = None, include_metadata: bool = False
    ) -> str:
        """Format feedback for inclusion in agent prompt.

        Args:
            filter_type: Optional type filter (only include this type)
            include_metadata: Whether to include metadata in output

        Returns:
            Formatted feedback string
        """
        # Filter if requested
        if filter_type:
            entries = self.get_by_type(filter_type)
        else:
            entries = self.entries

        if not entries:
            return "No feedback available."

        lines = []
        for i, entry in enumerate(entries, 1):
            # Format header
            lines.append(f"Feedback {i} (iteration {entry.iteration}, {entry.type.value}):")

            # Add message
            lines.append(entry.message)

            # Add metadata if requested
            if include_metadata and entry.metadata:
                lines.append(f"Metadata: {entry.metadata}")

            # Add separator
            lines.append("")

        return "\n".join(lines)

    def clear(self) -> None:
        """Clear all feedback entries."""
        count = len(self.entries)
        self.entries.clear()
        logger.debug(f"Cleared {count} feedback entries")

    def count(self) -> int:
        """Get count of current feedback entries.

        Returns:
            Number of feedback entries
        """
        return len(self.entries)

    def is_empty(self) -> bool:
        """Check if feedback manager is empty.

        Returns:
            True if no feedback entries
        """
        return len(self.entries) == 0
