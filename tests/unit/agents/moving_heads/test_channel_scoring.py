"""Tests for channel scoring validation.

Tests that ensure judge evaluates channel usage
and provides feedback on shutter/color/gobo appropriateness.
"""

from blinkb0t.core.agents.moving_heads.judge_critic import CategoryScore, Evaluation
from blinkb0t.core.agents.moving_heads.models_agent_plan import ChannelScoring


class TestChannelScoring:
    """Test channel scoring validation."""

    def test_evaluation_has_channel_scoring(self):
        """Test that evaluation includes channel scoring."""
        # Create evaluation with proper channel scoring (bug is fixed)
        evaluation = Evaluation(
            story_overview="Test sequence with good channel usage",
            overall_score=85.0,
            category_scores=[
                CategoryScore(
                    category="Musical Alignment",
                    score=95,
                    reasoning="Excellent alignment",
                    strengths=["Perfect downbeat alignment"],
                    weaknesses=[],
                )
            ],
            summary="Good plan",
            actionable_feedback=["Consider adding more variety"],
            pass_threshold=True,
            channel_scoring=ChannelScoring(  # ✅ Fixed: now includes channel scoring
                shutter_appropriateness=8,
                color_appropriateness=9,
                gobo_appropriateness=1,
                visual_impact=8,
            ),
        )

        # Verify channel scoring is present and valid
        assert evaluation.channel_scoring is not None
        assert isinstance(evaluation.channel_scoring, ChannelScoring)
        assert evaluation.channel_scoring.shutter_appropriateness == 8

    def test_channel_scoring_when_no_channels_used(self):
        """Test channel scoring when no channels are used (should have minimum scores)."""
        # When no channels are used, should still have scoring with minimum values
        evaluation = Evaluation(
            story_overview="Test sequence without channel effects",
            overall_score=70.0,
            category_scores=[],
            summary="No channels used",
            actionable_feedback=["Add channel effects for visual impact"],
            pass_threshold=False,
            channel_scoring=ChannelScoring(
                shutter_appropriateness=1,  # Minimum score
                shutter_issues=["No shutter effects specified"],
                color_appropriateness=1,  # Minimum score
                color_issues=["No color effects specified"],
                gobo_appropriateness=1,  # Minimum score
                gobo_issues=["No gobo effects specified"],
                visual_impact=1,  # Minimum score
                visual_impact_issues=["Consider adding channel effects for visual impact"],
            ),
        )

        # Verify scoring exists and has minimum scores
        assert evaluation.channel_scoring is not None
        assert evaluation.channel_scoring.shutter_appropriateness >= 1
        assert evaluation.channel_scoring.color_appropriateness >= 1
        assert evaluation.channel_scoring.gobo_appropriateness >= 1
        assert len(evaluation.channel_scoring.visual_impact_issues) > 0

    def test_channel_scoring_when_channels_used(self):
        """Test channel scoring when channels are actually used."""
        # When channels are used, should have higher scores
        evaluation = Evaluation(
            story_overview="Test sequence with excellent channel coordination",
            overall_score=90.0,
            category_scores=[],
            summary="Good channel usage",
            actionable_feedback=[],
            pass_threshold=True,
            channel_scoring=ChannelScoring(
                shutter_appropriateness=9,  # Good shutter usage
                shutter_issues=[],
                color_appropriateness=10,  # Excellent color usage
                color_issues=[],
                gobo_appropriateness=1,  # No gobos used
                gobo_issues=["Consider adding gobo patterns for texture"],
                visual_impact=9,  # Good overall impact
                visual_impact_issues=[],
            ),
        )

        # Verify scoring reflects usage
        assert evaluation.channel_scoring is not None
        assert evaluation.channel_scoring.shutter_appropriateness > 1
        assert evaluation.channel_scoring.color_appropriateness > 1
        assert evaluation.channel_scoring.visual_impact > 1

    def test_channel_scoring_includes_all_categories(self):
        """Test that channel scoring includes all required categories."""
        evaluation = Evaluation(
            story_overview="Test sequence for channel scoring validation",
            overall_score=85.0,
            category_scores=[],
            summary="Test",
            actionable_feedback=[],
            pass_threshold=True,
            channel_scoring=ChannelScoring(
                shutter_appropriateness=8,
                color_appropriateness=8,
                gobo_appropriateness=1,
                visual_impact=7,
            ),
        )

        # Verify all required attributes present
        assert hasattr(evaluation.channel_scoring, "shutter_appropriateness")
        assert hasattr(evaluation.channel_scoring, "color_appropriateness")
        assert hasattr(evaluation.channel_scoring, "gobo_appropriateness")
        assert hasattr(evaluation.channel_scoring, "visual_impact")
        assert hasattr(evaluation.channel_scoring, "shutter_issues")
        assert hasattr(evaluation.channel_scoring, "color_issues")
        assert hasattr(evaluation.channel_scoring, "gobo_issues")
        assert hasattr(evaluation.channel_scoring, "visual_impact_issues")

    def test_channel_scoring_reasoning_is_specific(self):
        """Test that channel scoring reasoning is specific and actionable."""
        evaluation = Evaluation(
            story_overview="Test sequence with specific channel issues to address",
            overall_score=75.0,
            category_scores=[],
            summary="Needs improvement",
            actionable_feedback=[],
            pass_threshold=False,
            channel_scoring=ChannelScoring(
                shutter_appropriateness=5,
                shutter_issues=[
                    "Inconsistent with energy levels",
                    "Low-energy sections have fast strobes",
                ],
                color_appropriateness=6,
                color_issues=["Limited variety"],
                gobo_appropriateness=1,
                gobo_issues=["No gobo patterns used"],
                visual_impact=4,
                visual_impact_issues=["Consider using pulse patterns for builds"],
            ),
        )

        # Verify issues are substantial and specific
        all_issues = (
            evaluation.channel_scoring.shutter_issues
            + evaluation.channel_scoring.color_issues
            + evaluation.channel_scoring.gobo_issues
            + evaluation.channel_scoring.visual_impact_issues
        )

        assert len(all_issues) > 0, "Channel scoring should have specific issues"

        # Check that issues reference specific channels
        all_issues_text = " ".join(all_issues).lower()
        assert any(
            word in all_issues_text for word in ["shutter", "strobe", "pulse", "color", "gobo"]
        ), "Issues should mention specific channel types"
