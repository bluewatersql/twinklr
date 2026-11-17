"""Tests for heuristic validator."""

import pytest

from tests.support.moving_heads import plan_section
from twinklr.core.agents.sequencer.moving_heads.heuristic_validator import (
    HeuristicValidationResult,
    HeuristicValidator,
)
from twinklr.core.agents.sequencer.moving_heads.models import (
    ChoreographyPlan,
)


@pytest.fixture
def available_templates():
    """List of available templates."""
    return ["sweep_lr_fan_pulse", "circle_fan_hold", "pendulum_chevron_breathe"]


@pytest.fixture
def song_structure():
    """Sample song structure, as `MovingHeadPlanningContext.for_prompt` gives it:
    inclusive bars, keyed by section id."""
    return {
        "sections": [
            {"section_id": "intro", "name": "intro", "start_bar": 1, "end_bar": 8},
            {"section_id": "verse", "name": "verse", "start_bar": 9, "end_bar": 24},
            {"section_id": "chorus", "name": "chorus", "start_bar": 25, "end_bar": 40},
        ],
        "total_bars": 40,
    }


REASON = "Answers the section's energy with a fitting template and colour."
STRATEGY = "The heads follow the song's energy arc and answer its lyric hooks."


def _section(*args, **fields):
    """`plan_section` with a reason, as the validator requires."""
    return plan_section(*args, **{"reasoning": REASON, **fields})


def _rest_of_song() -> list:
    """The verse and chorus of the `song_structure` fixture, planned."""
    return [
        _section("verse", 9, 24, "circle_fan_hold"),
        _section("chorus", 25, 40, "pendulum_chevron_breathe"),
    ]


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
        sections=[_section("intro", 1, 8, "sweep_lr_fan_pulse"), *_rest_of_song()],
        overall_strategy=STRATEGY,
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
        sections=[_section("intro", 1, 8, "nonexistent_template")], overall_strategy=STRATEGY
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
        sections=[_section("intro", 1, 8, "template1")], overall_strategy=STRATEGY
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
        sections=[_section("intro", 1, 12, "sweep_lr_fan_pulse")], overall_strategy=STRATEGY
    )

    result = validator.validate(plan)

    # A section's bars are the song structure's: a mismatch is an error.
    assert "Section 'intro' end_bar (12) doesn't match song structure (8)" in result.errors


def test_validate_negative_timing():
    """Test validation catches negative or invalid timing."""
    _validator = HeuristicValidator(
        available_templates=["template1"],
        song_structure={"sections": {"intro": {"start_bar": 1, "end_bar": 8}}, "total_bars": 32},
    )

    # This should fail Pydantic validation before reaching heuristic validator
    with pytest.raises(Exception):  # noqa: B017
        _section("intro", 8, 1, "template1")


def test_validate_incomplete_coverage(available_templates, song_structure):
    """Test validation detects incomplete coverage."""
    validator = HeuristicValidator(
        available_templates=available_templates,
        song_structure=song_structure,
    )

    # Only covers intro, missing verse and chorus
    plan = ChoreographyPlan(
        sections=[_section("intro", 1, 8, "sweep_lr_fan_pulse")], overall_strategy=STRATEGY
    )

    result = validator.validate(plan)

    # Every song section must be planned: the missing ones are an error naming them.
    assert not result.valid
    assert result.errors == [
        "The plan has no section for song section(s) 'verse' (bars 9-24), 'chorus' "
        "(bars 25-40); plan every section of the Song Structure table, each over its own bars"
    ]


def test_validate_result_structure():
    """Test validation result structure."""
    validator = HeuristicValidator(
        available_templates=["template1"],
        song_structure={"sections": {"intro": {"start_bar": 1, "end_bar": 8}}, "total_bars": 8},
    )

    plan = ChoreographyPlan(
        sections=[_section("intro", 1, 8, "template1")], overall_strategy=STRATEGY
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
        sections=[_section("unknown_section", 1, 8, "invalid_template")], overall_strategy=STRATEGY
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
        sections=[_section("intro", 1, 8, "sweep_lr_fan_pulse"), *_rest_of_song()],
        overall_strategy=STRATEGY,
    )

    result = validator.validate(plan)

    # Should be valid with existing template
    assert result.valid is True
    assert len(result.errors) == 0


def _two_parts(second_template: str):
    return _section(
        "intro",
        1,
        8,
        "sweep_lr_fan_pulse",
        parts=[
            {
                "start_bar": 1,
                "template_id": "sweep_lr_fan_pulse",
                "preset_id": None,
                "modifiers": [],
                "label": None,
                "reasoning": "",
            },
            {
                "start_bar": 5,
                "template_id": second_template,
                "preset_id": None,
                "modifiers": [],
                "label": None,
                "reasoning": "",
            },
        ],
    )


def test_every_part_must_name_an_offered_template(available_templates, song_structure):
    """Each part is checked against the library and located by its derived id."""
    validator = HeuristicValidator(
        available_templates=available_templates,
        song_structure=song_structure,
    )

    good = validator.validate(
        ChoreographyPlan(
            sections=[_two_parts("circle_fan_hold"), *_rest_of_song()], overall_strategy=STRATEGY
        )
    )
    bad = validator.validate(
        ChoreographyPlan(
            sections=[_two_parts("not_offered"), *_rest_of_song()], overall_strategy=STRATEGY
        )
    )

    assert good.valid and good.errors == []
    assert not bad.valid
    assert bad.errors == ["Section 'intro|B': template 'not_offered' not in library"]


def test_parts_are_units_for_cross_section_overlap(available_templates, song_structure):
    """A section overlapping a later part of another section is named by that part."""
    validator = HeuristicValidator(
        available_templates=available_templates,
        song_structure=song_structure,
    )
    plan = ChoreographyPlan(
        sections=[_two_parts("circle_fan_hold"), _section("verse", 8, 24, "circle_fan_hold")],
        overall_strategy=STRATEGY,
    )

    result = validator.validate(plan)

    assert any("'intro|B' (5-8) overlaps 'verse' (8-24)" in error for error in result.errors)


# =============================================================================
# V2 Interface Tests
# =============================================================================


class TestHeuristicValidatorV2:
    """Tests for V2 interface (from_context and create_validator_function)."""

    @pytest.fixture
    def planning_context(self):
        """Create a MovingHeadPlanningContext for testing."""
        from twinklr.core.agents.audio.profile.models import (
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
                    EnergyPoint(t_ms=sec.start_ms),
                    EnergyPoint(t_ms=(sec.start_ms + sec.end_ms) // 2),
                    EnergyPoint(t_ms=sec.end_ms - 1),
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

        plan = _context_plan(planning_context, "sweep_lr_fan_pulse")

        result = validator.validate(plan)

        assert result.valid is True
        assert len(result.errors) == 0

    def test_from_context_detects_invalid_template(self, planning_context):
        """Test validator from_context detects invalid templates."""
        validator = HeuristicValidator.from_context(planning_context)

        plan = ChoreographyPlan(
            sections=[_section("intro", 1, 15, "nonexistent_template")], overall_strategy=STRATEGY
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
        valid_plan = _context_plan(planning_context, "sweep_lr_fan_pulse")

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
            sections=[_section("intro", 1, 15, "invalid_template_xyz")], overall_strategy=STRATEGY
        )

        errors = validator_fn(invalid_plan)

        assert isinstance(errors, list)
        assert len(errors) > 0
        assert any("invalid_template_xyz" in err for err in errors)


def _context_plan(context, template_id: str) -> ChoreographyPlan:
    """Every section of `context`'s song structure, planned over its own bars."""
    return ChoreographyPlan(
        sections=[
            _section(entry["section_id"], entry["start_bar"], entry["end_bar"], template_id)
            for entry in context.for_prompt()["song_structure"]["sections"]
        ],
        overall_strategy=STRATEGY,
    )


def test_a_placeholder_reasoning_or_strategy_is_an_error(available_templates, song_structure):
    validator = HeuristicValidator(
        available_templates=available_templates, song_structure=song_structure
    )
    plan = ChoreographyPlan(
        sections=[
            _section("intro", 1, 8, "sweep_lr_fan_pulse", reasoning="x"),
            *_rest_of_song(),
        ],
        overall_strategy="x",
    )

    errors = validator.validate(plan).errors

    assert any("Section 'intro': reasoning 'x' is a placeholder" in e for e in errors)
    assert any("overall_strategy 'x' is a placeholder" in e for e in errors)


def test_a_section_shorter_than_a_bar_is_not_required(available_templates):
    """It shares its start bar with the next section; planning both would overlap."""
    structure = {
        "sections": [
            {"section_id": "intro", "start_bar": 1, "end_bar": 8},
            {"section_id": "pickup", "start_bar": 9, "end_bar": 9},
            {"section_id": "verse", "start_bar": 9, "end_bar": 16},
        ],
        "total_bars": 16,
    }
    validator = HeuristicValidator(
        available_templates=available_templates, song_structure=structure
    )
    plan = ChoreographyPlan(
        sections=[
            _section("intro", 1, 8, "sweep_lr_fan_pulse"),
            _section("verse", 9, 16, "circle_fan_hold"),
        ],
        overall_strategy=STRATEGY,
    )

    assert validator.validate(plan).errors == []


class TestGridShorterThanTheSong:
    """The 2026-11-17 failed run: the table ran past `total_bars`, so following it
    and clamping it were both errors. The table is now clamped to the grid."""

    @staticmethod
    def _plan(*bars: tuple[str, int, int]) -> ChoreographyPlan:
        return ChoreographyPlan(
            sections=[_section(name, start, end, "sweep_lr_fan_hold") for name, start, end in bars],
            overall_strategy=STRATEGY,
        )

    def test_a_plan_following_the_table_is_clean(self) -> None:
        from tests.unit.agents.sequencer.moving_heads.test_context_grid import (
            DANCE_GRID_BARS,
            DANCE_SONG,
            SHORT_GRID_BARS,
            SHORT_GRID_SONG,
            short_grid_context,
        )

        for bars, song in ((SHORT_GRID_BARS, SHORT_GRID_SONG), (DANCE_GRID_BARS, DANCE_SONG)):
            context = short_grid_context(bars, song)
            table = context.song_structure()["sections"]
            plan = self._plan(*((s["section_id"], s["start_bar"], s["end_bar"]) for s in table))
            assert HeuristicValidator.from_context(context).validate(plan).errors == []

    def test_the_failed_runs_iteration_1_plan_is_an_error(self) -> None:
        """It followed the old table: chorus_2 to bar 63, verse_3 at bar 64."""
        from tests.unit.agents.sequencer.moving_heads.test_context_grid import (
            short_grid_context,
        )

        context = short_grid_context()
        head = [("intro", 1, 10), ("verse_1", 11, 20), ("verse_2", 21, 31)]
        head += [("chorus_1", 32, 42), ("break", 43, 52)]
        errors = (
            HeuristicValidator.from_context(context)
            .validate(self._plan(*head, ("chorus_2", 53, 63), ("verse_3", 64, 64)))
            .errors
        )

        assert "Unit 'chorus_2' ends at bar 63, beyond total_bars (61)" in errors
        assert "Section 'chorus_2' end_bar (63) doesn't match song structure (61)" in errors
        assert (
            "Section 'verse_3' lies beyond the detected beat grid (its last bar is 61); "
            "leave it out of the plan"
        ) in errors

    def test_the_failed_runs_iteration_2_plan_is_clean_once_it_matches_the_table(self) -> None:
        """Iteration 2 clamped into the grid (chorus_2 53-60, verse_3 61); against the
        corrected table chorus_2 runs to bar 61 and verse_3 is not planned."""
        from tests.unit.agents.sequencer.moving_heads.test_context_grid import (
            short_grid_context,
        )

        validator = HeuristicValidator.from_context(short_grid_context())
        head = [("intro", 1, 10), ("verse_1", 11, 20), ("verse_2", 21, 31)]
        head += [("chorus_1", 32, 42), ("break", 43, 52)]

        as_sent = validator.validate(self._plan(*head, ("chorus_2", 53, 60), ("verse_3", 61, 61)))
        matching = validator.validate(self._plan(*head, ("chorus_2", 53, 61)))

        assert "Section 'chorus_2' end_bar (60) doesn't match song structure (61)" in as_sent.errors
        assert matching.errors == []
