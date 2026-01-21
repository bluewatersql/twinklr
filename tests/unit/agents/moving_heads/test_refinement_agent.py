"""Tests for RefinementAgent component."""

from __future__ import annotations

from typing import Any
from unittest.mock import Mock

import pytest

from blinkb0t.core.agents.moving_heads.judge_critic import (
    CategoryScore,
    Evaluation,
    FailureAnalysis,
)
from blinkb0t.core.agents.moving_heads.models_agent_plan import (
    AgentImplementation,
    AgentPlan,
    ImplementationSection,
    SectionPlan,
)
from blinkb0t.core.agents.moving_heads.refinement_agent import (
    RefinementAgent,
    RefinementResult,
    RefineStrategy,
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
    """Create test job config."""
    return JobConfig(
        openai_api_key="test-key",
        agent=AgentOrchestrationConfig(
            refinement_agent=AgentConfig(
                model="gpt-5.2",
                temperature=0.4,
                max_tokens=10000,
            ),
        ),
    )


@pytest.fixture
def mock_openai_client() -> Mock:
    """Create mock OpenAI client."""
    client = Mock()

    # Mock generate_json to return dict directly
    client.generate_json.return_value = {"sections": []}

    # Mock token usage tracking
    token_usage_mock = Mock()
    token_usage_mock.total_tokens = 1000
    token_usage_mock.prompt_tokens = 500
    token_usage_mock.completion_tokens = 500
    client.get_total_token_usage.return_value = token_usage_mock

    # Mock get_messages_from_simple to return messages as-is (identity function)
    client.get_messages_from_simple.side_effect = lambda msgs: msgs

    return client


@pytest.fixture
def mock_plan_generator() -> Mock:
    """Create mock plan generator."""
    return Mock()


@pytest.fixture
def mock_implementation_expander() -> Mock:
    """Create mock implementation expander."""
    return Mock()


@pytest.fixture
def sample_plan() -> AgentPlan:
    """Create sample plan."""
    return AgentPlan(
        sections=[
            SectionPlan(
                name="verse_1",
                start_bar=1,
                end_bar=16,
                section_role="verse",
                energy_level=40,
                templates=["gentle_sweep"],
                params={"intensity": "SMOOTH"},
                base_pose="AUDIENCE_CENTER",
                reasoning="Calm verse needs gentle movement",
            )
        ],
        overall_strategy="Simple plan for testing",
        template_variety_score=7,
        energy_alignment_score=8,
    )


@pytest.fixture
def sample_implementation() -> AgentImplementation:
    """Create sample implementation (Phase 5A schema: bars)."""
    return AgentImplementation(
        sections=[
            ImplementationSection(
                name="verse_1",
                plan_section_name="verse_1",
                start_bar=1,
                end_bar=8,
                template_id="gentle_sweep",
                params={"intensity": "SMOOTH"},
                base_pose="AUDIENCE_CENTER",
                targets=["ALL"],
                layer_priority=0,
            )
        ],
        total_duration_bars=8,
        quantization_applied=True,
        timing_precision="bar_aligned",
    )


@pytest.fixture
def failing_evaluation() -> Evaluation:
    """Create failing evaluation."""
    return Evaluation(
        story_overview="Test sequence with repetitive patterns that need more variety and energy adjustment",
        overall_score=65.0,
        category_scores=[
            CategoryScore(
                category="Template Variety",
                score=50,
                reasoning="Too repetitive",
                strengths=[],
                weaknesses=["Same template repeated"],
            ),
            CategoryScore(
                category="Energy Matching",
                score=65,  # Changed to < 70 to be included
                reasoning="Decent energy",
                strengths=["Good match in verse"],
                weaknesses=["Chorus too low energy"],
            ),
            CategoryScore(
                category="Musical Alignment",
                score=75,
                reasoning="Mostly aligned",
                strengths=["Good downbeat alignment"],
                weaknesses=[],
            ),
        ],
        summary="Needs more variety",
        actionable_feedback=["Vary templates more", "Increase chorus energy"],
        pass_threshold=False,
    )


@pytest.fixture
def plan_failure_analysis() -> FailureAnalysis:
    """Create plan-related failure analysis."""
    return FailureAnalysis(
        primary_issue="plan",
        failure_categories=["Template Variety"],
        root_cause="Template selection issues",
        fix_strategy="replan",
    )


@pytest.fixture
def impl_failure_analysis() -> FailureAnalysis:
    """Create implementation-related failure analysis."""
    return FailureAnalysis(
        primary_issue="implementation",
        failure_categories=["Musical Alignment"],
        root_cause="Timing issues",
        fix_strategy="refine_implementation",
    )


@pytest.fixture
def mock_song_features() -> dict[str, Any]:
    """Create mock song features."""
    return {
        "duration_s": 180.0,
        "tempo_bpm": 120.0,
        "time_signature": {"time_signature": "4/4"},
        "bars_s": [i * 2.0 for i in range(90)],  # 90 bars
        "beats_s": [i * 0.5 for i in range(360)],  # 360 beats
        "energy": {
            "times_s": [i * 0.1 for i in range(1800)],
            "phrase_level": [0.5 + (i % 10) * 0.05 for i in range(1800)],
            "peaks": [{"t_s": 50.0, "val": 0.9}],
            "stats": {"min": 0.2, "max": 0.95, "mean": 0.6},
        },
        "assumptions": {"beats_per_bar": 4},
    }


@pytest.fixture
def mock_template_metadata() -> list[dict[str, Any]]:
    """Create mock template metadata."""
    return [
        {
            "template_id": "gentle_sweep",
            "name": "Gentle Sweep",
            "category": "low_energy",
            "metadata": {
                "description": "Gentle sweeping movement",
                "energy_range": [10, 40],
                "recommended_sections": ["verse", "ambient"],
                "tags": ["smooth", "calm", "gentle"],
            },
            "step_count": 2,
        },
        {
            "template_id": "energetic_pulse",
            "name": "Energetic Pulse",
            "category": "high_energy",
            "metadata": {
                "description": "High energy pulsing",
                "energy_range": [70, 90],
                "recommended_sections": ["chorus", "drop"],
                "tags": ["energetic", "dynamic", "intense"],
            },
            "step_count": 3,
        },
    ]


class TestRefinementAgentInit:
    """Test RefinementAgent initialization."""

    def test_init(
        self,
        job_config: JobConfig,
        mock_openai_client: Mock,
        mock_plan_generator: Mock,
        mock_implementation_expander: Mock,
    ):
        """Test basic initialization."""
        agent = RefinementAgent(
            job_config=job_config,
            openai_client=mock_openai_client,
            plan_generator=mock_plan_generator,
            implementation_expander=mock_implementation_expander,
        )

        assert agent.job_config == job_config
        assert agent.openai_client == mock_openai_client
        assert agent.plan_generator == mock_plan_generator
        assert agent.implementation_expander == mock_implementation_expander
        assert agent.context_shaper is not None


class TestRefinementAgentReplanStrategy:
    """Test replan strategy."""

    def test_refine_with_replan_strategy(
        self,
        job_config: JobConfig,
        mock_openai_client: Mock,
        mock_plan_generator: Mock,
        mock_implementation_expander: Mock,
        sample_plan: AgentPlan,
        sample_implementation: AgentImplementation,
        failing_evaluation: Evaluation,
        plan_failure_analysis: FailureAnalysis,
        mock_song_features: dict[str, Any],
        mock_template_metadata: list[dict[str, Any]],
    ):
        """Test replan strategy is used for plan-related failures."""
        # Setup mock response with valid plan JSON
        mock_openai_client.generate_json.return_value = {
            "sections": [
                {
                    "name": "verse_1",
                    "start_bar": 1,
                    "end_bar": 16,
                    "section_role": "verse",
                    "energy_level": 80,
                    "templates": ["energetic_pulse"],
                    "params": {"intensity": "DRAMATIC"},
                    "base_pose": "AUDIENCE_CENTER",
                    "reasoning": "More variety",
                }
            ],
            "overall_strategy": "Improved plan",
            "template_variety_score": 9,
            "energy_alignment_score": 9,
        }

        agent = RefinementAgent(
            job_config=job_config,
            openai_client=mock_openai_client,
            plan_generator=mock_plan_generator,
            implementation_expander=mock_implementation_expander,
        )

        result = agent.refine(
            plan=sample_plan,
            implementation=sample_implementation,
            evaluation=failing_evaluation,
            failure_analysis=plan_failure_analysis,
            song_features=mock_song_features,
            seq_fingerprint={},
            template_metadata=mock_template_metadata,
        )

        assert result.success is True
        assert result.strategy == RefineStrategy.REPLAN
        assert result.plan is not None
        assert result.implementation is None
        assert mock_openai_client.generate_json.called

    def test_replan_includes_feedback_in_prompt(
        self,
        job_config: JobConfig,
        mock_openai_client: Mock,
        mock_plan_generator: Mock,
        mock_implementation_expander: Mock,
        sample_plan: AgentPlan,
        sample_implementation: AgentImplementation,
        failing_evaluation: Evaluation,
        plan_failure_analysis: FailureAnalysis,
        mock_song_features: dict[str, Any],
        mock_template_metadata: list[dict[str, Any]],
    ):
        """Test that replan prompt includes feedback."""
        mock_openai_client.generate_json.return_value = {
            "sections": [],
            "overall_strategy": "Test",
            "template_variety_score": 5,
            "energy_alignment_score": 5,
        }

        agent = RefinementAgent(
            job_config=job_config,
            openai_client=mock_openai_client,
            plan_generator=mock_plan_generator,
            implementation_expander=mock_implementation_expander,
        )

        agent.refine(
            plan=sample_plan,
            implementation=sample_implementation,
            evaluation=failing_evaluation,
            failure_analysis=plan_failure_analysis,
            song_features=mock_song_features,
            seq_fingerprint={},
            template_metadata=mock_template_metadata,
        )

        # Check that prompt includes feedback
        call_args = mock_openai_client.generate_json.call_args
        # call_args is (args, kwargs) tuple, messages is in kwargs
        assert call_args is not None
        kwargs = call_args.kwargs if hasattr(call_args, "kwargs") else call_args[1]
        user_message = kwargs["messages"][1]["content"]

        assert "65.0" in user_message  # Score
        assert "Template Variety" in user_message  # Failing category
        assert "Same template repeated" in user_message  # Issue
        assert "Vary templates more" in user_message  # Feedback

    def test_replan_failure_returns_error(
        self,
        job_config: JobConfig,
        mock_openai_client: Mock,
        mock_plan_generator: Mock,
        mock_implementation_expander: Mock,
        sample_plan: AgentPlan,
        sample_implementation: AgentImplementation,
        failing_evaluation: Evaluation,
        plan_failure_analysis: FailureAnalysis,
        mock_song_features: dict[str, Any],
        mock_template_metadata: list[dict[str, Any]],
    ):
        """Test replan failure handling."""
        mock_openai_client.generate_json.side_effect = Exception("API error")

        agent = RefinementAgent(
            job_config=job_config,
            openai_client=mock_openai_client,
            plan_generator=mock_plan_generator,
            implementation_expander=mock_implementation_expander,
        )

        result = agent.refine(
            plan=sample_plan,
            implementation=sample_implementation,
            evaluation=failing_evaluation,
            failure_analysis=plan_failure_analysis,
            song_features=mock_song_features,
            seq_fingerprint={},
            template_metadata=mock_template_metadata,
        )

        assert result.success is False
        assert result.strategy == RefineStrategy.REPLAN
        assert result.error is not None
        assert "API error" in result.error
        assert result.tokens_used == 0


class TestRefinementAgentRefineImplementationStrategy:
    """Test refine implementation strategy."""

    def test_refine_with_refine_impl_strategy(
        self,
        job_config: JobConfig,
        mock_openai_client: Mock,
        mock_plan_generator: Mock,
        mock_implementation_expander: Mock,
        sample_plan: AgentPlan,
        sample_implementation: AgentImplementation,
        failing_evaluation: Evaluation,
        impl_failure_analysis: FailureAnalysis,
        mock_song_features: dict[str, Any],
        mock_template_metadata: list[dict[str, Any]],
    ):
        """Test refine implementation strategy is used for impl-related failures."""
        # Setup mock response with valid implementation JSON (Phase 5A schema)
        mock_openai_client.generate_json.return_value = {
            "sections": [
                {
                    "name": "verse_1",
                    "plan_section_name": "verse_1",
                    "start_bar": 1,
                    "end_bar": 8,
                    "template_id": "gentle_sweep",
                    "params": {"intensity": "SMOOTH"},
                    "base_pose": "AUDIENCE_CENTER",
                    "targets": ["ALL"],
                    "layer_priority": 0,
                    "reasoning": "Test section",
                }
            ],
            "total_duration_bars": 8,
            "quantization_applied": True,
            "timing_precision": "bar_aligned",
        }

        agent = RefinementAgent(
            job_config=job_config,
            openai_client=mock_openai_client,
            plan_generator=mock_plan_generator,
            implementation_expander=mock_implementation_expander,
        )

        result = agent.refine(
            plan=sample_plan,
            implementation=sample_implementation,
            evaluation=failing_evaluation,
            failure_analysis=impl_failure_analysis,
            song_features=mock_song_features,
            seq_fingerprint={},
            template_metadata=mock_template_metadata,
        )

        assert result.success is True
        assert result.strategy == RefineStrategy.REFINE_IMPLEMENTATION
        assert result.plan is None
        assert result.implementation is not None
        assert mock_openai_client.generate_json.called

    def test_refine_impl_includes_original_implementation(
        self,
        job_config: JobConfig,
        mock_openai_client: Mock,
        mock_plan_generator: Mock,
        mock_implementation_expander: Mock,
        sample_plan: AgentPlan,
        sample_implementation: AgentImplementation,
        failing_evaluation: Evaluation,
        impl_failure_analysis: FailureAnalysis,
        mock_song_features: dict[str, Any],
        mock_template_metadata: list[dict[str, Any]],
    ):
        """Test that refine impl prompt includes original implementation."""
        mock_openai_client.generate_json.return_value = {
            "sections": [],
            "total_duration_bars": 1,  # Phase 5A: bars not ms
            "quantization_applied": False,
            "timing_precision": "raw",
        }

        agent = RefinementAgent(
            job_config=job_config,
            openai_client=mock_openai_client,
            plan_generator=mock_plan_generator,
            implementation_expander=mock_implementation_expander,
        )

        agent.refine(
            plan=sample_plan,
            implementation=sample_implementation,
            evaluation=failing_evaluation,
            failure_analysis=impl_failure_analysis,
            song_features=mock_song_features,
            seq_fingerprint={},
            template_metadata=mock_template_metadata,
        )

        # Check that prompt includes implementation details
        call_args = mock_openai_client.generate_json.call_args
        # call_args is (args, kwargs) tuple, messages is in kwargs
        assert call_args is not None
        kwargs = call_args.kwargs if hasattr(call_args, "kwargs") else call_args[1]
        user_message = kwargs["messages"][1]["content"]

        assert "65.0" in user_message  # Score
        assert "Musical Alignment" in user_message  # Failing category


class TestRefinementAgentFeedbackContext:
    """Test feedback context building."""

    def test_build_feedback_context(
        self,
        job_config: JobConfig,
        mock_openai_client: Mock,
        mock_plan_generator: Mock,
        mock_implementation_expander: Mock,
        failing_evaluation: Evaluation,
        plan_failure_analysis: FailureAnalysis,
    ):
        """Test feedback context construction."""
        agent = RefinementAgent(
            job_config=job_config,
            openai_client=mock_openai_client,
            plan_generator=mock_plan_generator,
            implementation_expander=mock_implementation_expander,
        )

        context = agent._build_feedback_context(
            evaluation=failing_evaluation,
            failure_analysis=plan_failure_analysis,
            focus="plan",
        )

        assert context["overall_score"] == 65.0
        assert "Template Variety" in context["failing_categories"]
        assert context["root_cause"] == "Template selection issues"
        assert "Vary templates more" in context["actionable_feedback"]
        assert len(context["category_details"]) > 0

        # Should only include low-scoring categories (<70)
        for detail in context["category_details"]:
            assert detail["score"] < 70

    def test_extract_issues(
        self,
        job_config: JobConfig,
        mock_openai_client: Mock,
        mock_plan_generator: Mock,
        mock_implementation_expander: Mock,
        failing_evaluation: Evaluation,
    ):
        """Test issue extraction from evaluation."""
        agent = RefinementAgent(
            job_config=job_config,
            openai_client=mock_openai_client,
            plan_generator=mock_plan_generator,
            implementation_expander=mock_implementation_expander,
        )

        issues = agent._extract_issues(failing_evaluation)

        assert len(issues) > 0
        assert "Same template repeated" in issues
        assert "Chorus too low energy" in issues

    def test_summarize_implementation(
        self,
        job_config: JobConfig,
        mock_openai_client: Mock,
        mock_plan_generator: Mock,
        mock_implementation_expander: Mock,
        sample_implementation: AgentImplementation,
    ):
        """Test implementation summarization."""
        agent = RefinementAgent(
            job_config=job_config,
            openai_client=mock_openai_client,
            plan_generator=mock_plan_generator,
            implementation_expander=mock_implementation_expander,
        )

        summary = agent._summarize_implementation(sample_implementation)

        assert summary["section_count"] == 1
        assert summary["total_duration_bars"] == 8  # Phase 5A: bars not ms
        assert len(summary["sections"]) == 1
        assert summary["sections"][0]["name"] == "verse_1"
        assert summary["sections"][0]["template_id"] == "gentle_sweep"


class TestRefinementAgentFullReplan:
    """Test full replan strategy."""

    def test_full_replan_strategy(
        self,
        job_config: JobConfig,
        mock_openai_client: Mock,
        mock_plan_generator: Mock,
        mock_implementation_expander: Mock,
        sample_plan: AgentPlan,
        sample_implementation: AgentImplementation,
        failing_evaluation: Evaluation,
        mock_song_features: dict[str, Any],
        mock_template_metadata: list[dict[str, Any]],
    ):
        """Test full replan strategy for severe failures."""
        # Create failure analysis with unknown strategy
        failure_analysis = FailureAnalysis(
            primary_issue="both",
            failure_categories=["Template Variety", "Musical Alignment"],
            root_cause="Multiple issues",
            fix_strategy="full_replan",
        )

        mock_openai_client.generate_json.return_value = {
            "sections": [],
            "overall_strategy": "Fresh start",
            "template_variety_score": 7,
            "energy_alignment_score": 7,
        }

        agent = RefinementAgent(
            job_config=job_config,
            openai_client=mock_openai_client,
            plan_generator=mock_plan_generator,
            implementation_expander=mock_implementation_expander,
        )

        result = agent.refine(
            plan=sample_plan,
            implementation=sample_implementation,
            evaluation=failing_evaluation,
            failure_analysis=failure_analysis,
            song_features=mock_song_features,
            seq_fingerprint={},
            template_metadata=mock_template_metadata,
        )

        assert result.success is True
        assert result.strategy == RefineStrategy.FULL_REPLAN
        assert result.plan is not None


class TestRefinementResult:
    """Test RefinementResult dataclass."""

    def test_refinement_result_success(self):
        """Test successful refinement result."""
        plan = Mock()
        result = RefinementResult(
            success=True,
            strategy=RefineStrategy.REPLAN,
            plan=plan,
            implementation=None,
            error=None,
            tokens_used=5000,
        )

        assert result.success is True
        assert result.strategy == RefineStrategy.REPLAN
        assert result.plan is not None
        assert result.implementation is None
        assert result.error is None
        assert result.tokens_used == 5000

    def test_refinement_result_failure(self):
        """Test failed refinement result."""
        result = RefinementResult(
            success=False,
            strategy=RefineStrategy.REPLAN,
            plan=None,
            implementation=None,
            error="API error",
            tokens_used=0,
        )

        assert result.success is False
        assert result.error == "API error"
        assert result.tokens_used == 0
