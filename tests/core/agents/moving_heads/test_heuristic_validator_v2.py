"""Tests for v2 heuristic validator for template-driven paradigm.

The v2 validator checks LLMChoreographyPlan (template_id + preset_id selection)
rather than the old AgentPlan with complex layering.
"""


from blinkb0t.core.agents.moving_heads.models_llm_plan import (
    LLMChoreographyPlan,
    SectionSelection,
)


def create_test_plan(
    sections: list[dict] | None = None,
    overall_strategy: str = "Test strategy",
) -> LLMChoreographyPlan:
    """Create a test plan with default values."""
    if sections is None:
        sections = [
            {
                "section_name": "verse_1",
                "start_bar": 1,
                "end_bar": 16,
                "template_id": "fan_pulse",
            }
        ]

    section_selections = [SectionSelection(**s) for s in sections]
    return LLMChoreographyPlan(sections=section_selections, overall_strategy=overall_strategy)


def create_test_template_metadata() -> list[dict]:
    """Create test template metadata."""
    return [
        {
            "template_id": "fan_pulse",
            "name": "Fan Pulse",
            "category": "movement",
            "energy_range": (60, 100),
            "presets": [
                {"preset_id": "CHILL", "name": "Chill"},
                {"preset_id": "PEAK", "name": "Peak"},
            ],
        },
        {
            "template_id": "gentle_sweep",
            "name": "Gentle Sweep",
            "category": "ambient",
            "energy_range": (0, 50),
            "presets": [
                {"preset_id": "SMOOTH", "name": "Smooth"},
            ],
        },
        {
            "template_id": "static_hold",
            "name": "Static Hold",
            "category": "static",
            "energy_range": (0, 100),
            "presets": [],
        },
    ]


def create_test_song_features(bar_count: int = 64) -> dict:
    """Create test song features."""
    return {
        "bars_s": [i * 2.0 for i in range(bar_count)],  # 2 seconds per bar
        "tempo_bpm": 120,
        "duration_s": bar_count * 2.0,
    }


class TestLLMPlanValidator:
    """Test cases for LLMPlanValidator."""

    def test_valid_plan_passes(self) -> None:
        """Test that a valid plan passes validation."""
        from blinkb0t.core.agents.moving_heads.heuristic_validator_v2 import LLMPlanValidator

        plan = create_test_plan(
            sections=[
                {
                    "section_name": "verse_1",
                    "start_bar": 1,
                    "end_bar": 32,
                    "template_id": "fan_pulse",
                },
                {
                    "section_name": "chorus_1",
                    "start_bar": 33,
                    "end_bar": 64,
                    "template_id": "gentle_sweep",
                },
            ]
        )
        validator = LLMPlanValidator(
            template_metadata=create_test_template_metadata(),
            song_features=create_test_song_features(64),
        )

        result = validator.validate(plan)
        assert result.passed

    def test_invalid_template_id_fails(self) -> None:
        """Test that invalid template_id fails validation."""
        from blinkb0t.core.agents.moving_heads.heuristic_validator_v2 import LLMPlanValidator

        plan = create_test_plan(
            sections=[
                {
                    "section_name": "verse_1",
                    "start_bar": 1,
                    "end_bar": 64,
                    "template_id": "nonexistent_template",
                },
            ]
        )
        validator = LLMPlanValidator(
            template_metadata=create_test_template_metadata(),
            song_features=create_test_song_features(64),
        )

        result = validator.validate(plan)
        assert not result.passed
        assert result.error_count > 0
        assert any("template" in issue.rule.lower() for issue in result.issues)

    def test_invalid_preset_id_fails(self) -> None:
        """Test that invalid preset_id fails validation."""
        from blinkb0t.core.agents.moving_heads.heuristic_validator_v2 import LLMPlanValidator

        plan = create_test_plan(
            sections=[
                {
                    "section_name": "verse_1",
                    "start_bar": 1,
                    "end_bar": 64,
                    "template_id": "fan_pulse",
                    "preset_id": "NONEXISTENT",
                },
            ]
        )
        validator = LLMPlanValidator(
            template_metadata=create_test_template_metadata(),
            song_features=create_test_song_features(64),
        )

        result = validator.validate(plan)
        assert not result.passed
        assert any("preset" in issue.rule.lower() for issue in result.issues)

    def test_valid_preset_passes(self) -> None:
        """Test that valid preset_id passes validation."""
        from blinkb0t.core.agents.moving_heads.heuristic_validator_v2 import LLMPlanValidator

        plan = create_test_plan(
            sections=[
                {
                    "section_name": "verse_1",
                    "start_bar": 1,
                    "end_bar": 64,
                    "template_id": "fan_pulse",
                    "preset_id": "CHILL",
                },
            ]
        )
        validator = LLMPlanValidator(
            template_metadata=create_test_template_metadata(),
            song_features=create_test_song_features(64),
        )

        result = validator.validate(plan)
        assert result.passed


class TestTimingValidation:
    """Test cases for timing validation."""

    def test_gap_in_coverage_warns(self) -> None:
        """Test that gaps between sections generate warnings."""
        from blinkb0t.core.agents.moving_heads.heuristic_validator_v2 import LLMPlanValidator

        plan = create_test_plan(
            sections=[
                {
                    "section_name": "verse_1",
                    "start_bar": 1,
                    "end_bar": 16,
                    "template_id": "fan_pulse",
                },
                # Gap: bars 17-32 missing
                {
                    "section_name": "chorus_1",
                    "start_bar": 33,
                    "end_bar": 64,
                    "template_id": "fan_pulse",
                },
            ]
        )
        validator = LLMPlanValidator(
            template_metadata=create_test_template_metadata(),
            song_features=create_test_song_features(64),
        )

        result = validator.validate(plan)
        assert any("gap" in issue.message.lower() for issue in result.issues)

    def test_first_section_must_start_at_bar_1(self) -> None:
        """Test that first section must start at bar 1."""
        from blinkb0t.core.agents.moving_heads.heuristic_validator_v2 import LLMPlanValidator

        plan = create_test_plan(
            sections=[
                {
                    "section_name": "verse_1",
                    "start_bar": 5,
                    "end_bar": 64,
                    "template_id": "fan_pulse",
                },
            ]
        )
        validator = LLMPlanValidator(
            template_metadata=create_test_template_metadata(),
            song_features=create_test_song_features(64),
        )

        result = validator.validate(plan)
        assert not result.passed
        assert any(
            "bar 1" in issue.message.lower() or "start" in issue.message.lower()
            for issue in result.issues
        )

    def test_coverage_warning_if_song_not_fully_covered(self) -> None:
        """Test warning when song is not fully covered."""
        from blinkb0t.core.agents.moving_heads.heuristic_validator_v2 import LLMPlanValidator

        plan = create_test_plan(
            sections=[
                {
                    "section_name": "verse_1",
                    "start_bar": 1,
                    "end_bar": 32,
                    "template_id": "fan_pulse",
                },
                # Missing bars 33-64
            ]
        )
        validator = LLMPlanValidator(
            template_metadata=create_test_template_metadata(),
            song_features=create_test_song_features(64),
        )

        result = validator.validate(plan)
        assert any("coverage" in issue.rule.lower() for issue in result.issues)


class TestEnergyValidation:
    """Test cases for energy alignment validation."""

    def test_energy_mismatch_warns(self) -> None:
        """Test that energy mismatch generates warning."""
        from blinkb0t.core.agents.moving_heads.heuristic_validator_v2 import LLMPlanValidator

        plan = create_test_plan(
            sections=[
                {
                    "section_name": "verse_1",
                    "start_bar": 1,
                    "end_bar": 64,
                    "template_id": "fan_pulse",  # energy_range (60, 100)
                    "energy_level": 20,  # Low energy - mismatch!
                },
            ]
        )
        validator = LLMPlanValidator(
            template_metadata=create_test_template_metadata(),
            song_features=create_test_song_features(64),
        )

        result = validator.validate(plan)
        assert any("energy" in issue.rule.lower() for issue in result.issues)

    def test_energy_match_passes(self) -> None:
        """Test that matching energy passes."""
        from blinkb0t.core.agents.moving_heads.heuristic_validator_v2 import LLMPlanValidator

        plan = create_test_plan(
            sections=[
                {
                    "section_name": "verse_1",
                    "start_bar": 1,
                    "end_bar": 64,
                    "template_id": "fan_pulse",  # energy_range (60, 100)
                    "energy_level": 80,  # High energy - matches!
                },
            ]
        )
        validator = LLMPlanValidator(
            template_metadata=create_test_template_metadata(),
            song_features=create_test_song_features(64),
        )

        result = validator.validate(plan)
        energy_issues = [i for i in result.issues if "energy" in i.rule.lower()]
        assert len(energy_issues) == 0


class TestVarietyValidation:
    """Test cases for template variety validation."""

    def test_repeated_template_warns(self) -> None:
        """Test that repeated templates in consecutive sections warn."""
        from blinkb0t.core.agents.moving_heads.heuristic_validator_v2 import LLMPlanValidator

        plan = create_test_plan(
            sections=[
                {
                    "section_name": "verse_1",
                    "start_bar": 1,
                    "end_bar": 16,
                    "template_id": "fan_pulse",
                },
                {
                    "section_name": "verse_2",
                    "start_bar": 17,
                    "end_bar": 32,
                    "template_id": "fan_pulse",
                },
                {
                    "section_name": "verse_3",
                    "start_bar": 33,
                    "end_bar": 48,
                    "template_id": "fan_pulse",
                },
                {
                    "section_name": "verse_4",
                    "start_bar": 49,
                    "end_bar": 64,
                    "template_id": "fan_pulse",
                },
            ]
        )
        validator = LLMPlanValidator(
            template_metadata=create_test_template_metadata(),
            song_features=create_test_song_features(64),
        )

        result = validator.validate(plan)
        assert any("variety" in issue.rule.lower() for issue in result.issues)

    def test_varied_templates_passes(self) -> None:
        """Test that varied templates pass variety check."""
        from blinkb0t.core.agents.moving_heads.heuristic_validator_v2 import LLMPlanValidator

        plan = create_test_plan(
            sections=[
                {
                    "section_name": "verse_1",
                    "start_bar": 1,
                    "end_bar": 16,
                    "template_id": "gentle_sweep",
                },
                {
                    "section_name": "chorus_1",
                    "start_bar": 17,
                    "end_bar": 32,
                    "template_id": "fan_pulse",
                },
                {
                    "section_name": "verse_2",
                    "start_bar": 33,
                    "end_bar": 48,
                    "template_id": "static_hold",
                },
                {
                    "section_name": "chorus_2",
                    "start_bar": 49,
                    "end_bar": 64,
                    "template_id": "fan_pulse",
                },
            ]
        )
        validator = LLMPlanValidator(
            template_metadata=create_test_template_metadata(),
            song_features=create_test_song_features(64),
        )

        result = validator.validate(plan)
        # Should pass with good variety
        assert result.passed


class TestValidationResult:
    """Test ValidationResult helper methods."""

    def test_error_summary_format(self) -> None:
        """Test error summary formatting."""
        from blinkb0t.core.agents.moving_heads.heuristic_validator_v2 import (
            LLMPlanValidator,
        )

        plan = create_test_plan(
            sections=[
                {
                    "section_name": "verse_1",
                    "start_bar": 1,
                    "end_bar": 64,
                    "template_id": "nonexistent",
                },
            ]
        )
        validator = LLMPlanValidator(
            template_metadata=create_test_template_metadata(),
            song_features=create_test_song_features(64),
        )

        result = validator.validate(plan)
        summary = result.get_error_summary()

        assert "error" in summary.lower() or "issue" in summary.lower()
