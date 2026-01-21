"""Tests for template models."""

from pydantic import ValidationError
import pytest

from blinkb0t.core.domains.sequencing.models.templates import (
    BlendMode,
    FixtureTarget,
    PatternStep,
    PatternStepTiming,
    Template,
    TemplateCategory,
    TemplateMetadata,
    TemplateTiming,
    TransitionConfig,
    TransitionMode,
)
from blinkb0t.core.domains.sequencing.models.timing import MusicalTiming, TimingMode


class TestFixtureTarget:
    """Test FixtureTarget enum."""

    def test_fixture_targets(self):
        """Test all fixture target options."""
        assert FixtureTarget.ALL == "ALL"
        assert FixtureTarget.LEFT == "LEFT"
        assert FixtureTarget.RIGHT == "RIGHT"
        assert FixtureTarget.INNER == "INNER"
        assert FixtureTarget.OUTER == "OUTER"
        assert FixtureTarget.ODD == "ODD"
        assert FixtureTarget.EVEN == "EVEN"


class TestTransitionMode:
    """Test TransitionMode enum."""

    def test_transition_modes(self):
        """Test all transition modes."""
        assert TransitionMode.SNAP == "snap"
        assert TransitionMode.CROSSFADE == "crossfade"
        assert TransitionMode.FADE_THROUGH_BLACK == "fade_through_black"


class TestBlendMode:
    """Test BlendMode enum."""

    def test_blend_modes(self):
        """Test all blend modes."""
        assert BlendMode.OVERRIDE == "override"
        assert BlendMode.ADD == "add"
        assert BlendMode.MULTIPLY == "multiply"
        assert BlendMode.MAX == "max"


class TestTransitionConfig:
    """Test TransitionConfig model."""

    def test_snap_transition(self):
        """Test SNAP transition (instant)."""
        transition = TransitionConfig(mode=TransitionMode.SNAP)

        assert transition.mode == TransitionMode.SNAP
        assert transition.duration_bars == 0.0

    def test_crossfade_transition(self):
        """Test CROSSFADE transition."""
        transition = TransitionConfig(
            mode=TransitionMode.CROSSFADE, duration_bars=0.5, curve="EASE_IN_OUT"
        )

        assert transition.mode == TransitionMode.CROSSFADE
        assert transition.duration_bars == 0.5
        assert transition.curve == "EASE_IN_OUT"

    def test_snap_with_duration_fails(self):
        """Test that SNAP with duration > 0 fails."""
        with pytest.raises(ValidationError) as exc_info:
            TransitionConfig(mode=TransitionMode.SNAP, duration_bars=0.5)

        errors = exc_info.value.errors()
        assert any("SNAP" in str(e) for e in errors)

    def test_crossfade_without_duration_fails(self):
        """Test that CROSSFADE without duration fails."""
        with pytest.raises(ValidationError) as exc_info:
            TransitionConfig(mode=TransitionMode.CROSSFADE, duration_bars=0.0)

        errors = exc_info.value.errors()
        assert any("duration_bars" in str(e) for e in errors)


class TestPatternStepTiming:
    """Test PatternStepTiming model."""

    def test_simple_timing(self):
        """Test simple timing without loop or offsets."""
        timing = PatternStepTiming(
            base_timing=MusicalTiming(start_offset_bars=0.0, duration_bars=4.0)
        )

        assert timing.base_timing.start_offset_bars == 0.0
        assert timing.base_timing.duration_bars == 4.0
        assert timing.loop is False
        assert timing.per_fixture_offsets is None

    def test_looping_timing(self):
        """Test looping pattern timing."""
        timing = PatternStepTiming(
            base_timing=MusicalTiming(start_offset_bars=0.0, duration_bars=8.0), loop=True
        )

        assert timing.loop is True

    def test_per_fixture_offsets(self):
        """Test timing with per-fixture offsets (chase effect)."""
        timing = PatternStepTiming(
            base_timing=MusicalTiming(start_offset_bars=0.0, duration_bars=4.0),
            per_fixture_offsets=[0.0, 0.25, 0.5, 0.75],
        )

        assert timing.per_fixture_offsets == [0.0, 0.25, 0.5, 0.75]


class TestPatternStep:
    """Test PatternStep model."""

    def test_minimal_pattern_step(self):
        """Test creating minimal pattern step."""
        step = PatternStep(
            step_id="test_step",
            timing=PatternStepTiming(
                base_timing=MusicalTiming(start_offset_bars=0.0, duration_bars=2.0)
            ),
            movement_id="sweep_lr",
            dimmer_id="fade_in",
        )

        assert step.step_id == "test_step"
        assert step.target == "ALL"  # Default
        assert step.movement_id == "sweep_lr"
        assert step.dimmer_id == "fade_in"
        assert step.geometry_id is None

    def test_full_pattern_step(self):
        """Test pattern step with all fields."""
        step = PatternStep(
            step_id="full_step",
            target="LEFT",
            timing=PatternStepTiming(
                base_timing=MusicalTiming(start_offset_bars=0.0, duration_bars=4.0)
            ),
            movement_id="circle",
            geometry_id="fan",
            dimmer_id="pulse",
            movement_params={"intensity": "DRAMATIC"},
            geometry_params={"fan_width": 0.7},
            dimmer_params={"intensity": "INTENSE"},
            entry_transition=TransitionConfig(mode=TransitionMode.SNAP),
            exit_transition=TransitionConfig(mode=TransitionMode.CROSSFADE, duration_bars=0.5),
            priority=1,
            blend_mode=BlendMode.ADD,
        )

        assert step.target == "LEFT"
        assert step.geometry_id == "fan"
        assert step.movement_params["intensity"] == "DRAMATIC"
        assert step.priority == 1

    def test_negative_priority_fails(self):
        """Test that negative priority fails."""
        with pytest.raises(ValidationError):
            PatternStep(
                step_id="test",
                timing=PatternStepTiming(base_timing=MusicalTiming()),
                movement_id="sweep_lr",
                dimmer_id="fade_in",
                priority=-1,
            )


class TestTemplateCategory:
    """Test TemplateCategory enum."""

    def test_template_categories(self):
        """Test all template categories."""
        assert TemplateCategory.LOW_ENERGY == "low_energy"
        assert TemplateCategory.MEDIUM_ENERGY == "medium_energy"
        assert TemplateCategory.HIGH_ENERGY == "high_energy"
        assert TemplateCategory.BUILD == "build"
        assert TemplateCategory.BREAKDOWN == "breakdown"
        assert TemplateCategory.ACCENT == "accent"
        assert TemplateCategory.TRANSITION == "transition"
        assert TemplateCategory.AMBIENT == "ambient"


class TestTemplateMetadata:
    """Test TemplateMetadata model."""

    def test_metadata_with_all_fields(self):
        """Test metadata with all fields populated."""
        metadata = TemplateMetadata(
            description="Energetic fan sweep",
            recommended_sections=["chorus", "drop"],
            energy_range=(70, 100),
            tags=["energetic", "fan", "sweep"],
        )

        assert metadata.description == "Energetic fan sweep"
        assert metadata.recommended_sections == ["chorus", "drop"]
        assert metadata.energy_range == (70, 100)
        assert metadata.tags == ["energetic", "fan", "sweep"]


class TestTemplateTiming:
    """Test TemplateTiming model."""

    def test_default_template_timing(self):
        """Test default template timing."""
        timing = TemplateTiming()

        assert timing.mode == TimingMode.MUSICAL
        assert timing.default_duration_bars == 8.0

    def test_custom_duration(self):
        """Test custom default duration."""
        timing = TemplateTiming(default_duration_bars=16.0)

        assert timing.default_duration_bars == 16.0

    def test_zero_duration_fails(self):
        """Test that zero duration fails."""
        with pytest.raises(ValidationError):
            TemplateTiming(default_duration_bars=0.0)


class TestTemplate:
    """Test Template model."""

    def test_simple_template(self):
        """Test creating simple template with one step."""
        template = Template(
            template_id="test_template",
            name="Test Template",
            category=TemplateCategory.MEDIUM_ENERGY,
            steps=[
                PatternStep(
                    step_id="step1",
                    timing=PatternStepTiming(
                        base_timing=MusicalTiming(start_offset_bars=0.0, duration_bars=4.0)
                    ),
                    movement_id="sweep_lr",
                    dimmer_id="fade_in",
                )
            ],
        )

        assert template.template_id == "test_template"
        assert template.category == TemplateCategory.MEDIUM_ENERGY
        assert len(template.steps) == 1

    def test_multi_step_template(self):
        """Test template with multiple steps."""
        template = Template(
            template_id="multi_step",
            name="Multi-Step Template",
            category=TemplateCategory.HIGH_ENERGY,
            steps=[
                PatternStep(
                    step_id="intro",
                    timing=PatternStepTiming(
                        base_timing=MusicalTiming(start_offset_bars=0.0, duration_bars=2.0)
                    ),
                    movement_id="sweep_lr",
                    dimmer_id="fade_in",
                ),
                PatternStep(
                    step_id="main",
                    timing=PatternStepTiming(
                        base_timing=MusicalTiming(start_offset_bars=2.0, duration_bars=6.0)
                    ),
                    movement_id="circle",
                    dimmer_id="pulse",
                ),
            ],
        )

        assert len(template.steps) == 2
        assert template.steps[0].step_id == "intro"
        assert template.steps[1].step_id == "main"

    def test_empty_steps_fails(self):
        """Test that template with no steps fails."""
        with pytest.raises(ValidationError):
            Template(
                template_id="empty",
                name="Empty Template",
                category=TemplateCategory.LOW_ENERGY,
                steps=[],
            )

    def test_duplicate_step_ids_fails(self):
        """Test that duplicate step IDs fail."""
        with pytest.raises(ValidationError) as exc_info:
            Template(
                template_id="duplicate",
                name="Duplicate Steps",
                category=TemplateCategory.MEDIUM_ENERGY,
                steps=[
                    PatternStep(
                        step_id="step1",
                        timing=PatternStepTiming(base_timing=MusicalTiming()),
                        movement_id="sweep_lr",
                        dimmer_id="fade_in",
                    ),
                    PatternStep(
                        step_id="step1",  # Duplicate!
                        timing=PatternStepTiming(base_timing=MusicalTiming()),
                        movement_id="circle",
                        dimmer_id="pulse",
                    ),
                ],
            )

        errors = exc_info.value.errors()
        assert any("unique" in str(e).lower() for e in errors)
