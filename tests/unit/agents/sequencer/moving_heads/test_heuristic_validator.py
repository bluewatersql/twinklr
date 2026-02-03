"""Tests for heuristic validator."""

import pytest

from twinklr.core.agents.sequencer.moving_heads.heuristic_validator import (
    HeuristicValidationResult,
    HeuristicValidator,
)
from twinklr.core.agents.sequencer.moving_heads.models import (
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


def test_validate_segments_null_accepted(available_templates, song_structure):
    """Test that segments: null is accepted as equivalent to omitting segments."""
    validator = HeuristicValidator(
        available_templates=available_templates,
        song_structure=song_structure,
    )

    # Create a plan with segments explicitly set to None (null in JSON)
    plan = ChoreographyPlan(
        sections=[
            PlanSection(
                section_name="intro",
                start_bar=1,
                end_bar=8,
                template_id="sweep_lr_fan_pulse",
                segments=None,  # Explicitly set to None (null in JSON)
            ),
            PlanSection(
                section_name="verse",
                start_bar=9,
                end_bar=24,
                template_id="circle_fan_hold",
                segments=None,  # Explicitly set to None
            ),
        ]
    )

    result = validator.validate(plan)

    # Should be valid - segments: null is treated the same as omitting segments
    assert result.valid is True
    assert len(result.errors) == 0


# =============================================================================
# V2 Interface Tests
# =============================================================================


class TestHeuristicValidatorV2:
    """Tests for V2 interface (from_context and create_validator_function)."""

    @pytest.fixture
    def planning_context(self):
        """Create a MovingHeadPlanningContext for testing."""
        from twinklr.core.agents.audio.profile.models import (
            AssetUsage,
            AudioProfileModel,
            Contrast,
            CreativeGuidance,
            EnergyPoint,
            EnergyProfile,
            LyricProfile,
            MacroEnergy,
            MotionDensity,
            PlannerHints,
            SectionEnergyProfile,
            SongIdentity,
            SongSectionRef,
            Structure,
        )
        from twinklr.core.agents.sequencer.moving_heads.context import (
            FixtureContext,
            MovingHeadPlanningContext,
        )

        song_identity = SongIdentity(
            title="Test Song",
            duration_ms=120000,
            bpm=120.0,
            time_signature="4/4",
        )

        sections = [
            SongSectionRef(section_id="intro", name="intro", start_ms=0, end_ms=30000),
            SongSectionRef(section_id="verse_1", name="verse", start_ms=30000, end_ms=60000),
            SongSectionRef(section_id="chorus_1", name="chorus", start_ms=60000, end_ms=90000),
            SongSectionRef(section_id="outro", name="outro", start_ms=90000, end_ms=120000),
        ]

        structure = Structure(sections=sections, structure_confidence=0.9)

        # Create minimal section energy profiles
        section_profiles = [
            SectionEnergyProfile(
                section_id=sec.section_id,
                start_ms=sec.start_ms,
                end_ms=sec.end_ms,
                energy_curve=[
                    EnergyPoint(t_ms=sec.start_ms, energy_0_1=0.5),
                    EnergyPoint(t_ms=(sec.start_ms + sec.end_ms) // 2, energy_0_1=0.6),
                    EnergyPoint(t_ms=sec.end_ms - 1, energy_0_1=0.5),
                ],
                mean_energy=0.55,
                peak_energy=0.6,
            )
            for sec in sections
        ]

        energy_profile = EnergyProfile(
            macro_energy=MacroEnergy.MED,
            section_profiles=section_profiles,
            peaks=[],
            overall_mean=0.5,
            energy_confidence=0.8,
        )

        lyric_profile = LyricProfile(
            has_plain_lyrics=False,
            has_timed_words=False,
            has_phonemes=False,
            lyric_confidence=0.0,
            phoneme_confidence=0.0,
        )

        creative_guidance = CreativeGuidance(
            recommended_layer_count=2,
            recommended_contrast=Contrast.MED,
            recommended_motion_density=MotionDensity.MED,
            recommended_asset_usage=AssetUsage.SPARSE,
        )

        planner_hints = PlannerHints()

        audio_profile = AudioProfileModel(
            song_identity=song_identity,
            structure=structure,
            energy_profile=energy_profile,
            lyric_profile=lyric_profile,
            creative_guidance=creative_guidance,
            planner_hints=planner_hints,
        )

        return MovingHeadPlanningContext(
            audio_profile=audio_profile,
            fixtures=FixtureContext(count=4, groups=[]),
            available_templates=[
                "sweep_lr_fan_pulse",
                "circle_fan_hold",
                "pendulum_chevron_breathe",
            ],
        )

    def test_from_context_creates_validator(self, planning_context):
        """Test from_context class method creates valid validator."""
        validator = HeuristicValidator.from_context(planning_context)

        assert validator is not None
        assert "sweep_lr_fan_pulse" in validator.available_templates
        assert "circle_fan_hold" in validator.available_templates

    def test_from_context_validates_plan(self, planning_context):
        """Test validator from_context can validate plans."""
        validator = HeuristicValidator.from_context(planning_context)

        plan = ChoreographyPlan(
            sections=[
                PlanSection(
                    section_name="intro",
                    start_bar=1,
                    end_bar=15,
                    template_id="sweep_lr_fan_pulse",
                )
            ]
        )

        result = validator.validate(plan)

        assert result.valid is True
        assert len(result.errors) == 0

    def test_from_context_detects_invalid_template(self, planning_context):
        """Test validator from_context detects invalid templates."""
        validator = HeuristicValidator.from_context(planning_context)

        plan = ChoreographyPlan(
            sections=[
                PlanSection(
                    section_name="intro",
                    start_bar=1,
                    end_bar=15,
                    template_id="nonexistent_template",
                )
            ]
        )

        result = validator.validate(plan)

        assert result.valid is False
        assert any("nonexistent_template" in err for err in result.errors)

    def test_create_validator_function(self, planning_context):
        """Test create_validator_function factory."""
        from twinklr.core.agents.sequencer.moving_heads.heuristic_validator import (
            create_validator_function,
        )

        validator_fn = create_validator_function(planning_context)

        # Should be callable
        assert callable(validator_fn)

    def test_create_validator_function_returns_errors_only(self, planning_context):
        """Test validator function returns only errors, not warnings."""
        from twinklr.core.agents.sequencer.moving_heads.heuristic_validator import (
            create_validator_function,
        )

        validator_fn = create_validator_function(planning_context)

        # Valid plan
        valid_plan = ChoreographyPlan(
            sections=[
                PlanSection(
                    section_name="intro",
                    start_bar=1,
                    end_bar=15,
                    template_id="sweep_lr_fan_pulse",
                )
            ]
        )

        errors = validator_fn(valid_plan)

        assert isinstance(errors, list)
        assert len(errors) == 0  # No errors for valid plan

    def test_create_validator_function_captures_errors(self, planning_context):
        """Test validator function captures errors correctly."""
        from twinklr.core.agents.sequencer.moving_heads.heuristic_validator import (
            create_validator_function,
        )

        validator_fn = create_validator_function(planning_context)

        # Invalid plan with unknown template
        invalid_plan = ChoreographyPlan(
            sections=[
                PlanSection(
                    section_name="intro",
                    start_bar=1,
                    end_bar=15,
                    template_id="invalid_template_xyz",
                )
            ]
        )

        errors = validator_fn(invalid_plan)

        assert isinstance(errors, list)
        assert len(errors) > 0
        assert any("invalid_template_xyz" in err for err in errors)
