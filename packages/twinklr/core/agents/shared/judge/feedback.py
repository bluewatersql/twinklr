"""Feedback management for agent iterations."""

from __future__ import annotations

import logging
import time
from enum import Enum
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel, ConfigDict, Field

from twinklr.core.agents.issues import Issue

if TYPE_CHECKING:
    from twinklr.core.agents.analytics.repository import IssueRepository
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
    - Optionally record issues to persistent repository for cross-job learning

    Attributes:
        max_entries: Maximum feedback entries to keep
        entries: Current feedback entries
        agent_name: Name of agent for issue attribution
        job_id: Current job identifier
        issue_repository: Optional persistent issue storage
        previous_issue_ids: Issue IDs from previous iteration (for resolution tracking)
    """

    def __init__(
        self,
        max_entries: int = 25,
        agent_name: str = "unknown",
        job_id: str = "unknown",
        issue_repository: IssueRepository | None = None,
    ):
        """Initialize feedback manager.

        Args:
            max_entries: Maximum number of feedback entries to keep (default 25)
            agent_name: Name of agent for issue attribution (e.g., 'macro_planner_judge')
            job_id: Current job identifier for cross-job tracking
            issue_repository: Optional persistent issue repository (enabled by default if provided)
        """
        self.max_entries = max_entries
        self.agent_name = agent_name
        self.job_id = job_id
        self.issue_repository = issue_repository
        self.entries: list[FeedbackEntry] = []
        self.previous_issue_ids: set[str] = set()

        logger.debug(
            f"FeedbackManager initialized: max_entries={max_entries}, "
            f"agent={agent_name}, repository={'enabled' if issue_repository else 'disabled'}"
        )

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
        Only adds feedback to iteration loop for SOFT_FAIL and HARD_FAIL (APPROVE is a no-op for iteration).

        However, ALL issues are recorded to issue_repository for learning, regardless of verdict status.
        This enables learning from minor issues even in approved plans.

        Args:
            verdict: Judge verdict
            iteration: Current iteration number
        """
        from twinklr.core.agents.shared.judge.models import VerdictStatus

        # Add feedback for iteration loop (only on failures)
        if verdict.status == VerdictStatus.SOFT_FAIL:
            self.add_judge_soft_failure(
                message=verdict.feedback_for_planner,
                iteration=iteration,
                score=verdict.score,
                issues=verdict.issues,
                metadata={
                    "status": verdict.status.value,
                    "confidence": verdict.confidence,
                    # Don't include full verdict.model_dump() - too large for feedback
                },
            )
        elif verdict.status == VerdictStatus.HARD_FAIL:
            self.add_judge_hard_failure(
                message=verdict.feedback_for_planner,
                iteration=iteration,
                score=verdict.score,
                issues=verdict.issues,
                metadata={
                    "status": verdict.status.value,
                    "confidence": verdict.confidence,
                    # Don't include full verdict.model_dump() - too large for feedback
                },
            )
        # APPROVE is a no-op for iteration feedback

        # Record ALL issues to repository (regardless of verdict status) for learning
        # This captures minor issues (WARN/NIT) even from approved plans
        if self.issue_repository and verdict.issues:
            current_issue_ids = {issue.issue_id for issue in verdict.issues}

            self.issue_repository.record_issues(
                issues=verdict.issues,
                agent_name=self.agent_name,
                job_id=self.job_id,
                iteration=iteration,
                verdict_score=verdict.score,
                timestamp=time.time(),
                resolved_issue_ids=set(),  # Current issues are not resolved
            )

            # Update tracking for next iteration
            self.previous_issue_ids = current_issue_ids

            logger.debug(
                f"Recorded {len(verdict.issues)} issues for learning "
                f"(status={verdict.status.value}, score={verdict.score:.1f})"
            )

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

    def format_historical_for_prompt(self, filter_type: FeedbackType | None = None) -> str:
        """Format generic rules from current issues for historical learning context.

        Extracts reusable rules from issues for persistence and cross-job learning.
        This is used to build the general learning context that goes in developer prompts.

        Args:
            filter_type: Optional type filter (only include this type)

        Returns:
            Formatted rules string
        """
        # Filter if requested
        if filter_type:
            entries = self.get_by_type(filter_type)
        else:
            entries = self.entries

        if not entries:
            return ""

        # Collect unique rules
        rules = []
        for entry in entries:
            if entry.issues:
                rules.extend([issue.rule for issue in entry.issues if issue.rule])

        if not rules:
            return ""

        # Deduplicate while preserving order
        seen = set()
        unique_rules = []
        for rule in rules:
            if rule not in seen:
                seen.add(rule)
                unique_rules.append(rule)

        lines = ["Common patterns to avoid:"]
        for i, rule in enumerate(unique_rules, 1):
            lines.append(f"{i}. {rule}")

        return "\n".join(lines)

    def format_feedback_for_prompt(self, filter_type: FeedbackType | None = None) -> str:
        """Format specific feedback for current iteration's planner prompt.

        Provides detailed, actionable feedback about THIS plan's specific issues.
        Includes message, fix_hint, and acceptance_test for each issue.

        Args:
            filter_type: Optional type filter (only include this type)

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
        for _, entry in enumerate(entries, 1):
            # Format header
            lines.append(f"## Iteration {entry.iteration} Feedback ({entry.type.value})")
            lines.append("")

            # Add entry message if present (for validation failures)
            if entry.message and not entry.issues:
                lines.append(entry.message)
                lines.append("")
            # Format issues with detailed, actionable information
            elif entry.issues:
                # Group by severity
                errors = [i for i in entry.issues if i.severity.value == "ERROR"]
                warnings = [i for i in entry.issues if i.severity.value == "WARN"]
                nits = [i for i in entry.issues if i.severity.value == "NIT"]

                if errors:
                    lines.append("**BLOCKING ERRORS** (must fix):")
                    lines.append("")
                    for issue in errors:
                        lines.append(f"- **{issue.issue_id}** ({issue.category.value})")
                        lines.append(f"  Problem: {issue.message}")
                        if issue.targeted_actions:
                            lines.append("  Actions:")
                            for action in issue.targeted_actions:
                                parts = [f"[{action.action_type.value}]"]
                                parts.append(f"section={action.section_id}")
                                if action.lane:
                                    parts.append(f"lane={action.lane}")
                                if action.target:
                                    parts.append(f"target={action.target}")
                                if action.template_id:
                                    parts.append(f"template={action.template_id}")
                                if action.replacement_template_id:
                                    parts.append(f"-> {action.replacement_template_id}")
                                if action.palette_id:
                                    parts.append(f"palette={action.palette_id}")
                                lines.append(f"    - {', '.join(parts)}")
                                lines.append(f"      {action.description}")
                        else:
                            lines.append(f"  Fix: {issue.fix_hint}")
                        lines.append(f"  Success criteria: {issue.acceptance_test}")
                        lines.append("")

                if warnings:
                    lines.append("**Warnings** (should fix):")
                    lines.append("")
                    for issue in warnings:
                        lines.append(f"- **{issue.issue_id}** ({issue.category.value})")
                        lines.append(f"  Problem: {issue.message}")
                        if issue.targeted_actions:
                            lines.append("  Actions:")
                            for action in issue.targeted_actions:
                                parts = [f"[{action.action_type.value}]"]
                                parts.append(f"section={action.section_id}")
                                if action.lane:
                                    parts.append(f"lane={action.lane}")
                                if action.target:
                                    parts.append(f"target={action.target}")
                                if action.template_id:
                                    parts.append(f"template={action.template_id}")
                                if action.replacement_template_id:
                                    parts.append(f"-> {action.replacement_template_id}")
                                if action.palette_id:
                                    parts.append(f"palette={action.palette_id}")
                                lines.append(f"    - {', '.join(parts)}")
                                lines.append(f"      {action.description}")
                        else:
                            lines.append(f"  Fix: {issue.fix_hint}")
                        lines.append("")

                if nits:
                    lines.append("**Suggestions** (nice to have):")
                    lines.append("")
                    for issue in nits:
                        lines.append(f"- **{issue.issue_id}**: {issue.message}")
                        lines.append(f"  Suggestion: {issue.fix_hint}")
                        lines.append("")

        return "\n".join(lines)

    def format_for_prompt(self, filter_type: FeedbackType | None = None) -> str:
        """Alias for format_feedback_for_prompt (backward compatibility).

        Args:
            filter_type: Optional type filter (only include this type)

        Returns:
            Formatted feedback string
        """
        return self.format_feedback_for_prompt(filter_type)

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

    def format_with_learning_context(
        self, include_historical: bool = True, top_n_historical: int = 5
    ) -> str:
        """Format feedback with optional historical learning context.

        Combines current iteration feedback with historical learning context
        from the issue repository (if configured).

        Args:
            include_historical: Whether to include historical learning context
            top_n_historical: Number of top historical issues to include

        Returns:
            Formatted feedback string with learning context
        """
        lines = []

        # Add historical learning context if available
        if include_historical and self.issue_repository:
            historical_context = self.issue_repository.format_learning_context(
                agent_name=self.agent_name,
                top_n=top_n_historical,
                include_resolution_rate=True,
            )
            if historical_context:
                lines.append(historical_context)
                lines.append("")
                lines.append("---")
                lines.append("")

        # Add current iteration feedback
        current_feedback = self.format_feedback_for_prompt()
        lines.append(current_feedback)

        return "\n".join(lines)
