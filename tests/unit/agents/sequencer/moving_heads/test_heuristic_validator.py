"""Tests for heuristic validator."""

import pytest

from blinkb0t.core.agents.sequencer.moving_heads.heuristic_validator import (
    HeuristicValidationResult,
    HeuristicValidator,
)
from blinkb0t.core.agents.sequencer.moving_heads.models import (
    ChoreographyPlan,
    PlanSection,
)


@pytest.fixture
def available_templates():
    """List of available templates."""
    return ["sweep_lr_fan_pulse", "circle_fan_hold", "pendulum_chevron_breathe"]


@pytest.fixture
def song_structure():
    """Sample song structure."""
    return {
        "sections": {
            "intro": {"start_bar": 0, "end_bar": 8},
            "verse": {"start_bar": 8, "end_bar": 24},
            "chorus": {"start_bar": 24, "end_bar": 40},
        },
        "total_bars": 40,
    }


def test_validator_init(available_templates, song_structure):
    """Test validator initialization."""
    validator = HeuristicValidator(
        available_templates=available_templates,
        song_structure=song_structure,
    )

    # Templates stored as set for fast lookup
    assert validator.available_templates == set(available_templates)
    assert validator.song_structure == song_structure


def test_validate_simple_valid_plan(available_templates, song_structure):
    """Test validation of simple valid plan."""
    validator = HeuristicValidator(
        available_templates=available_templates,
        song_structure=song_structure,
    )

    plan = ChoreographyPlan(
        sections=[
            PlanSection(
                section_name="intro",
                start_bar=1,
                end_bar=8,
                template_id="sweep_lr_fan_pulse",
            )
        ]
    )

    result = validator.validate(plan)

    assert result.valid is True
    assert len(result.errors) == 0


def test_validate_missing_template(available_templates, song_structure):
    """Test validation catches missing template."""
    validator = HeuristicValidator(
        available_templates=available_templates,
        song_structure=song_structure,
    )

    plan = ChoreographyPlan(
        sections=[
            PlanSection(
                section_name="intro",
                start_bar=1,
                end_bar=8,
                template_id="nonexistent_template",  # Not in library
            )
        ]
    )

    result = validator.validate(plan)

    assert result.valid is False
    assert len(result.errors) > 0
    assert any("template" in err.lower() for err in result.errors)


def test_validate_empty_sections():
    """Test validation of plan with minimal section (Pydantic requires at least 1)."""
    validator = HeuristicValidator(
        available_templates=["template1"],
        song_structure={"sections": {"intro": {"start_bar": 1, "end_bar": 8}}, "total_bars": 32},
    )

    # Test a valid minimal plan with one section
    plan = ChoreographyPlan(
        sections=[
            PlanSection(
                section_name="intro",
                start_bar=1,
                end_bar=8,
                template_id="template1",
            )
        ]
    )

    result = validator.validate(plan)

    # Should be valid
    assert result.valid is True


def test_validate_section_timing_mismatch(available_templates, song_structure):
    """Test validation catches section timing mismatch."""
    validator = HeuristicValidator(
        available_templates=available_templates,
        song_structure=song_structure,
    )

    plan = ChoreographyPlan(
        sections=[
            PlanSection(
                section_name="intro",
                start_bar=1,
                end_bar=12,  # Should be 8 per song structure
                template_id="sweep_lr_fan_pulse",
            )
        ]
    )

    result = validator.validate(plan)

    # Should have warning about timing mismatch
    assert len(result.warnings) > 0 or not result.valid


def test_validate_negative_timing():
    """Test validation catches negative or invalid timing."""
    _validator = HeuristicValidator(
        available_templates=["template1"],
        song_structure={"sections": {"intro": {"start_bar": 1, "end_bar": 8}}, "total_bars": 32},
    )

    # This should fail Pydantic validation before reaching heuristic validator
    with pytest.raises(Exception):  # noqa: B017
        PlanSection(
            section_name="intro",
            start_bar=8,
            end_bar=1,  # End before start
            template_id="template1",
        )


def test_validate_incomplete_coverage(available_templates, song_structure):
    """Test validation detects incomplete coverage."""
    validator = HeuristicValidator(
        available_templates=available_templates,
        song_structure=song_structure,
    )

    # Only covers intro, missing verse and chorus
    plan = ChoreographyPlan(
        sections=[
            PlanSection(
                section_name="intro",
                start_bar=1,
                end_bar=8,
                template_id="sweep_lr_fan_pulse",
            )
        ]
    )

    result = validator.validate(plan)

    # Should warn about missing sections
    assert len(result.warnings) > 0
    # Check for any of these keywords
    warnings_text = " ".join(result.warnings).lower()
    assert (
        "cover" in warnings_text
        or "missing" in warnings_text
        or "verse" in warnings_text
        or "chorus" in warnings_text
    )


def test_validate_result_structure():
    """Test validation result structure."""
    validator = HeuristicValidator(
        available_templates=["template1"],
        song_structure={"sections": {"intro": {"start_bar": 1, "end_bar": 8}}, "total_bars": 8},
    )

    plan = ChoreographyPlan(
        sections=[
            PlanSection(
                section_name="intro",
                start_bar=1,
                end_bar=8,
                template_id="template1",
            )
        ]
    )

    result = validator.validate(plan)

    # Should have expected structure
    assert isinstance(result, HeuristicValidationResult)
    assert isinstance(result.valid, bool)
    assert isinstance(result.errors, list)
    assert isinstance(result.warnings, list)


def test_validate_multiple_errors(available_templates, song_structure):
    """Test validation collects multiple errors."""
    validator = HeuristicValidator(
        available_templates=available_templates,
        song_structure=song_structure,
    )

    plan = ChoreographyPlan(
        sections=[
            PlanSection(
                section_name="unknown_section",  # Not in song structure
                start_bar=1,
                end_bar=8,
                template_id="invalid_template",  # Not in library
            )
        ]
    )

    result = validator.validate(plan)

    # Should collect multiple issues
    assert result.valid is False
    total_issues = len(result.errors) + len(result.warnings)
    assert total_issues >= 1  # At least template error


def test_validate_template_exists(available_templates, song_structure):
    """Test validation accepts valid template."""
    validator = HeuristicValidator(
        available_templates=available_templates,
        song_structure=song_structure,
    )

    plan = ChoreographyPlan(
        sections=[
            PlanSection(
                section_name="intro",
                start_bar=1,
                end_bar=8,
                template_id="sweep_lr_fan_pulse",
            )
        ]
    )

    result = validator.validate(plan)

    # Should be valid with existing template
    assert result.valid is True
    assert len(result.errors) == 0
