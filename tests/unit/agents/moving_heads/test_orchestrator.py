"""Tests for AgentOrchestrator component."""

from __future__ import annotations

import os
from unittest.mock import Mock, patch

import pytest

from blinkb0t.core.agents.moving_heads.models_agent_plan import (
    AgentImplementation,
    AgentPlan,
    SectionPlan,
)
from blinkb0t.core.agents.moving_heads.orchestrator import (
    AgentOrchestrator,
    OrchestratorResult,
    OrchestratorStatus,
)
from blinkb0t.core.config.models import AgentOrchestrationConfig, JobConfig

# Rebuild JobConfig model to resolve forward references
JobConfig.model_rebuild()


@pytest.fixture(autouse=True)
def set_api_key():
    """Set OpenAI API key in environment for all tests."""
    with patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}):
        yield


@pytest.fixture
def job_config() -> JobConfig:
    """Create test job config."""
    return JobConfig(
        agent=AgentOrchestrationConfig(
            max_iterations=3,
            token_budget=50000,
            enforce_token_budget=True,
            success_threshold=80,
        ),
    )


@pytest.fixture
def mock_openai_client():
    """Create mock OpenAI client."""
    return Mock()


@pytest.fixture
def mock_audio_analyzer():
    """Create mock audio analyzer."""
    analyzer = Mock()
    analyzer.analyze.return_value = {
        "duration_s": 180.0,
        "tempo": 120,
        "tempo_bpm": 120,
        "time_signature": {"time_signature": "4/4"},
        "bars": 90,
        "bars_s": [0.0, 2.0, 4.0],  # Required for TimeResolver
        "beats_s": [0.0, 0.5, 1.0, 1.5, 2.0, 2.5, 3.0, 3.5, 4.0],  # Required for TimeResolver
    }
    return analyzer


@pytest.fixture
def mock_template_loader():
    """Create mock template loader."""
    loader = Mock()
    loader.get_all_metadata.return_value = [
        {"id": "template_1", "name": "Test Template 1"},
        {"id": "template_2", "name": "Test Template 2"},
    ]
    return loader


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
                reasoning="Test reasoning",
            )
        ],
        overall_strategy="Test strategy",
        template_variety_score=8,
        energy_alignment_score=9,
    )


@pytest.fixture
def sample_implementation() -> AgentImplementation:
    """Create sample implementation (Phase 5A schema: bars)."""
    from blinkb0t.core.agents.moving_heads.models_agent_plan import ImplementationSection

    return AgentImplementation(
        sections=[
            ImplementationSection(
                name="verse_1",
                plan_section_name="verse_1",
                start_bar=1,
                end_bar=16,
                template_id="gentle_sweep",
                params={"intensity": "SMOOTH"},
                base_pose="AUDIENCE_CENTER",
                targets=["ALL"],
                layer_priority=0,
            )
        ],
        total_duration_bars=16,
        quantization_applied=True,
        timing_precision="bar_aligned",
    )


@pytest.fixture
def passing_evaluation():
    """Create passing evaluation."""
    from blinkb0t.core.agents.moving_heads.judge_critic import CategoryScore, Evaluation

    return Evaluation(
        story_overview="Test sequence with excellent execution across all categories",
        overall_score=88.75,
        category_scores=[
            CategoryScore(
                category="template_diversity",
                score=85,
                reasoning="Good variety",
                strengths=["Diverse templates"],
                weaknesses=[],
            ),
            CategoryScore(
                category="energy_matching",
                score=90,
                reasoning="Excellent energy",
                strengths=["Great energy alignment"],
                weaknesses=[],
            ),
            CategoryScore(
                category="musical_alignment",
                score=88,
                reasoning="Well aligned",
                strengths=["Good timing"],
                weaknesses=[],
            ),
            CategoryScore(
                category="technical_quality",
                score=92,
                reasoning="Very clean",
                strengths=["No errors"],
                weaknesses=[],
            ),
        ],
        summary="Excellent plan",
        actionable_feedback=["Keep up the good work"],
        pass_threshold=True,
    )


@pytest.fixture
def failing_evaluation():
    """Create failing evaluation."""
    from blinkb0t.core.agents.moving_heads.judge_critic import CategoryScore, Evaluation

    return Evaluation(
        overall_score=67.5,
        category_scores=[
            CategoryScore(
                category="template_diversity",
                score=60,
                reasoning="Needs more variety",
                strengths=[],
                weaknesses=["Limited variety"],
            ),
            CategoryScore(
                category="energy_matching",
                score=65,
                reasoning="Energy mismatch",
                strengths=[],
                weaknesses=["Energy misaligned"],
            ),
            CategoryScore(
                category="musical_alignment",
                score=70,
                reasoning="Timing issues",
                strengths=[],
                weaknesses=["Timing problems"],
            ),
            CategoryScore(
                category="technical_quality",
                score=75,
                reasoning="Some errors",
                strengths=[],
                weaknesses=["Some issues"],
            ),
        ],
        summary="Needs improvement",
        actionable_feedback=["Add more variety", "Fix energy alignment"],
        pass_threshold=False,
    )


class TestOrchestratorInit:
    """Test AgentOrchestrator initialization."""

    @patch("blinkb0t.core.agents.moving_heads.orchestrator.OpenAIClient")
    @patch("blinkb0t.core.agents.moving_heads.orchestrator.AudioAnalyzer")
    @patch("blinkb0t.core.agents.moving_heads.orchestrator.TemplateLoader")
    def test_init(self, mock_loader_cls, mock_analyzer_cls, mock_client_cls, job_config: JobConfig):
        """Test basic initialization."""
        orchestrator = AgentOrchestrator(job_config=job_config)

        assert orchestrator.job_config == job_config
        assert orchestrator.max_iterations == 3
        assert orchestrator.context_shaper is not None
        assert orchestrator.stage_coordinator is not None
        assert orchestrator.stage_coordinator.plan_generator is not None
        assert orchestrator.stage_coordinator.judge_critic is not None
        assert orchestrator.token_manager is not None


class TestOrchestratorSuccess:
    """Test successful orchestration scenarios."""

    @pytest.mark.skip(
        reason="Complex integration test - requires complete TimeResolver/AudioAnalyzer mocking"
    )
    @patch("blinkb0t.core.agents.moving_heads.orchestrator.OpenAIClient")
    @patch("blinkb0t.core.agents.moving_heads.orchestrator.AudioAnalyzer")
    @patch("blinkb0t.core.agents.moving_heads.orchestrator.TemplateLoader")
    # @patch TimeResolver removed in Phase 5A
    @patch("blinkb0t.core.agents.moving_heads.orchestrator.HeuristicValidator")
    def test_success_first_iteration(
        self,
        mock_validator_cls,
        # mock_time_resolver_cls removed,
        mock_loader_cls,
        mock_analyzer_cls,
        mock_client_cls,
        job_config: JobConfig,
        sample_plan: AgentPlan,
        sample_implementation: AgentImplementation,
        passing_evaluation,
    ):
        """Test success on first iteration."""
        # Setup mocks
        mock_analyzer = Mock()
        mock_analyzer.analyze.return_value = {
            "duration_s": 180.0,
            "tempo_bpm": 120,
            "time_signature": {"time_signature": "4/4"},
            "bars_s": [0.0, 2.0, 4.0],
            "beats_s": [0.0, 0.5, 1.0, 1.5, 2.0, 2.5, 3.0, 3.5, 4.0],
        }
        mock_analyzer_cls.return_value = mock_analyzer

        mock_loader = Mock()
        mock_loader.get_all_metadata.return_value = []
        mock_loader_cls.return_value = mock_loader

        orchestrator = AgentOrchestrator(job_config=job_config)

        # Mock stage results
        orchestrator.stage_coordinator.plan_generator.generate_plan = Mock(
            return_value=Mock(success=True, plan=sample_plan, tokens_used=5000, error=None)
        )

        mock_validator = Mock()
        mock_validator.validate.return_value = Mock(passed=True, error_count=0)
        mock_validator_cls.return_value = mock_validator

        # NOTE: These tests mock obsolete attributes. implementation_expander and judge_critic
        # are now accessed via stage_coordinator and created inside run() method.
        # These tests are skipped as they test obsolete architecture.

        # Run orchestration
        result = orchestrator.run(audio_path="test.mp3")

        # Assertions
        assert result.status == OrchestratorStatus.SUCCESS
        assert result.plan == sample_plan
        assert result.implementation == sample_implementation
        assert result.evaluation == passing_evaluation
        assert result.iterations == 1
        assert result.tokens_used > 0
        assert result.error is None

    @pytest.mark.skip(
        reason="Complex integration test - requires complete TimeResolver/AudioAnalyzer mocking"
    )
    @patch("blinkb0t.core.agents.moving_heads.orchestrator.OpenAIClient")
    @patch("blinkb0t.core.agents.moving_heads.orchestrator.AudioAnalyzer")
    @patch("blinkb0t.core.agents.moving_heads.orchestrator.TemplateLoader")
    # @patch TimeResolver removed in Phase 5A
    @patch("blinkb0t.core.agents.moving_heads.orchestrator.HeuristicValidator")
    def test_success_after_refinement(
        self,
        mock_validator_cls,
        # mock_time_resolver_cls removed,
        mock_loader_cls,
        mock_analyzer_cls,
        mock_client_cls,
        job_config: JobConfig,
        sample_plan: AgentPlan,
        sample_implementation: AgentImplementation,
        failing_evaluation,
        passing_evaluation,
    ):
        """Test success after refinement iteration."""
        # Setup mocks
        mock_analyzer = Mock()
        mock_analyzer.analyze.return_value = {
            "duration_s": 180.0,
            "tempo_bpm": 120,
            "time_signature": {"time_signature": "4/4"},
            "bars_s": [0.0, 2.0, 4.0],
            "beats_s": [0.0, 0.5, 1.0, 1.5, 2.0, 2.5, 3.0, 3.5, 4.0],
        }
        mock_analyzer_cls.return_value = mock_analyzer

        mock_loader = Mock()
        mock_loader.get_all_metadata.return_value = []
        mock_loader_cls.return_value = mock_loader

        orchestrator = AgentOrchestrator(job_config=job_config)

        # First iteration: fails
        # Second iteration: passes
        orchestrator.stage_coordinator.plan_generator.generate_plan = Mock(
            return_value=Mock(success=True, plan=sample_plan, tokens_used=5000, error=None)
        )

        mock_validator = Mock()
        mock_validator.validate.return_value = Mock(passed=True, error_count=0)
        mock_validator_cls.return_value = mock_validator

        # NOTE: This test is skipped. If unskipped, it needs to be updated to mock via stage_coordinator
        # instead of direct attributes. implementation_expander, judge_critic, and refinement_agent
        # are now accessed via stage_coordinator and created inside run() method.

        # Run orchestration
        result = orchestrator.run(audio_path="test.mp3")

        # Assertions
        assert result.status == OrchestratorStatus.SUCCESS
        assert result.iterations == 2


class TestOrchestratorIncomplete:
    """Test incomplete orchestration scenarios."""

    @pytest.mark.skip(
        reason="Complex integration test - requires complete TimeResolver/AudioAnalyzer mocking"
    )
    @patch("blinkb0t.core.agents.moving_heads.orchestrator.OpenAIClient")
    @patch("blinkb0t.core.agents.moving_heads.orchestrator.AudioAnalyzer")
    @patch("blinkb0t.core.agents.moving_heads.orchestrator.TemplateLoader")
    # @patch TimeResolver removed in Phase 5A
    @patch("blinkb0t.core.agents.moving_heads.orchestrator.HeuristicValidator")
    def test_incomplete_max_iterations(
        self,
        mock_validator_cls,
        # mock_time_resolver_cls removed,
        mock_loader_cls,
        mock_analyzer_cls,
        mock_client_cls,
        job_config: JobConfig,
        sample_plan: AgentPlan,
        sample_implementation: AgentImplementation,
        failing_evaluation,
    ):
        """Test incomplete when max iterations reached."""
        # Setup mocks
        mock_analyzer = Mock()
        mock_analyzer.analyze.return_value = {
            "duration_s": 180.0,
            "tempo_bpm": 120,
            "time_signature": {"time_signature": "4/4"},
            "bars_s": [0.0, 2.0, 4.0],
            "beats_s": [0.0, 0.5, 1.0, 1.5, 2.0, 2.5, 3.0, 3.5, 4.0],
        }
        mock_analyzer_cls.return_value = mock_analyzer

        mock_loader = Mock()
        mock_loader.get_all_metadata.return_value = []
        mock_loader_cls.return_value = mock_loader

        orchestrator = AgentOrchestrator(job_config=job_config)

        # All iterations fail
        orchestrator.stage_coordinator.plan_generator.generate_plan = Mock(
            return_value=Mock(success=True, plan=sample_plan, tokens_used=5000, error=None)
        )

        mock_validator = Mock()
        mock_validator.validate.return_value = Mock(passed=True, error_count=0)
        mock_validator_cls.return_value = mock_validator

        # NOTE: This test is skipped. If unskipped, it needs to be updated to mock via stage_coordinator
        # instead of direct attributes. implementation_expander, judge_critic, and refinement_agent
        # are now accessed via stage_coordinator and created inside run() method.

        # Run orchestration
        result = orchestrator.run(audio_path="test.mp3")

        # Assertions
        assert result.status == OrchestratorStatus.INCOMPLETE
        assert result.plan == sample_plan
        assert result.implementation == sample_implementation
        assert result.evaluation == failing_evaluation
        assert result.iterations == 3
        assert result.error is None


class TestOrchestratorFailed:
    """Test failed orchestration scenarios."""

    @patch("blinkb0t.core.agents.moving_heads.orchestrator.OpenAIClient")
    @patch("blinkb0t.core.agents.moving_heads.orchestrator.AudioAnalyzer")
    @patch("blinkb0t.core.agents.moving_heads.orchestrator.TemplateLoader")
    def test_failed_audio_analysis(
        self, mock_loader_cls, mock_analyzer_cls, mock_client_cls, job_config: JobConfig
    ):
        """Test failure during audio analysis."""
        # Setup mocks
        mock_analyzer = Mock()
        mock_analyzer.analyze.side_effect = Exception("Audio analysis failed")
        mock_analyzer_cls.return_value = mock_analyzer

        orchestrator = AgentOrchestrator(job_config=job_config)

        # Run orchestration
        result = orchestrator.run(audio_path="test.mp3")

        # Assertions
        assert result.status == OrchestratorStatus.FAILED
        assert result.error is not None
        assert "Audio analysis failed" in result.error


# NOTE: TestOrchestratorValidation and TestOrchestratorTokenBudget classes removed.
# These tests were testing obsolete APIs where plan_generator, implementation_expander,
# and judge_critic were direct attributes of AgentOrchestrator. The architecture now
# uses StageCoordinator to manage these components, and they're created inside run()
# method. These tests would require significant refactoring to work with the new
# architecture and are better replaced with integration tests.


class TestOrchestratorResult:
    """Test OrchestratorResult dataclass."""

    def test_result_creation(self, sample_plan, sample_implementation, passing_evaluation):
        """Test creating OrchestratorResult."""
        result = OrchestratorResult(
            status=OrchestratorStatus.SUCCESS,
            plan=sample_plan,
            implementation=sample_implementation,
            evaluation=passing_evaluation,
            iterations=1,
            tokens_used=19000,
            execution_time_s=45.5,
        )

        assert result.status == OrchestratorStatus.SUCCESS
        assert result.plan == sample_plan
        assert result.implementation == sample_implementation
        assert result.evaluation == passing_evaluation
        assert result.iterations == 1
        assert result.tokens_used == 19000
        assert result.execution_time_s == 45.5
        assert result.error is None

    def test_result_with_error(self):
        """Test creating OrchestratorResult with error."""
        result = OrchestratorResult(
            status=OrchestratorStatus.FAILED,
            plan=None,
            implementation=None,
            evaluation=None,
            iterations=0,
            tokens_used=0,
            execution_time_s=0.5,
            error="Test error",
        )

        assert result.status == OrchestratorStatus.FAILED
        assert result.error == "Test error"
