"""Tests for HeuristicValidator."""

from __future__ import annotations

import pytest

from blinkb0t.core.agents.moving_heads import (
    HeuristicValidator,
    Severity,
    ValidationResult,
)
from blinkb0t.core.agents.moving_heads.models_agent_plan import AgentPlan, SectionPlan


@pytest.fixture
def mock_template_metadata() -> list[dict]:
    """Mock template metadata."""
    return [
        {
            "template_id": "gentle_sweep_breathe",
            "metadata": {
                "name": "Gentle Sweep & Breathe",
                "description": "Soft sweeping with breathing dim",
                "energy_range": [10, 40],
                "recommended_sections": ["verse", "intro"],
                "tags": ["gentle", "sweep", "breathe"],
            },
            "step_count": 8,
        },
        {
            "template_id": "energetic_fan_pulse",
            "metadata": {
                "name": "Energetic Fan Pulse",
                "description": "Fast fan movements with pulsing",
                "energy_range": [70, 100],
                "recommended_sections": ["chorus", "climax"],
                "tags": ["energetic", "fan", "pulse"],
            },
            "step_count": 16,
        },
    ]


@pytest.fixture
def mock_song_features() -> dict:
    """Mock song features with 32 bars."""
    return {
        "bars_s": [i * 2.0 for i in range(32)],  # 32 bars
        "tempo_bpm": 120,
        "time_signature": "4/4",
    }


@pytest.fixture
def validator(mock_template_metadata: list[dict], mock_song_features: dict) -> HeuristicValidator:
    """Create HeuristicValidator instance."""
    return HeuristicValidator(
        template_metadata=mock_template_metadata, song_features=mock_song_features
    )


@pytest.fixture
def valid_plan() -> AgentPlan:
    """Create valid plan."""
    return AgentPlan(
        sections=[
            SectionPlan(
                name="verse_1",
                start_bar=1,
                end_bar=16,
                section_role="verse",
                energy_level=30,
                templates=["gentle_sweep_breathe"],
                params={"intensity": "SMOOTH"},
                base_pose="AUDIENCE_CENTER",
                reasoning="Test",
            ),
            SectionPlan(
                name="chorus_1",
                start_bar=17,
                end_bar=32,
                section_role="chorus",
                energy_level=85,
                templates=["energetic_fan_pulse"],
                params={"intensity": "DRAMATIC"},
                base_pose="AUDIENCE_CENTER",
                reasoning="Test",
            ),
        ],
        overall_strategy="Test strategy",
        template_variety_score=8,
        energy_alignment_score=9,
    )


class TestValidationResult:
    """Tests for ValidationResult."""

    def test_add_error(self):
        """Test adding error sets passed to False."""
        result = ValidationResult(passed=True)

        result.add_error("test_rule", "Test error", "test_section")

        assert not result.passed
        assert result.error_count == 1
        assert result.warning_count == 0
        assert len(result.issues) == 1
        assert result.issues[0].severity == Severity.ERROR
        assert result.issues[0].rule == "test_rule"

    def test_add_warning(self):
        """Test adding warning doesn't affect passed status."""
        result = ValidationResult(passed=True)

        result.add_warning("test_rule", "Test warning", "test_section")

        assert result.passed  # Still passed
        assert result.error_count == 0
        assert result.warning_count == 1
        assert len(result.issues) == 1
        assert result.issues[0].severity == Severity.WARNING

    def test_get_error_summary_no_issues(self):
        """Test error summary with no issues."""
        result = ValidationResult(passed=True)

        summary = result.get_error_summary()

        assert summary == "No issues"

    def test_get_error_summary_with_issues(self):
        """Test error summary with issues."""
        result = ValidationResult(passed=True)
        result.add_error("timing", "Gap detected", "verse_1")
        result.add_warning("energy", "Energy mismatch", "chorus_1")

        summary = result.get_error_summary()

        assert "1 errors, 1 warnings" in summary
        assert "❌ timing [verse_1]: Gap detected" in summary
        assert "⚠️ energy [chorus_1]: Energy mismatch" in summary


class TestHeuristicValidator:
    """Tests for HeuristicValidator."""

    def test_validate_valid_plan(self, validator: HeuristicValidator, valid_plan: AgentPlan):
        """Test validation of valid plan."""
        result = validator.validate(valid_plan)

        assert result.passed
        assert result.error_count == 0

    def test_detect_timing_gap(self, validator: HeuristicValidator, valid_plan: AgentPlan):
        """Test detection of timing gap."""
        # Create gap: section 1 ends at 16, section 2 starts at 20 (gap: 17-19)
        valid_plan.sections[1].start_bar = 20

        result = validator.validate(valid_plan)

        assert not result.passed
        assert result.error_count > 0
        assert any("Gap" in issue.message for issue in result.issues)
        assert any("3 bars" in issue.message for issue in result.issues)

    def test_detect_timing_overlap(self, validator: HeuristicValidator, valid_plan: AgentPlan):
        """Test detection of timing overlap."""
        # Create overlap: section 1 ends at 18, section 2 starts at 17
        valid_plan.sections[0].end_bar = 18

        result = validator.validate(valid_plan)

        # Overlaps are now ALLOWED (for layering) - just logged as info
        assert result.passed
        assert result.error_count == 0
        assert any(
            "overlap" in issue.message.lower() and issue.severity.value == "info"
            for issue in result.issues
        )

    def test_detect_negative_duration(self, validator: HeuristicValidator, valid_plan: AgentPlan):
        """Test detection of negative duration."""
        # Create negative duration
        valid_plan.sections[0].end_bar = 0  # start=1, end=0

        result = validator.validate(valid_plan)

        assert not result.passed
        assert any("Negative duration" in issue.message for issue in result.issues)

    def test_detect_first_section_not_starting_at_1(
        self, validator: HeuristicValidator, valid_plan: AgentPlan
    ):
        """Test detection of first section not starting at bar 1."""
        valid_plan.sections[0].start_bar = 5

        result = validator.validate(valid_plan)

        assert not result.passed
        assert any("should start at 1" in issue.message for issue in result.issues)

    def test_detect_invalid_template(self, validator: HeuristicValidator, valid_plan: AgentPlan):
        """Test detection of invalid template ID."""
        valid_plan.sections[0].templates = ["nonexistent_template"]

        result = validator.validate(valid_plan)

        assert not result.passed
        assert result.error_count > 0
        assert any("not found" in issue.message for issue in result.issues)

    def test_detect_invalid_pose(self, validator: HeuristicValidator, valid_plan: AgentPlan):
        """Test detection of invalid pose ID."""
        valid_plan.sections[0].base_pose = "INVALID_POSE"

        result = validator.validate(valid_plan)

        assert not result.passed
        assert result.error_count > 0
        assert any("Invalid pose" in issue.message for issue in result.issues)

    def test_detect_invalid_intensity(self, validator: HeuristicValidator, valid_plan: AgentPlan):
        """Test detection of invalid intensity parameter."""
        valid_plan.sections[0].params["intensity"] = "INVALID"

        result = validator.validate(valid_plan)

        assert not result.passed
        assert result.error_count > 0
        assert any("Invalid intensity" in issue.message for issue in result.issues)

    def test_detect_invalid_speed(self, validator: HeuristicValidator, valid_plan: AgentPlan):
        """Test detection of invalid speed parameter."""
        valid_plan.sections[0].params["speed"] = "INVALID_SPEED"

        result = validator.validate(valid_plan)

        assert not result.passed
        assert any("Invalid speed" in issue.message for issue in result.issues)

    def test_detect_invalid_scale(self, validator: HeuristicValidator, valid_plan: AgentPlan):
        """Test detection of invalid scale parameter."""
        valid_plan.sections[0].params["scale"] = "INVALID_SCALE"

        result = validator.validate(valid_plan)

        assert not result.passed
        assert any("Invalid scale" in issue.message for issue in result.issues)

    def test_valid_intensity_parameters(self, validator: HeuristicValidator, valid_plan: AgentPlan):
        """Test valid intensity parameters pass validation."""
        for intensity in ["SMOOTH", "DRAMATIC", "INTENSE"]:
            valid_plan.sections[0].params["intensity"] = intensity
            result = validator.validate(valid_plan)
            assert result.passed or result.error_count == 0

    def test_energy_mismatch_warning(self, validator: HeuristicValidator, valid_plan: AgentPlan):
        """Test energy mismatch generates warning."""
        # Set high energy for low-energy template (gentle_sweep_breathe: [10, 40])
        valid_plan.sections[0].energy_level = 95

        result = validator.validate(valid_plan)

        # Should pass but with warning
        assert result.passed  # Warnings don't fail validation
        assert result.warning_count > 0
        assert any("Energy mismatch" in issue.message for issue in result.issues)

    def test_energy_within_range_no_warning(
        self, validator: HeuristicValidator, valid_plan: AgentPlan
    ):
        """Test energy within range doesn't generate warning."""
        # Set energy within template range (gentle_sweep_breathe: [10, 40])
        valid_plan.sections[0].energy_level = 25

        result = validator.validate(valid_plan)

        # Check no energy warnings
        energy_issues = [issue for issue in result.issues if issue.rule == "energy"]
        assert len(energy_issues) == 0

    def test_coverage_warning_missing_bars(
        self, validator: HeuristicValidator, valid_plan: AgentPlan
    ):
        """Test coverage warning for missing bars."""
        # End at bar 20 instead of 32
        valid_plan.sections[1].end_bar = 20

        result = validator.validate(valid_plan)

        assert result.passed  # Warnings don't fail
        assert result.warning_count > 0
        assert any("not fully covered" in issue.message for issue in result.issues)
        assert any("12 bars" in issue.message for issue in result.issues)

    def test_coverage_warning_extends_beyond_song(
        self, validator: HeuristicValidator, valid_plan: AgentPlan
    ):
        """Test coverage warning when plan extends beyond song."""
        # Extend beyond 32 bars
        valid_plan.sections[1].end_bar = 40

        result = validator.validate(valid_plan)

        assert result.passed  # Warnings don't fail
        assert result.warning_count > 0
        assert any("beyond song end" in issue.message for issue in result.issues)
        assert any("8 bars" in issue.message for issue in result.issues)

    def test_variety_warning_consecutive_templates(
        self, validator: HeuristicValidator, valid_plan: AgentPlan
    ):
        """Test variety warning for consecutive same templates."""
        # Use same template for both sections
        valid_plan.sections[1].templates = ["gentle_sweep_breathe"]

        result = validator.validate(valid_plan)

        assert result.passed  # Warnings don't fail
        assert result.warning_count > 0
        assert any("repeated in consecutive sections" in issue.message for issue in result.issues)

    def test_variety_warning_low_variety(self, validator: HeuristicValidator):
        """Test variety warning for low overall variety."""
        # Create plan with 4 sections, all using same template
        plan = AgentPlan(
            sections=[
                SectionPlan(
                    name=f"section_{i}",
                    start_bar=i * 8 + 1,
                    end_bar=(i + 1) * 8,
                    section_role="verse",
                    energy_level=30,
                    templates=["gentle_sweep_breathe"],
                    params={"intensity": "SMOOTH"},
                    base_pose="AUDIENCE_CENTER",
                    reasoning="Test",
                )
                for i in range(4)
            ],
            overall_strategy="Test",
            template_variety_score=3,
            energy_alignment_score=9,
        )

        result = validator.validate(plan)

        assert result.passed  # Warnings don't fail
        assert result.warning_count > 0
        variety_issues = [
            issue for issue in result.issues if "Low template variety" in issue.message
        ]
        assert len(variety_issues) > 0

    def test_empty_plan(self, validator: HeuristicValidator):
        """Test validation of empty plan."""
        plan = AgentPlan(
            sections=[],
            overall_strategy="Empty",
            template_variety_score=0,
            energy_alignment_score=0,
        )

        result = validator.validate(plan)

        assert not result.passed
        assert result.error_count > 0
        assert any("No sections" in issue.message for issue in result.issues)

    def test_multiple_errors(self, validator: HeuristicValidator, valid_plan: AgentPlan):
        """Test plan with multiple validation errors."""
        # Introduce multiple errors
        valid_plan.sections[0].templates = ["nonexistent"]  # Invalid template
        valid_plan.sections[0].base_pose = "INVALID_POSE"  # Invalid pose
        valid_plan.sections[0].params["intensity"] = "INVALID"  # Invalid param
        valid_plan.sections[1].start_bar = 20  # Gap

        result = validator.validate(valid_plan)

        assert not result.passed
        assert result.error_count >= 4  # At least 4 errors

    def test_validation_with_warnings_only(
        self, validator: HeuristicValidator, valid_plan: AgentPlan
    ):
        """Test plan that passes but has warnings."""
        # Add energy mismatch (warning)
        valid_plan.sections[0].energy_level = 95
        # Add consecutive templates (warning)
        valid_plan.sections[1].templates = ["gentle_sweep_breathe"]

        result = validator.validate(valid_plan)

        assert result.passed  # Passes despite warnings
        assert result.error_count == 0
        assert result.warning_count > 0

    def test_sections_sorted_by_start_bar(
        self, validator: HeuristicValidator, valid_plan: AgentPlan
    ):
        """Test that sections are sorted by start_bar for validation."""
        # Reverse section order
        valid_plan.sections = valid_plan.sections[::-1]

        result = validator.validate(valid_plan)

        # Should still pass (internally sorted)
        assert result.passed
