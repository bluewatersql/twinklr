from __future__ import annotations

from scripts.validation._core.models import ValidationIssue, ValidationResult
from scripts.validation._core.reporting import result_to_json_dict


def test_result_to_json_dict_includes_summary_categories_and_issues() -> None:
    result = ValidationResult(
        issues=[
            ValidationIssue(severity="ERROR", category="A", message="err"),
            ValidationIssue(severity="WARNING", category="B", message="warn"),
            ValidationIssue(severity="WARNING", category="B", message="warn2"),
        ],
        stats={"total_effects": 42},
        artifacts_checked=["/tmp/a.json"],
    )

    payload = result_to_json_dict("Test Validation", result)

    assert payload["title"] == "Test Validation"
    assert payload["summary"]["errors"] == 1
    assert payload["summary"]["warnings"] == 2
    assert payload["categories"] == {"A": 1, "B": 2}
    assert payload["artifacts_checked"] == ["/tmp/a.json"]
    assert payload["stats"] == {"total_effects": 42}
    assert len(payload["issues"]) == 3

