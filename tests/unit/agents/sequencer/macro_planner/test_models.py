"""Unit tests for MacroPlanner V2 models (design spec compliant).

Tests the new schema that matches:
changes/vnext/agents/core/04_macro_planner_agent_full_spec.md
"""

from pydantic import ValidationError
import pytest

from twinklr.core.agents.audio.profile.models import Provenance
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


class TestEnergyTarget:
    """Test EnergyTarget enum."""

    def test_all_values(self):
        """Test all enum values are defined."""
        assert EnergyTarget.LOW == "LOW"
        assert EnergyTarget.MED == "MED"
        assert EnergyTarget.HIGH == "HIGH"
        assert EnergyTarget.BUILD == "BUILD"
        assert EnergyTarget.RELEASE == "RELEASE"
        assert EnergyTarget.PEAK == "PEAK"


class TestChoreographyStyle:
    """Test ChoreographyStyle enum."""

    def test_all_values(self):
        """Test all enum values are defined."""
        assert ChoreographyStyle.IMAGERY == "imagery"
        assert ChoreographyStyle.ABSTRACT == "abstract"
        assert ChoreographyStyle.HYBRID == "hybrid"


class TestMotionDensity:
    """Test MotionDensity enum."""

    def test_all_values(self):
        """Test all enum values are defined."""
        assert MotionDensity.SPARSE == "SPARSE"
        assert MotionDensity.MED == "MED"
        assert MotionDensity.BUSY == "BUSY"


class TestGlobalStory:
    """Test GlobalStory model."""

    def test_valid_creation(self):
        """Test creating a valid GlobalStory."""
        story = GlobalStory(
            theme="Joyful celebration",
            motifs=["Rising intensity", "Call-and-response"],
            pacing_notes="Gradual build to peak at chorus",
            color_story="Traditional red/green with white accents",
        )
        assert story.theme == "Joyful celebration"
        assert len(story.motifs) == 2
        assert "Rising intensity" in story.motifs

    def test_frozen(self):
        """Test GlobalStory is immutable."""
        story = GlobalStory(
            theme="Test",
            motifs=["Motif"],
            pacing_notes="Notes",
            color_story="Colors",
        )
        with pytest.raises(ValidationError):
            story.theme = "New theme"  # type: ignore

    def test_extra_forbid(self):
        """Test extra fields are forbidden."""
        with pytest.raises(ValidationError):
            GlobalStory(
                theme="Test",
                motifs=["Motif"],
                pacing_notes="Notes",
                color_story="Colors",
                extra_field="not allowed",  # type: ignore
            )


class TestLayerIntent:
    """Test LayerIntent model."""

    def test_valid_creation(self):
        """Test creating a valid LayerIntent."""
        intent = LayerIntent(
            layer_index=1,
            intent="Provide rhythmic punctuation",
            preferred_templates=["chase", "pulse"],
            intensity=0.8,
        )
        assert intent.layer_index == 1
        assert intent.intent == "Provide rhythmic punctuation"
        assert "chase" in intent.preferred_templates

    def test_default_values(self):
        """Test default values."""
        intent = LayerIntent(
            layer_index=2,
            intent="Create ambient mood",
        )
        assert intent.preferred_templates == []
        assert intent.preferred_assets == []
        assert intent.blend_mode == "normal"
        assert intent.intensity == 0.7

    def test_layer_index_validation(self):
        """Test layer_index must be 1-3."""
        with pytest.raises(ValidationError):
            LayerIntent(layer_index=0, intent="Test")

        with pytest.raises(ValidationError):
            LayerIntent(layer_index=4, intent="Test")

    def test_intensity_validation(self):
        """Test intensity must be 0.0-1.0."""
        with pytest.raises(ValidationError):
            LayerIntent(layer_index=1, intent="Test", intensity=-0.1)

        with pytest.raises(ValidationError):
            LayerIntent(layer_index=1, intent="Test", intensity=1.1)


class TestLayeringPlan:
    """Test LayeringPlan model."""

    def test_valid_single_layer(self):
        """Test creating a plan with one layer."""
        plan = LayeringPlan(
            layers=[
                LayerIntent(layer_index=1, intent="Main choreography"),
            ]
        )
        assert len(plan.layers) == 1

    def test_valid_multiple_layers(self):
        """Test creating a plan with multiple layers."""
        plan = LayeringPlan(
            layers=[
                LayerIntent(layer_index=1, intent="Base layer"),
                LayerIntent(layer_index=2, intent="Rhythm layer"),
                LayerIntent(layer_index=3, intent="Highlight layer"),
            ]
        )
        assert len(plan.layers) == 3

    def test_layer_count_validation(self):
        """Test layer count must be 1-3."""
        # Too few
        with pytest.raises(ValidationError, match="Must have 1-3 layers"):
            LayeringPlan(layers=[])

        # Too many
        with pytest.raises(ValidationError, match="Must have 1-3 layers"):
            LayeringPlan(
                layers=[
                    LayerIntent(layer_index=1, intent="L1"),
                    LayerIntent(layer_index=2, intent="L2"),
                    LayerIntent(layer_index=3, intent="L3"),
                    LayerIntent(layer_index=1, intent="L4"),  # Duplicate index
                ]
            )

    def test_unique_layer_indices(self):
        """Test layer indices must be unique."""
        with pytest.raises(ValidationError, match="Layer indices must be unique"):
            LayeringPlan(
                layers=[
                    LayerIntent(layer_index=1, intent="L1"),
                    LayerIntent(layer_index=1, intent="L2"),  # Duplicate!
                ]
            )


class TestMacroSectionPlan:
    """Test MacroSectionPlan model."""

    def test_valid_creation(self):
        """Test creating a valid MacroSectionPlan."""
        section = MacroSectionPlan(
            section_id="chorus_1",
            section_name="chorus",
            start_ms=10000,
            end_ms=20000,
            energy_target=EnergyTarget.HIGH,
            primary_focus_groups=["mega_tree", "roofline"],
            choreography_style=ChoreographyStyle.HYBRID,
            motion_density=MotionDensity.BUSY,
            layering_plan=LayeringPlan(layers=[LayerIntent(layer_index=1, intent="Main show")]),
        )
        assert section.section_id == "chorus_1"
        assert section.energy_target == EnergyTarget.HIGH
        assert "mega_tree" in section.primary_focus_groups

    def test_timing_validation(self):
        """Test end_ms must be > start_ms."""
        with pytest.raises(ValidationError, match="must be > start_ms"):
            MacroSectionPlan(
                section_id="test",
                section_name="test",
                start_ms=10000,
                end_ms=10000,  # Equal, not greater
                energy_target=EnergyTarget.MED,
                primary_focus_groups=["group1"],
                choreography_style=ChoreographyStyle.ABSTRACT,
                motion_density=MotionDensity.MED,
                layering_plan=LayeringPlan(layers=[LayerIntent(layer_index=1, intent="Test")]),
            )

    def test_requires_focus_groups(self):
        """Test at least one primary focus group required."""
        with pytest.raises(ValidationError, match="at least one primary focus group"):
            MacroSectionPlan(
                section_id="test",
                section_name="test",
                start_ms=0,
                end_ms=1000,
                energy_target=EnergyTarget.LOW,
                primary_focus_groups=[],  # Empty!
                choreography_style=ChoreographyStyle.ABSTRACT,
                motion_density=MotionDensity.SPARSE,
                layering_plan=LayeringPlan(layers=[LayerIntent(layer_index=1, intent="Test")]),
            )

    def test_default_values(self):
        """Test default values for optional fields."""
        section = MacroSectionPlan(
            section_id="test",
            section_name="test",
            start_ms=0,
            end_ms=1000,
            energy_target=EnergyTarget.MED,
            primary_focus_groups=["group1"],
            choreography_style=ChoreographyStyle.ABSTRACT,
            motion_density=MotionDensity.MED,
            layering_plan=LayeringPlan(layers=[LayerIntent(layer_index=1, intent="Test")]),
        )
        assert section.secondary_groups == []
        assert section.transition_in is None
        assert section.transition_out is None
        assert section.objectives == []
        assert section.avoid == []


class TestGlobalConstraints:
    """Test GlobalConstraints model."""

    def test_valid_creation(self):
        """Test creating valid GlobalConstraints."""
        constraints = GlobalConstraints(
            max_layers=3,
            default_blend_mode="additive",
            intensity_policy="dynamic",
        )
        assert constraints.max_layers == 3

    def test_default_values(self):
        """Test default values."""
        constraints = GlobalConstraints()
        assert constraints.max_layers == 3
        assert constraints.default_blend_mode == "normal"
        assert constraints.intensity_policy == "dynamic"

    def test_max_layers_validation(self):
        """Test max_layers must be 1-3."""
        with pytest.raises(ValidationError):
            GlobalConstraints(max_layers=0)

        with pytest.raises(ValidationError):
            GlobalConstraints(max_layers=4)


class TestMacroPlan:
    """Test MacroPlan model."""

    @pytest.fixture
    def sample_provenance(self) -> Provenance:
        """Create sample provenance."""
        return Provenance(
            provider_id="openai",
            model_id="gpt-5.2",
            prompt_pack="macro_planner",
            prompt_pack_version="2.0",
            framework_version="2.0",
            seed=None,
            temperature=0.7,
            created_at="2026-01-30T00:00:00Z",
        )

    @pytest.fixture
    def sample_section(self) -> MacroSectionPlan:
        """Create a sample section plan."""
        return MacroSectionPlan(
            section_id="intro_1",
            section_name="intro",
            start_ms=0,
            end_ms=10000,
            energy_target=EnergyTarget.BUILD,
            primary_focus_groups=["roofline"],
            choreography_style=ChoreographyStyle.ABSTRACT,
            motion_density=MotionDensity.SPARSE,
            layering_plan=LayeringPlan(
                layers=[LayerIntent(layer_index=1, intent="Establish mood")]
            ),
        )

    def test_valid_creation(self, sample_provenance, sample_section):
        """Test creating a valid MacroPlan."""
        plan = MacroPlan(
            run_id="test_run_001",
            iteration=1,
            provenance=sample_provenance,
            global_story=GlobalStory(
                theme="Festive celebration",
                motifs=["Rising energy"],
                pacing_notes="Build to climax",
                color_story="Red and green",
            ),
            section_plans=[sample_section],
            global_constraints=GlobalConstraints(),
        )
        assert plan.schema_version == "2.0"
        assert plan.agent_id == "macro_planner.v2"
        assert len(plan.section_plans) == 1

    def test_requires_sections(self, sample_provenance):
        """Test at least one section required."""
        with pytest.raises(ValidationError, match="at least one section"):
            MacroPlan(
                run_id="test",
                iteration=1,
                provenance=sample_provenance,
                global_story=GlobalStory(
                    theme="Test",
                    motifs=["Test"],
                    pacing_notes="Test",
                    color_story="Test",
                ),
                section_plans=[],  # Empty!
                global_constraints=GlobalConstraints(),
            )

    def test_default_values(self, sample_provenance, sample_section):
        """Test default values for optional fields."""
        plan = MacroPlan(
            run_id="test",
            iteration=1,
            provenance=sample_provenance,
            global_story=GlobalStory(
                theme="Test",
                motifs=["Test"],
                pacing_notes="Test",
                color_story="Test",
            ),
            section_plans=[sample_section],
            global_constraints=GlobalConstraints(),
        )
        assert plan.warnings == []
        assert plan.asset_requirements == []
        assert plan.judge_score is None
        assert plan.judge_feedback is None

    def test_judge_score_validation(self, sample_provenance, sample_section):
        """Test judge_score must be 0-10."""
        with pytest.raises(ValidationError):
            MacroPlan(
                run_id="test",
                iteration=1,
                provenance=sample_provenance,
                global_story=GlobalStory(
                    theme="Test",
                    motifs=["Test"],
                    pacing_notes="Test",
                    color_story="Test",
                ),
                section_plans=[sample_section],
                global_constraints=GlobalConstraints(),
                judge_score=11.0,  # Too high
            )

    def test_frozen(self, sample_provenance, sample_section):
        """Test MacroPlan is immutable."""
        plan = MacroPlan(
            run_id="test",
            iteration=1,
            provenance=sample_provenance,
            global_story=GlobalStory(
                theme="Test",
                motifs=["Test"],
                pacing_notes="Test",
                color_story="Test",
            ),
            section_plans=[sample_section],
            global_constraints=GlobalConstraints(),
        )
        with pytest.raises(ValidationError):
            plan.iteration = 2  # type: ignore

    def test_extra_forbid(self, sample_provenance, sample_section):
        """Test extra fields are forbidden."""
        with pytest.raises(ValidationError):
            MacroPlan(
                run_id="test",
                iteration=1,
                provenance=sample_provenance,
                global_story=GlobalStory(
                    theme="Test",
                    motifs=["Test"],
                    pacing_notes="Test",
                    color_story="Test",
                ),
                section_plans=[sample_section],
                global_constraints=GlobalConstraints(),
                extra_field="not allowed",  # type: ignore
            )
