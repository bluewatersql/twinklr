"""Tests for JudgeCritic."""

from __future__ import annotations

from unittest.mock import Mock

import pytest

from blinkb0t.core.agents.moving_heads import JudgeCritic
from blinkb0t.core.agents.moving_heads.models_agent_plan import (
    AgentImplementation,
    AgentPlan,
    ImplementationSection,
    SectionPlan,
)
from blinkb0t.core.config.models import (
    AgentConfig,
    AgentOrchestrationConfig,
    JobConfig,
)

# Rebuild JobConfig model to resolve forward references
JobConfig.model_rebuild()


@pytest.fixture
def job_config() -> JobConfig:
    """Create job config for testing."""
    return JobConfig(
        agent=AgentOrchestrationConfig(
            plan_agent=AgentConfig(model="gpt-4", temperature=0.7, max_tokens=4000),
            implementation_agent=AgentConfig(model="gpt-4", temperature=0.5, max_tokens=6000),
            judge_agent=AgentConfig(model="gpt-4", temperature=0.3, max_tokens=2000),
            success_threshold=80,
        )
    )


@pytest.fixture
def mock_openai_client() -> Mock:
    """Mock OpenAI client with good evaluation."""
    client = Mock()

    # Mock passing evaluation
    mock_response = {
        "story_overview": "The sequence builds from a gentle, introspective verse to an energetic chorus with dynamic transitions that mirror the song's emotional arc.",
        "overall_score": 85.0,
        "category_scores": [
            {
                "category": "Musical Alignment",
                "score": 90,
                "reasoning": "Excellent beat alignment throughout",
                "strengths": ["Perfect downbeat alignment", "Smooth transitions"],
                "weaknesses": [],
            },
            {
                "category": "Energy Matching",
                "score": 85,
                "reasoning": "Good energy matching with minor issues",
                "strengths": ["High energy chorus", "Good progression"],
                "weaknesses": ["One minor mismatch in verse"],
            },
            {
                "category": "Template Variety",
                "score": 80,
                "reasoning": "Acceptable variety",
                "strengths": ["Good mix of templates"],
                "weaknesses": ["Could use more variety"],
            },
            {
                "category": "Timing Coverage",
                "score": 90,
                "reasoning": "Perfect coverage",
                "strengths": ["No gaps", "Full song covered"],
                "weaknesses": [],
            },
            {
                "category": "Transition Quality",
                "score": 85,
                "reasoning": "Smooth transitions",
                "strengths": ["Appropriate modes"],
                "weaknesses": ["One transition could be smoother"],
            },
        ],
        "summary": "Good overall execution with minor areas for improvement",
        "actionable_feedback": ["Consider more template variety", "Refine verse energy match"],
        "pass_threshold": True,
    }

    client.generate_json.return_value = mock_response

    # Mock token usage tracking
    token_usage_mock = Mock()
    token_usage_mock.total_tokens = 1000
    token_usage_mock.prompt_tokens = 500
    token_usage_mock.completion_tokens = 500
    client.get_total_token_usage.return_value = token_usage_mock

    return client


@pytest.fixture
def mock_song_features() -> dict:
    """Mock song features."""
    return {
        "duration_s": 180.0,
        "tempo_bpm": 120.0,
        "time_signature": {"time_signature": "4/4"},
        "bars_s": [i * 2.0 for i in range(90)],
        "beats_s": [i * 0.5 for i in range(360)],
    }


@pytest.fixture
def mock_plan() -> AgentPlan:
    """Mock plan for evaluation."""
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
                reasoning="Calm opening",
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
                reasoning="High energy",
            ),
        ],
        overall_strategy="Build from calm to energetic",
        template_variety_score=8,
        energy_alignment_score=9,
    )


@pytest.fixture
def mock_implementation() -> AgentImplementation:
    """Mock implementation for evaluation (Phase 5A schema: bars)."""
    return AgentImplementation(
        sections=[
            ImplementationSection(
                name="verse_1",
                plan_section_name="verse_1",
                start_bar=1,
                end_bar=16,
                template_id="gentle_sweep_breathe",
                params={"intensity": "SMOOTH"},
                base_pose="AUDIENCE_CENTER",
                targets=["ALL"],
                layer_priority=0,
            ),
            ImplementationSection(
                name="chorus_1",
                plan_section_name="chorus_1",
                start_bar=17,
                end_bar=32,
                template_id="energetic_fan_pulse",
                params={"intensity": "DRAMATIC"},
                base_pose="AUDIENCE_CENTER",
                targets=["ALL"],
                layer_priority=0,
            ),
        ],
        total_duration_bars=90,
        quantization_applied=True,
        timing_precision="bar_aligned",
    )


@pytest.fixture
def judge(job_config: JobConfig, mock_openai_client: Mock) -> JudgeCritic:
    """Create JudgeCritic instance."""
    return JudgeCritic(job_config=job_config, openai_client=mock_openai_client)


class TestJudgeCritic:
    """Tests for JudgeCritic."""

    def test_evaluate_success_passing(
        self,
        judge: JudgeCritic,
        mock_plan: AgentPlan,
        mock_implementation: AgentImplementation,
        mock_song_features: dict,
    ):
        """Test successful evaluation with passing score."""
        result = judge.evaluate(
            plan=mock_plan,
            implementation=mock_implementation,
            song_features=mock_song_features,
        )

        assert result.success
        assert result.evaluation is not None
        assert result.evaluation.overall_score == 85.0
        assert result.evaluation.pass_threshold is True
        assert len(result.evaluation.category_scores) == 5
        assert result.failure_analysis is None  # No failure analysis for passing

    def test_evaluate_success_failing(
        self,
        judge: JudgeCritic,
        mock_plan: AgentPlan,
        mock_implementation: AgentImplementation,
        mock_song_features: dict,
        mock_openai_client: Mock,
    ):
        """Test successful evaluation with failing score."""
        # Mock failing evaluation
        mock_openai_client.generate_json.return_value = {
            "story_overview": "The sequence attempts to build energy but struggles with repetitive patterns and timing issues that detract from the overall impact.",
            "overall_score": 55.0,
            "category_scores": [
                {
                    "category": "Musical Alignment",
                    "score": 70,
                    "reasoning": "Acceptable alignment",
                    "strengths": ["Good overall"],
                    "weaknesses": ["Some timing issues"],
                },
                {
                    "category": "Energy Matching",
                    "score": 45,
                    "reasoning": "Poor energy matching",
                    "strengths": [],
                    "weaknesses": ["Major mismatches"],
                },
                {
                    "category": "Template Variety",
                    "score": 40,
                    "reasoning": "Too repetitive",
                    "strengths": [],
                    "weaknesses": ["Same template repeated"],
                },
                {
                    "category": "Timing Coverage",
                    "score": 65,
                    "reasoning": "Some gaps",
                    "strengths": ["Most covered"],
                    "weaknesses": ["Few gaps"],
                },
                {
                    "category": "Transition Quality",
                    "score": 55,
                    "reasoning": "Some rough transitions",
                    "strengths": [],
                    "weaknesses": ["Jarring cuts"],
                },
            ],
            "summary": "Needs significant improvement",
            "actionable_feedback": ["Improve energy matching", "Add template variety"],
            "pass_threshold": False,
        }

        result = judge.evaluate(
            plan=mock_plan,
            implementation=mock_implementation,
            song_features=mock_song_features,
        )

        assert result.success
        assert result.evaluation is not None
        assert result.evaluation.overall_score == 55.0
        assert result.evaluation.pass_threshold is False
        assert result.failure_analysis is not None  # Should have failure analysis

    def test_category_scores(
        self,
        judge: JudgeCritic,
        mock_plan: AgentPlan,
        mock_implementation: AgentImplementation,
        mock_song_features: dict,
    ):
        """Test that all 5 categories are evaluated."""
        result = judge.evaluate(
            plan=mock_plan,
            implementation=mock_implementation,
            song_features=mock_song_features,
        )

        assert result.success
        categories = {score.category for score in result.evaluation.category_scores}
        expected = {
            "Musical Alignment",
            "Energy Matching",
            "Template Variety",
            "Timing Coverage",
            "Transition Quality",
        }
        assert categories == expected

    def test_failure_analysis_plan_issue(self, judge: JudgeCritic):
        """Test failure analysis identifies plan issues."""
        from blinkb0t.core.agents.moving_heads.judge_critic import (
            CategoryScore,
            Evaluation,
        )

        eval = Evaluation(
            story_overview="The sequence has plan-related issues that need to be addressed",
            overall_score=55.0,
            category_scores=[
                CategoryScore(
                    category="Musical Alignment",
                    score=70,
                    reasoning="OK",
                    strengths=[],
                    weaknesses=[],
                ),
                CategoryScore(
                    category="Energy Matching",
                    score=45,  # Failing plan-related
                    reasoning="Poor",
                    strengths=[],
                    weaknesses=["Bad match"],
                ),
                CategoryScore(
                    category="Template Variety",
                    score=40,  # Failing plan-related
                    reasoning="Poor",
                    strengths=[],
                    weaknesses=["Repetitive"],
                ),
                CategoryScore(
                    category="Timing Coverage",
                    score=70,
                    reasoning="OK",
                    strengths=[],
                    weaknesses=[],
                ),
                CategoryScore(
                    category="Transition Quality",
                    score=65,
                    reasoning="OK",
                    strengths=[],
                    weaknesses=[],
                ),
            ],
            summary="Plan issues",
            actionable_feedback=["Fix plan"],
            pass_threshold=False,
        )

        mock_plan = Mock()
        mock_impl = Mock()

        analysis = judge._analyze_failure(eval, mock_plan, mock_impl)

        assert analysis.primary_issue == "plan"
        assert analysis.fix_strategy == "replan"
        assert "Energy Matching" in analysis.failure_categories
        assert "Template Variety" in analysis.failure_categories

    def test_failure_analysis_implementation_issue(self, judge: JudgeCritic):
        """Test failure analysis identifies implementation issues."""
        from blinkb0t.core.agents.moving_heads.judge_critic import (
            CategoryScore,
            Evaluation,
        )

        eval = Evaluation(
            story_overview="The sequence has implementation-related issues with timing and transitions",
            overall_score=55.0,
            category_scores=[
                CategoryScore(
                    category="Musical Alignment",
                    score=45,  # Failing impl-related
                    reasoning="Poor",
                    strengths=[],
                    weaknesses=["Bad timing"],
                ),
                CategoryScore(
                    category="Energy Matching",
                    score=70,
                    reasoning="OK",
                    strengths=[],
                    weaknesses=[],
                ),
                CategoryScore(
                    category="Template Variety",
                    score=70,
                    reasoning="OK",
                    strengths=[],
                    weaknesses=[],
                ),
                CategoryScore(
                    category="Timing Coverage",
                    score=50,  # Failing impl-related
                    reasoning="Poor",
                    strengths=[],
                    weaknesses=["Gaps"],
                ),
                CategoryScore(
                    category="Transition Quality",
                    score=55,  # Failing impl-related
                    reasoning="Poor",
                    strengths=[],
                    weaknesses=["Rough"],
                ),
            ],
            summary="Implementation issues",
            actionable_feedback=["Fix implementation"],
            pass_threshold=False,
        )

        mock_plan = Mock()
        mock_impl = Mock()

        analysis = judge._analyze_failure(eval, mock_plan, mock_impl)

        assert analysis.primary_issue == "implementation"
        assert analysis.fix_strategy == "refine_implementation"
        assert "Musical Alignment" in analysis.failure_categories
        assert "Timing Coverage" in analysis.failure_categories

    def test_system_prompt(self, judge: JudgeCritic):
        """Test system prompt is defined with pass threshold."""
        system_prompt = judge._get_system_prompt()

        assert len(system_prompt) > 0
        assert "critic" in system_prompt.lower() or "judge" in system_prompt.lower()
        assert "musical alignment" in system_prompt.lower()
        assert "energy matching" in system_prompt.lower()
        assert "80" in system_prompt  # Pass threshold

    def test_prompt_building(
        self,
        judge: JudgeCritic,
        mock_plan: AgentPlan,
        mock_implementation: AgentImplementation,
    ):
        """Test prompt building includes key elements."""
        shaped_context = {
            "audio_summary": {
                "duration_s": 180.0,
                "tempo_bpm": 120,
                "time_signature": "4/4",
                "bar_count": 90,
            }
        }

        prompt = judge._build_prompt(mock_plan, mock_implementation, shaped_context)

        # Check key elements
        assert "verse_1" in prompt
        assert "chorus_1" in prompt
        assert "gentle_sweep_breathe" in prompt
        assert "energetic_fan_pulse" in prompt
        assert "120" in prompt  # Tempo
        assert "Musical Alignment" in prompt
        assert "Energy Matching" in prompt

    def test_invalid_json_handling(
        self,
        judge: JudgeCritic,
        mock_plan: AgentPlan,
        mock_implementation: AgentImplementation,
        mock_song_features: dict,
        mock_openai_client: Mock,
    ):
        """Test handling of invalid JSON response."""
        # Mock invalid response
        mock_openai_client.generate_json.return_value = {
            "overall_score": "invalid",  # Should be float
            "category_scores": [],
        }

        result = judge.evaluate(
            plan=mock_plan,
            implementation=mock_implementation,
            song_features=mock_song_features,
        )

        assert not result.success
        assert result.evaluation is None
        assert result.error is not None
        assert "validation" in result.error.lower() or "parse" in result.error.lower()

    def test_pass_threshold_applied(
        self,
        judge: JudgeCritic,
        mock_plan: AgentPlan,
        mock_implementation: AgentImplementation,
        mock_song_features: dict,
        mock_openai_client: Mock,
    ):
        """Test that pass threshold is correctly applied."""
        # Test exactly at threshold (80)
        mock_openai_client.generate_json.return_value = {
            "story_overview": "The sequence meets the minimum threshold with acceptable execution across all categories",
            "overall_score": 80.0,
            "category_scores": [
                {
                    "category": "Musical Alignment",
                    "score": 80,
                    "reasoning": "At threshold",
                    "strengths": ["OK"],
                    "weaknesses": [],
                }
                for _ in range(5)
            ],
            "summary": "At threshold",
            "actionable_feedback": [],
            "pass_threshold": True,
        }

        result = judge.evaluate(
            plan=mock_plan,
            implementation=mock_implementation,
            song_features=mock_song_features,
        )

        assert result.success
        assert result.evaluation.overall_score == 80.0
        assert result.evaluation.pass_threshold is True

    def test_context_shaping_for_judge(
        self,
        judge: JudgeCritic,
        mock_plan: AgentPlan,
        mock_implementation: AgentImplementation,
        mock_song_features: dict,
    ):
        """Test that context is shaped for JUDGE stage."""
        result = judge.evaluate(
            plan=mock_plan,
            implementation=mock_implementation,
            song_features=mock_song_features,
        )

        # Should succeed (context shaping should work)
        assert result.success
