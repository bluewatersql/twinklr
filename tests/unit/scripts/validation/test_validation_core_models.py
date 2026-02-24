from __future__ import annotations

from scripts.validation._core.models import ValidationIssue, ValidationResult


def test_validation_result_counts_by_severity() -> None:
    result = ValidationResult()
    result.issues.append(
        ValidationIssue(severity="ERROR", category="STRUCTURE", message="bad raw plan")
    )
    result.issues.append(
        ValidationIssue(severity="WARNING", category="TIMING", message="gap detected")
    )
    result.issues.append(
        ValidationIssue(severity="INFO", category="SUMMARY", message="checked 4 sections")
    )

    assert result.error_count == 1
    assert result.warning_count == 1
    assert result.info_count == 1


def test_validation_result_exit_code_only_fails_on_errors() -> None:
    warning_only = ValidationResult(
        issues=[ValidationIssue(severity="WARNING", category="TIMING", message="warn")]
    )
    error_result = ValidationResult(
        issues=[ValidationIssue(severity="ERROR", category="TIMING", message="error")]
    )

    assert warning_only.exit_code == 0
    assert error_result.exit_code == 1

