from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

ValidationSeverity = str


@dataclass(frozen=True)
class ValidationIssue:
    """Structured validation issue."""

    severity: ValidationSeverity
    category: str
    message: str
    artifact: str | None = None
    section_id: str | None = None
    element_name: str | None = None
    details: dict[str, Any] = field(default_factory=dict)


@dataclass
class ValidationResult:
    """Aggregated validation results."""

    issues: list[ValidationIssue] = field(default_factory=list)
    stats: dict[str, Any] = field(default_factory=dict)
    artifacts_checked: list[str] = field(default_factory=list)

    @property
    def error_count(self) -> int:
        return sum(1 for issue in self.issues if issue.severity == "ERROR")

    @property
    def warning_count(self) -> int:
        return sum(1 for issue in self.issues if issue.severity == "WARNING")

    @property
    def info_count(self) -> int:
        return sum(1 for issue in self.issues if issue.severity == "INFO")

    @property
    def exit_code(self) -> int:
        return 1 if self.error_count > 0 else 0

    def extend(self, issues: list[ValidationIssue]) -> None:
        """Append multiple issues."""
        self.issues.extend(issues)
