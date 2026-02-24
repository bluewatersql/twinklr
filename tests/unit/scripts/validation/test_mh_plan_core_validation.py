from __future__ import annotations

from scripts.validation._core.mh_plan_validation import (
    cross_validate_plans,
    validate_evaluation_structure,
    validate_implementation_structure,
    validate_raw_plan_structure,
)


def test_validate_raw_plan_structure_requires_sections() -> None:
    issues = validate_raw_plan_structure({})

    assert any(issue.category == "RAW_PLAN_STRUCTURE" for issue in issues)
    assert any("sections" in issue.message for issue in issues)


def test_validate_implementation_structure_checks_required_fields() -> None:
    implementation = {
        "sections": [
            {
                "name": "Intro",
                "start_ms": 0,
                "end_ms": 1000,
            }
        ]
    }

    issues = validate_implementation_structure(implementation)

    assert any(issue.category == "IMPLEMENTATION_STRUCTURE" for issue in issues)
    assert any("template_id" in issue.message for issue in issues)


def test_validate_evaluation_structure_checks_mh_shape() -> None:
    issues = validate_evaluation_structure({"overall_score": 101, "channel_scoring": None})

    assert any("pass_threshold" in issue.message for issue in issues)
    assert any("overall_score" in issue.message for issue in issues)
    assert any("channel_scoring" in issue.message for issue in issues)


def test_cross_validate_plans_detects_missing_raw_section() -> None:
    raw_plan = {"sections": [{"name": "Verse"}]}
    implementation = {"sections": [{"name": "Chorus", "template_id": "tmpl"}]}

    issues = cross_validate_plans(raw_plan, implementation)

    assert any(issue.category == "CROSS_VALIDATION" for issue in issues)
    assert any("Verse" in issue.message for issue in issues)

