"""Persistent issue tracking for cross-job agent learning.

This module provides a JSON-based repository for tracking issues across
multiple job runs, enabling agents to learn from common mistakes.
"""

from __future__ import annotations

import json
import logging
from collections import Counter
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from twinklr.core.agents.issues import Issue, IssueCategory

logger = logging.getLogger(__name__)


class IssueRecord(BaseModel):
    """Persistent record of an issue with agent context.

    Tracks issues across job runs with metadata for analytics.

    Attributes:
        issue: The structured issue
        agent_name: Name of agent/judge that identified this issue
        job_id: Job identifier
        iteration: Iteration number when issue was identified
        verdict_score: Judge score when issue was identified
        timestamp: Unix timestamp
        resolved: Whether issue was resolved in next iteration
    """

    issue: Issue = Field(description="The structured issue")
    agent_name: str = Field(description="Agent/judge name (e.g., 'macro_planner_judge')")
    job_id: str = Field(description="Job identifier")
    iteration: int = Field(ge=0, description="Iteration number")
    verdict_score: float = Field(ge=0.0, le=10.0, description="Judge score")
    timestamp: float = Field(description="Unix timestamp")
    resolved: bool = Field(default=False, description="Resolved in next iteration")

    model_config = ConfigDict(frozen=True)


class IssueRepository:
    """Persistent JSON-based issue repository.

    Stores issues across job runs for analytics and learning context generation.
    Uses JSON-lines format for efficient append and streaming reads.

    The repository is organized by agent name:
    - {storage_dir}/{agent_name}_issues.jsonl

    Attributes:
        storage_dir: Directory for JSON-lines files
        enabled: Whether repository is enabled (for opt-out)
    """

    def __init__(self, storage_dir: Path | str, enabled: bool = True):
        """Initialize issue repository.

        Args:
            storage_dir: Directory for storing issue files
            enabled: Whether to actually record issues (opt-out flag)
        """
        self.storage_dir = Path(storage_dir)
        self.enabled = enabled

        if self.enabled:
            self.storage_dir.mkdir(parents=True, exist_ok=True)
            logger.debug(f"IssueRepository initialized: {self.storage_dir}")
        else:
            logger.debug("IssueRepository disabled (collection opt-out)")

    def record_issues(
        self,
        issues: list[Issue],
        agent_name: str,
        job_id: str,
        iteration: int,
        verdict_score: float,
        timestamp: float,
        resolved_issue_ids: set[str] | None = None,
    ) -> None:
        """Record issues from a judge verdict.

        Args:
            issues: List of issues to record
            agent_name: Agent/judge name
            job_id: Job identifier
            iteration: Iteration number
            verdict_score: Judge score
            timestamp: Unix timestamp
            resolved_issue_ids: Optional set of issue_ids that were resolved
        """
        if not self.enabled:
            return

        if not issues:
            return

        resolved_ids = resolved_issue_ids or set()

        # Append to agent-specific file
        file_path = self._get_agent_file(agent_name)

        records = []
        for issue in issues:
            record = IssueRecord(
                issue=issue,
                agent_name=agent_name,
                job_id=job_id,
                iteration=iteration,
                verdict_score=verdict_score,
                timestamp=timestamp,
                resolved=issue.issue_id in resolved_ids,
            )
            records.append(record)

        # Append as JSON-lines
        with file_path.open("a") as f:
            for record in records:
                f.write(record.model_dump_json() + "\n")
            f.flush()  # Explicit flush to prevent race conditions in async/parallel contexts

        logger.debug(
            f"Recorded {len(records)} issues for {agent_name} "
            f"(job: {job_id}, iteration: {iteration})"
        )

    def get_top_issues(
        self,
        agent_name: str,
        top_n: int = 10,
        min_occurrences: int = 1,
        max_records: int = 1000,
    ) -> list[tuple[IssueCategory, int, list[str]]]:
        """Get most common issue categories for an agent.

        Args:
            agent_name: Agent/judge name
            top_n: Number of top issues to return
            min_occurrences: Minimum occurrences to include (default: 1)
            max_records: Maximum records to scan (most recent)

        Returns:
            List of (category, count, generic_examples) tuples
        """
        if not self.enabled:
            return []

        file_path = self._get_agent_file(agent_name)
        if not file_path.exists():
            return []

        # Read records (most recent first)
        records = self._read_records(file_path, max_records=max_records)

        # Count by category and collect generic examples
        category_counts: Counter[IssueCategory] = Counter()
        category_examples: dict[IssueCategory, list[str]] = {}

        for record in records:
            category = record.issue.category
            category_counts[category] += 1

            # Collect generic examples (if available)
            if record.issue.generic_example:
                if category not in category_examples:
                    category_examples[category] = []
                # Deduplicate examples
                if record.issue.generic_example not in category_examples[category]:
                    category_examples[category].append(record.issue.generic_example)

        # Filter by min_occurrences and get top N
        filtered = [
            (cat, count, category_examples.get(cat, [])[:5])  # Max 5 examples per category
            for cat, count in category_counts.most_common()
            if count >= min_occurrences
        ]

        return filtered[:top_n]

    def get_recurring_issues(
        self,
        agent_name: str,
        min_occurrences: int = 3,
        max_records: int = 500,
    ) -> list[tuple[str, int, Issue]]:
        """Get specific issues that recur frequently (by issue_id).

        Useful for identifying persistent problems that need special attention.

        Args:
            agent_name: Agent/judge name
            min_occurrences: Minimum occurrences to include
            max_records: Maximum records to scan

        Returns:
            List of (issue_id, count, example_issue) tuples
        """
        if not self.enabled:
            return []

        file_path = self._get_agent_file(agent_name)
        if not file_path.exists():
            return []

        records = self._read_records(file_path, max_records=max_records)

        # Count by issue_id and keep one example
        issue_counts: Counter[str] = Counter()
        issue_examples: dict[str, Issue] = {}

        for record in records:
            issue_id = record.issue.issue_id
            issue_counts[issue_id] += 1
            if issue_id not in issue_examples:
                issue_examples[issue_id] = record.issue

        # Filter and return
        return [
            (issue_id, count, issue_examples[issue_id])
            for issue_id, count in issue_counts.most_common()
            if count >= min_occurrences
        ]

    def get_resolution_rate(
        self,
        agent_name: str,
        category: IssueCategory | None = None,
        max_records: int = 500,
    ) -> float:
        """Calculate resolution rate for issues.

        Resolution is inferred by comparing issue_ids in older records vs recent records.
        An issue is "resolved" if it appeared in older records but not in the most recent 25% of records.

        Args:
            agent_name: Agent/judge name
            category: Optional category filter
            max_records: Maximum records to scan

        Returns:
            Resolution rate (0.0-1.0), or 0.0 if no data
        """
        if not self.enabled:
            return 0.0

        file_path = self._get_agent_file(agent_name)
        if not file_path.exists():
            return 0.0

        records = self._read_records(file_path, max_records=max_records)

        # Filter by category if specified
        if category:
            records = [r for r in records if r.issue.category == category]

        if len(records) < 4:  # Need at least 4 records to calculate resolution
            return 0.0

        # Split into "old" (first 75%) and "recent" (last 25%)
        split_point = int(len(records) * 0.75)
        old_records = records[:split_point]
        recent_records = records[split_point:]

        # Get issue IDs from each period
        old_issue_ids = {r.issue.issue_id for r in old_records}
        recent_issue_ids = {r.issue.issue_id for r in recent_records}

        # Issues resolved = appeared in old but not in recent
        resolved_issue_ids = old_issue_ids - recent_issue_ids

        if not old_issue_ids:
            return 0.0

        return len(resolved_issue_ids) / len(old_issue_ids)

    def format_learning_context(
        self,
        agent_name: str,
        top_n: int = 5,
        include_resolution_rate: bool = True,
    ) -> str:
        """Format learning context for injection into developer.j2 prompt.

        Generates a concise summary of common issues for the agent to reference.

        Args:
            agent_name: Agent/judge name
            top_n: Number of top issues to include
            include_resolution_rate: Whether to include resolution stats

        Returns:
            Formatted learning context string (empty if no data)
        """
        if not self.enabled:
            return ""

        top_issues = self.get_top_issues(agent_name, top_n=top_n)

        if not top_issues:
            return ""

        lines = ["# Historical Learning Context", ""]
        lines.append(f"Based on {sum(count for _, count, _ in top_issues)} recent issues:")
        lines.append("")

        for category, _, examples in top_issues:
            lines.append(f"**{category.value}**:")

            # Add generic examples if available
            if examples:
                for example in examples[:5]:  # Max 5 examples per category
                    lines.append(f"  - Example: {example}")
            lines.append("")

        lines.append(
            "Use this context to be more vigilant about these recurring patterns, "
            "but evaluate each plan on its own merits."
        )

        return "\n".join(lines)

    def get_stats(self, agent_name: str) -> dict[str, Any]:
        """Get summary statistics for an agent.

        Args:
            agent_name: Agent/judge name

        Returns:
            Dictionary of stats (total_issues, unique_categories, etc.)
        """
        if not self.enabled:
            return {}

        file_path = self._get_agent_file(agent_name)
        if not file_path.exists():
            return {"total_issues": 0}

        records = self._read_records(file_path, max_records=None)

        categories = {r.issue.category for r in records}
        severities = {r.issue.severity for r in records}

        # Get most common category (with min_occurrences=1 to ensure we get results)
        top_issues = self.get_top_issues(agent_name, top_n=1, min_occurrences=1)
        most_common = top_issues[0][0].value if top_issues else None

        return {
            "total_issues": len(records),
            "unique_categories": len(categories),
            "unique_severities": len(severities),
            "resolution_rate": self.get_resolution_rate(agent_name),
            "most_common_category": most_common,
        }

    def _get_agent_file(self, agent_name: str) -> Path:
        """Get file path for agent's issue records.

        Args:
            agent_name: Agent/judge name

        Returns:
            Path to JSON-lines file
        """
        # Sanitize agent name for filename
        safe_name = agent_name.replace("/", "_").replace("\\", "_")
        return self.storage_dir / f"{safe_name}_issues.jsonl"

    def _read_records(self, file_path: Path, max_records: int | None = None) -> list[IssueRecord]:
        """Read records from JSON-lines file.

        Args:
            file_path: Path to JSON-lines file
            max_records: Maximum records to read (most recent), None for all

        Returns:
            List of issue records (most recent first if max_records set)
        """
        records = []

        try:
            with file_path.open("r") as f:
                lines = f.readlines()

            # If max_records specified, take most recent
            if max_records is not None:
                lines = lines[-max_records:]

            for line in lines:
                try:
                    data = json.loads(line)
                    record = IssueRecord.model_validate(data)
                    records.append(record)
                except Exception as e:
                    logger.warning(f"Failed to parse issue record: {e}")
                    continue

        except Exception as e:
            logger.error(f"Failed to read issue records from {file_path}: {e}")

        return records
