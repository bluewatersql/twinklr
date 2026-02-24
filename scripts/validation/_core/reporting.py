from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from scripts.validation._core.models import ValidationIssue, ValidationResult


def _category_counts(issues: list[ValidationIssue]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for issue in issues:
        counts[issue.category] = counts.get(issue.category, 0) + 1
    return counts


def result_to_json_dict(title: str, result: ValidationResult) -> dict[str, object]:
    """Serialize validation results to JSON-compatible data."""
    categories = _category_counts(result.issues)
    return {
        "title": title,
        "summary": {
            "errors": result.error_count,
            "warnings": result.warning_count,
            "infos": result.info_count,
            "issue_count": len(result.issues),
            "exit_code": result.exit_code,
        },
        "categories": categories,
        "artifacts_checked": result.artifacts_checked,
        "stats": result.stats,
        "issues": [
            {
                "severity": issue.severity,
                "category": issue.category,
                "message": issue.message,
                "artifact": issue.artifact,
                "section_id": issue.section_id,
                "element_name": issue.element_name,
                "details": issue.details,
            }
            for issue in result.issues
        ],
    }


def write_result_json(path: Path, title: str, result: ValidationResult) -> None:
    """Write validation results to JSON."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(result_to_json_dict(title, result), indent=2), encoding="utf-8")


def print_text_summary(title: str, result: ValidationResult, *, max_issues: int = 25) -> None:
    """Print a richer CLI summary with category breakdown."""
    print(f"\n=== {title} ===")
    if not result.issues:
        print("PASS")
        if result.artifacts_checked:
            print(f"Artifacts checked: {len(result.artifacts_checked)}")
        return

    print(
        "Summary: "
        f"errors={result.error_count} warnings={result.warning_count} infos={result.info_count}"
    )
    if result.artifacts_checked:
        print(f"Artifacts checked ({len(result.artifacts_checked)}):")
        for artifact in result.artifacts_checked[:5]:
            print(f"  - {artifact}")
        if len(result.artifacts_checked) > 5:
            print(f"  - ... and {len(result.artifacts_checked) - 5} more")

    categories = _category_counts(result.issues)
    if categories:
        print("By Category:")
        for category, count in sorted(categories.items(), key=lambda item: (-item[1], item[0])):
            print(f"  - {category}: {count}")

    print("Issues:")
    for issue in result.issues[:max_issues]:
        print(f"{issue.severity}: {issue.category}: {issue.message}")
    if len(result.issues) > max_issues:
        print(f"... and {len(result.issues) - max_issues} more issues")
