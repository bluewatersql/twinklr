"""Unit tests for agent plan models (extensions)."""

from pydantic import ValidationError
import pytest

from blinkb0t.core.agents.moving_heads.models_agent_plan import ChannelScoring, SectionPlan
from blinkb0t.core.domains.sequencing.models.channels import ChannelSpecification


class TestSectionPlanChannels:
    """Test SectionPlan withchannel extensions."""

    def test_section_plan_with_channels(self):
        """Test creating section plan with channel specifications."""
        section = SectionPlan(
            name="verse_1",
            start_bar=1,
            end_bar=8,
            section_role="verse",
            energy_level=50,
            templates=["gentle_sweep"],
            params={"intensity": "SMOOTH"},
            base_pose="FORWARD",
            reasoning="Gentle verse with soft lighting",
            channels=ChannelSpecification(shutter="open", color="blue", gobo="clouds"),
        )

        assert section.name == "verse_1"
        assert section.channels.shutter == "open"
        assert section.channels.color == "blue"
        assert section.channels.gobo == "clouds"

    def test_section_plan_without_channels_uses_defaults(self):
        """Test section plan without explicit channels field."""
        section = SectionPlan(
            name="chorus_1",
            start_bar=9,
            end_bar=16,
            section_role="chorus",
            energy_level=80,
            templates=["energetic_fan"],
            params={"intensity": "DRAMATIC"},
            base_pose="UP",
            reasoning="High energy chorus",
        )

        # Should have default (empty) ChannelSpecification
        assert isinstance(section.channels, ChannelSpecification)
        assert section.channels.shutter is None
        assert section.channels.color is None
        assert section.channels.gobo is None

    def test_section_plan_partial_channels(self):
        """Test section plan with partial channel overrides."""
        section = SectionPlan(
            name="bridge",
            start_bar=17,
            end_bar=24,
            section_role="bridge",
            energy_level=60,
            templates=["slow_wave"],
            params={},
            base_pose="DOWN",
            reasoning="Atmospheric bridge",
            channels=ChannelSpecification(
                color="purple"  # Only override color
            ),
        )

        assert section.channels.shutter is None  # Not overridden
        assert section.channels.color == "purple"  # Overridden
        assert section.channels.gobo is None  # Not overridden

    def test_section_plan_validates_bar_numbers(self):
        """Test section plan validates bar numbers."""
        # Should allow valid bar numbers
        section = SectionPlan(
            name="test",
            start_bar=1,
            end_bar=8,
            section_role="verse",
            energy_level=50,
            templates=["test"],
            params={},
            base_pose="FORWARD",
            reasoning="test",
        )
        assert section.start_bar == 1
        assert section.end_bar == 8

        # Should reject negative/zero bar numbers
        with pytest.raises(ValidationError):
            SectionPlan(
                name="test",
                start_bar=0,  # Invalid
                end_bar=8,
                section_role="verse",
                energy_level=50,
                templates=["test"],
                params={},
                base_pose="FORWARD",
                reasoning="test",
            )

    def test_section_plan_validates_energy_level(self):
        """Test section plan validates energy level range."""
        # Should allow valid energy (0-100)
        section = SectionPlan(
            name="test",
            start_bar=1,
            end_bar=8,
            section_role="verse",
            energy_level=75,
            templates=["test"],
            params={},
            base_pose="FORWARD",
            reasoning="test",
        )
        assert section.energy_level == 75

        # Should reject energy > 100
        with pytest.raises(ValidationError):
            SectionPlan(
                name="test",
                start_bar=1,
                end_bar=8,
                section_role="verse",
                energy_level=101,  # Invalid
                templates=["test"],
                params={},
                base_pose="FORWARD",
                reasoning="test",
            )

        # Should reject energy < 0
        with pytest.raises(ValidationError):
            SectionPlan(
                name="test",
                start_bar=1,
                end_bar=8,
                section_role="verse",
                energy_level=-1,  # Invalid
                templates=["test"],
                params={},
                base_pose="FORWARD",
                reasoning="test",
            )

    def test_section_plan_backward_compatible(self):
        """Test backward compatibility - old plans without channels still work."""
        # Old plan without channels field
        old_plan_data = {
            "name": "verse_1",
            "start_bar": 1,
            "end_bar": 8,
            "section_role": "verse",
            "energy_level": 50,
            "templates": ["gentle_sweep"],
            "params": {"intensity": "SMOOTH"},
            "base_pose": "FORWARD",
            "reasoning": "Gentle verse",
            # No channels field
        }

        section = SectionPlan(**old_plan_data)
        assert section.name == "verse_1"
        assert isinstance(section.channels, ChannelSpecification)
        # Should have default empty channels
        assert section.channels.shutter is None


class TestChannelScoring:
    """Test ChannelScoring model for judge output."""

    def test_channel_scoring_valid(self):
        """Test creating valid channel scoring."""
        scoring = ChannelScoring(
            shutter_appropriateness=8,
            shutter_issues=[],
            color_appropriateness=7,
            color_issues=["Could use warmer colors in chorus"],
            gobo_appropriateness=9,
            gobo_issues=[],
            visual_impact=8,
            visual_impact_issues=[],
        )

        assert scoring.shutter_appropriateness == 8
        assert scoring.color_appropriateness == 7
        assert scoring.gobo_appropriateness == 9
        assert scoring.visual_impact == 8
        assert len(scoring.color_issues) == 1

    def test_channel_scoring_validates_range(self):
        """Test channel scoring validates score range (1-10)."""
        # Valid score
        scoring = ChannelScoring(
            shutter_appropriateness=5,
            color_appropriateness=5,
            gobo_appropriateness=5,
            visual_impact=5,
        )
        assert scoring.shutter_appropriateness == 5

        # Score too high
        with pytest.raises(ValidationError):
            ChannelScoring(
                shutter_appropriateness=11,  # Invalid
                color_appropriateness=5,
                gobo_appropriateness=5,
                visual_impact=5,
            )

        # Score too low
        with pytest.raises(ValidationError):
            ChannelScoring(
                shutter_appropriateness=5,
                color_appropriateness=0,  # Invalid
                gobo_appropriateness=5,
                visual_impact=5,
            )

    def test_channel_scoring_with_issues(self):
        """Test channel scoring with multiple issues."""
        scoring = ChannelScoring(
            shutter_appropriateness=6,
            shutter_issues=[
                "Strobe overused in low-energy sections",
                "Consider pulse instead of fast strobe",
            ],
            color_appropriateness=7,
            color_issues=["Color changes too frequent"],
            gobo_appropriateness=8,
            gobo_issues=[],
            visual_impact=7,
            visual_impact_issues=["Lacks memorable visual moments"],
        )

        assert len(scoring.shutter_issues) == 2
        assert len(scoring.color_issues) == 1
        assert len(scoring.gobo_issues) == 0
        assert len(scoring.visual_impact_issues) == 1

    def test_channel_scoring_defaults_to_empty_issues(self):
        """Test channel scoring defaults issues to empty lists."""
        scoring = ChannelScoring(
            shutter_appropriateness=8,
            color_appropriateness=7,
            gobo_appropriateness=9,
            visual_impact=8,
        )

        assert scoring.shutter_issues == []
        assert scoring.color_issues == []
        assert scoring.gobo_issues == []
        assert scoring.visual_impact_issues == []
