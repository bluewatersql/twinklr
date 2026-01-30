"""Feedback management for agent iterations."""

from __future__ import annotations

import logging
import time
from enum import Enum
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel, ConfigDict, Field

from twinklr.core.agents.issues import Issue

if TYPE_CHECKING:
    from twinklr.core.agents.shared.judge.models import JudgeVerdict

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

    # Structured issues
    issues: list[Issue] = Field(default_factory=list, description="Structured issues identified")

    # Optional metadata
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Additional metadata (scores, breakdown, confidence, etc.)",
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
        logger.debug(f"Added validation failure feedback (iteration {iteration})")

    def add_judge_soft_failure(
        self,
        message: str,
        iteration: int,
        score: float | None = None,
        issues: list[Issue] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """Add judge soft failure feedback (refinement needed).

        Args:
            message: Feedback message
            iteration: Current iteration number
            score: Optional evaluation score
            issues: Optional structured issues
            metadata: Optional metadata (score_breakdown, confidence, etc.)
        """
        meta = metadata or {}
        if score is not None:
            meta["score"] = score

        entry = FeedbackEntry(
            type=FeedbackType.JUDGE_SOFT_FAILURE,
            message=message,
            iteration=iteration,
            timestamp=time.time(),
            issues=issues or [],
            metadata=meta,
        )

        self._add_entry(entry)

        issue_count = len(issues) if issues else 0
        logger.debug(
            f"Added judge soft failure feedback "
            f"(iteration {iteration}, score={score}, issues={issue_count})"
        )

    def add_judge_hard_failure(
        self,
        message: str,
        iteration: int,
        score: float | None = None,
        issues: list[Issue] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """Add judge hard failure feedback (replan needed).

        Args:
            message: Feedback message
            iteration: Current iteration number
            score: Optional evaluation score
            issues: Optional structured issues
            metadata: Optional metadata (score_breakdown, confidence, etc.)
        """
        meta = metadata or {}
        if score is not None:
            meta["score"] = score

        entry = FeedbackEntry(
            type=FeedbackType.JUDGE_HARD_FAILURE,
            message=message,
            iteration=iteration,
            timestamp=time.time(),
            issues=issues or [],
            metadata=meta,
        )

        self._add_entry(entry)

        issue_count = len(issues) if issues else 0
        logger.debug(
            f"Added judge hard failure feedback "
            f"(iteration {iteration}, score={score}, issues={issue_count})"
        )

    def add_judge_verdict(self, verdict: JudgeVerdict, iteration: int) -> None:
        """Add judge verdict as feedback.

        Convenience method that determines feedback type based on verdict status.
        Only adds feedback for SOFT_FAIL and HARD_FAIL (APPROVE is a no-op).

        Args:
            verdict: Judge verdict
            iteration: Current iteration number
        """
        from twinklr.core.agents.shared.judge.models import VerdictStatus

        if verdict.status == VerdictStatus.SOFT_FAIL:
            self.add_judge_soft_failure(
                message=verdict.feedback_for_planner,
                iteration=iteration,
                score=verdict.score,
                issues=verdict.issues,
                metadata={"verdict": verdict.model_dump()},
            )
        elif verdict.status == VerdictStatus.HARD_FAIL:
            self.add_judge_hard_failure(
                message=verdict.feedback_for_planner,
                iteration=iteration,
                score=verdict.score,
                issues=verdict.issues,
                metadata={"verdict": verdict.model_dump()},
            )
        # APPROVE is a no-op (no feedback needed)

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

    def get_all_issues(self) -> list[Issue]:
        """Get all structured issues from all feedback entries.

        Returns:
            List of all issues across all feedback entries
        """
        issues = []
        for entry in self.entries:
            issues.extend(entry.issues)
        return issues

    def get_unresolved_issues(self, current_issues: list[Issue]) -> list[Issue]:
        """Get issues from previous iterations that are still present.

        Matches issues by issue_id to track resolution.

        Args:
            current_issues: Issues from current iteration

        Returns:
            List of issues from previous iterations still in current iteration
        """
        current_issue_ids = {issue.issue_id for issue in current_issues}
        previous_issues = self.get_all_issues()

        unresolved = []
        for prev_issue in previous_issues:
            if prev_issue.issue_id in current_issue_ids:
                unresolved.append(prev_issue)

        return unresolved

    def get_resolved_issues(self, current_issues: list[Issue]) -> list[Issue]:
        """Get issues from previous iterations that were resolved.

        Matches issues by issue_id to track resolution.

        Args:
            current_issues: Issues from current iteration

        Returns:
            List of issues from previous iterations not in current iteration
        """
        current_issue_ids = {issue.issue_id for issue in current_issues}
        previous_issues = self.get_all_issues()

        resolved = []
        for prev_issue in previous_issues:
            if prev_issue.issue_id not in current_issue_ids:
                resolved.append(prev_issue)

        return resolved

    def get_issues_by_severity(self, severity: str) -> list[Issue]:
        """Get all issues matching severity level.

        Args:
            severity: Severity level (ERROR, WARN, NIT)

        Returns:
            List of issues matching severity
        """
        all_issues = self.get_all_issues()
        return [issue for issue in all_issues if issue.severity.value == severity]
