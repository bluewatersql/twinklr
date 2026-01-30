"""Integration tests for MacroPlanner V2 heuristic validation."""

import json
from pathlib import Path

import pytest

from twinklr.core.agents.audio.profile.models import AudioProfileModel
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
def audio_profile() -> AudioProfileModel:
    """Load audio profile fixture."""
    fixture_path = Path("artifacts/audio_profile_demo_output.json")
    with fixture_path.open() as f:
        data = json.load(f)
    return AudioProfileModel.model_validate(data)


class TestHeuristicValidatorIntegration:
    """Integration tests for heuristic validator with real audio profiles."""

    def test_validator_with_valid_plan(self, audio_profile: AudioProfileModel):
        """Test validator passes valid plan with real audio profile."""
        # Create valid V2 plan matching audio profile sections
        valid_plan = MacroPlan(
            run_id="test_run_001",
            iteration=1,
            provenance=audio_profile.provenance,
            global_story=GlobalStory(
                theme="Festive celebration",
                motifs=["Rising energy", "Call-and-response"],
                pacing_notes="Build gradually to peak at chorus",
                color_story="Traditional red/green with white accents",
            ),
            section_plans=[
                MacroSectionPlan(
                    section_id=section.section_id,
                    section_name=section.name,
                    start_ms=section.start_ms,
                    end_ms=section.end_ms,
                    energy_target=EnergyTarget.MED,
                    primary_focus_groups=["mega_tree", "roofline"],
                    choreography_style=ChoreographyStyle.HYBRID,
                    motion_density=MotionDensity.MED,
                    layering_plan=LayeringPlan(
                        layers=[LayerIntent(layer_index=1, intent="Match section energy and mood")]
                    ),
                )
                for section in audio_profile.structure.sections
            ],
            global_constraints=GlobalConstraints(),
        )

        validator = MacroPlanHeuristicValidator()
        issues = validator.validate(valid_plan)

        assert len(issues) == 0

    def test_validator_catches_empty_theme(self, audio_profile: AudioProfileModel):
        """Test validator catches empty global story theme."""
        invalid_plan = MacroPlan(
            run_id="test_run_002",
            iteration=1,
            provenance=audio_profile.provenance,
            global_story=GlobalStory(
                theme="",  # Empty - should fail
                motifs=["Test"],
                pacing_notes="Test",
                color_story="Test",
            ),
            section_plans=[
                MacroSectionPlan(
                    section_id=audio_profile.structure.sections[0].section_id,
                    section_name=audio_profile.structure.sections[0].name,
                    start_ms=audio_profile.structure.sections[0].start_ms,
                    end_ms=audio_profile.structure.sections[0].end_ms,
                    energy_target=EnergyTarget.MED,
                    primary_focus_groups=["mega_tree"],
                    choreography_style=ChoreographyStyle.ABSTRACT,
                    motion_density=MotionDensity.MED,
                    layering_plan=LayeringPlan(layers=[LayerIntent(layer_index=1, intent="Test")]),
                )
            ],
            global_constraints=GlobalConstraints(),
        )

        validator = MacroPlanHeuristicValidator()
        issues = validator.validate(invalid_plan)

        assert len(issues) > 0
        assert any("theme" in issue.message.lower() for issue in issues)
