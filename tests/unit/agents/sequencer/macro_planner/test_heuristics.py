"""Unit tests for MacroPlanner V2 heuristic validator."""

import pytest

from twinklr.core.agents.audio.profile.models import Provenance
from twinklr.core.agents.issues import IssueCategory, IssueSeverity
from twinklr.core.agents.sequencer.macro_planner.heuristics import (
    MacroPlanHeuristicValidator,
)
from twinklr.core.agents.sequencer.macro_planner.models import (
    ChoreographyStyle,
    EnergyTarget,
    GlobalConstraints,
    GlobalStory,
    LayeringPlan,
    LayerIntent,
    MacroPlan,
    MacroSectionPlan,
    MotionDensity,
)


@pytest.fixture
def provenance() -> Provenance:
    """Create a test provenance."""
    return Provenance(
        provider_id="openai",
        model_id="gpt-5.2",
        prompt_pack="macro_planner.v2",
        prompt_pack_version="2.0",
        framework_version="2.0",
        temperature=0.7,
    )


@pytest.fixture
def global_story() -> GlobalStory:
    """Create a test global story."""
    return GlobalStory(
        theme="Joyful celebration",
        motifs=["Rising intensity", "Call-and-response"],
        pacing_notes="Gradual build to peak at chorus",
        color_story="Traditional red/green with white accents",
    )


@pytest.fixture
def sample_section() -> MacroSectionPlan:
    """Create a sample section plan."""
    return MacroSectionPlan(
        section_id="section-1",
        section_name="verse_1",
        start_ms=0,
        end_ms=16000,
        energy_target=EnergyTarget.MED,
        primary_focus_groups=["mega_tree", "roofline"],
        choreography_style=ChoreographyStyle.ABSTRACT,
        motion_density=MotionDensity.MED,
        layering_plan=LayeringPlan(
            layers=[LayerIntent(layer_index=1, intent="Create ambient mood")]
        ),
    )


class TestMacroPlanHeuristicValidator:
    """Tests for MacroPlanHeuristicValidator V2."""

    def test_valid_plan(self, provenance, global_story, sample_section):
        """Test validation of a valid plan."""
        section2 = MacroSectionPlan(
            section_id="section-2",
            section_name="chorus",
            start_ms=16000,
            end_ms=32000,
            energy_target=EnergyTarget.HIGH,
            primary_focus_groups=["mega_tree"],
            choreography_style=ChoreographyStyle.HYBRID,
            motion_density=MotionDensity.BUSY,
            layering_plan=LayeringPlan(layers=[LayerIntent(layer_index=1, intent="Peak energy")]),
        )

        plan = MacroPlan(
            run_id="test-run-123",
            iteration=1,
            provenance=provenance,
            global_story=global_story,
            section_plans=[sample_section, section2],
            global_constraints=GlobalConstraints(),
        )

        validator = MacroPlanHeuristicValidator()
        issues = validator.validate(plan)

        assert len(issues) == 0

    def test_empty_global_story_theme(self, provenance, sample_section):
        """Test that empty theme is caught."""
        plan = MacroPlan(
            run_id="test",
            iteration=1,
            provenance=provenance,
            global_story=GlobalStory(
                theme="",  # Empty!
                motifs=["Test"],
                pacing_notes="Test",
                color_story="Test",
            ),
            section_plans=[sample_section],
            global_constraints=GlobalConstraints(),
        )

        validator = MacroPlanHeuristicValidator()
        issues = validator.validate(plan)

        assert len(issues) == 1
        assert issues[0].severity == IssueSeverity.ERROR
        assert "theme" in issues[0].message.lower()

    def test_empty_motifs(self, provenance, sample_section):
        """Test that empty motifs is caught."""
        plan = MacroPlan(
            run_id="test",
            iteration=1,
            provenance=provenance,
            global_story=GlobalStory(
                theme="Test",
                motifs=[],  # Empty!
                pacing_notes="Test",
                color_story="Test",
            ),
            section_plans=[sample_section],
            global_constraints=GlobalConstraints(),
        )

        validator = MacroPlanHeuristicValidator()
        issues = validator.validate(plan)

        assert len(issues) == 1
        assert issues[0].severity == IssueSeverity.ERROR
        assert "motifs" in issues[0].message.lower()

    def test_no_sections(self, provenance, global_story):
        """Test that plan with no sections is caught by Pydantic validation."""
        # Pydantic validation catches this at model instantiation
        with pytest.raises(ValueError, match="at least one section"):
            MacroPlan(
                run_id="test",
                iteration=1,
                provenance=provenance,
                global_story=global_story,
                section_plans=[],  # Empty!
                global_constraints=GlobalConstraints(),
            )

    def test_no_primary_focus_groups(self, provenance, global_story):
        """Test that section with no primary focus groups is caught by Pydantic validation."""
        # Pydantic validation catches this at model instantiation
        with pytest.raises(ValueError, match="at least one primary focus group"):
            MacroSectionPlan(
                section_id="test",
                section_name="test",
                start_ms=0,
                end_ms=1000,
                energy_target=EnergyTarget.MED,
                primary_focus_groups=[],  # Empty!
                choreography_style=ChoreographyStyle.ABSTRACT,
                motion_density=MotionDensity.MED,
                layering_plan=LayeringPlan(layers=[LayerIntent(layer_index=1, intent="Test")]),
            )

    def test_overlapping_sections(self, provenance, global_story):
        """Test that overlapping sections are caught."""
        section1 = MacroSectionPlan(
            section_id="s1",
            section_name="verse",
            start_ms=0,
            end_ms=16000,
            energy_target=EnergyTarget.MED,
            primary_focus_groups=["group1"],
            choreography_style=ChoreographyStyle.ABSTRACT,
            motion_density=MotionDensity.MED,
            layering_plan=LayeringPlan(layers=[LayerIntent(layer_index=1, intent="Test")]),
        )

        section2 = MacroSectionPlan(
            section_id="s2",
            section_name="chorus",
            start_ms=15000,  # Overlaps with section1!
            end_ms=30000,
            energy_target=EnergyTarget.HIGH,
            primary_focus_groups=["group1"],
            choreography_style=ChoreographyStyle.ABSTRACT,
            motion_density=MotionDensity.MED,
            layering_plan=LayeringPlan(layers=[LayerIntent(layer_index=1, intent="Test")]),
        )

        plan = MacroPlan(
            run_id="test",
            iteration=1,
            provenance=provenance,
            global_story=global_story,
            section_plans=[section1, section2],
            global_constraints=GlobalConstraints(),
        )

        validator = MacroPlanHeuristicValidator()
        issues = validator.validate(plan)

        assert len(issues) == 1
        assert issues[0].severity == IssueSeverity.ERROR
        assert issues[0].category == IssueCategory.TIMING
        assert "overlap" in issues[0].message.lower()

    def test_gap_between_sections(self, provenance, global_story):
        """Test that gaps between sections trigger warnings."""
        section1 = MacroSectionPlan(
            section_id="s1",
            section_name="verse",
            start_ms=0,
            end_ms=16000,
            energy_target=EnergyTarget.MED,
            primary_focus_groups=["group1"],
            choreography_style=ChoreographyStyle.ABSTRACT,
            motion_density=MotionDensity.MED,
            layering_plan=LayeringPlan(layers=[LayerIntent(layer_index=1, intent="Test")]),
        )

        section2 = MacroSectionPlan(
            section_id="s2",
            section_name="chorus",
            start_ms=17000,  # Gap of 1000ms!
            end_ms=30000,
            energy_target=EnergyTarget.HIGH,
            primary_focus_groups=["group1"],
            choreography_style=ChoreographyStyle.ABSTRACT,
            motion_density=MotionDensity.MED,
            layering_plan=LayeringPlan(layers=[LayerIntent(layer_index=1, intent="Test")]),
        )

        plan = MacroPlan(
            run_id="test",
            iteration=1,
            provenance=provenance,
            global_story=global_story,
            section_plans=[section1, section2],
            global_constraints=GlobalConstraints(),
        )

        validator = MacroPlanHeuristicValidator()
        issues = validator.validate(plan)

        assert len(issues) == 1
        assert issues[0].severity == IssueSeverity.WARN  # Warning, not error
        assert issues[0].category == IssueCategory.TIMING
        assert "gap" in issues[0].message.lower()
