"""Unit tests for PlanGenerator."""

import json
from unittest.mock import Mock

import pytest

from blinkb0t.core.agents.moving_heads import (
    PlanGenerationResult,
    PlanGenerator,
    Stage,
)
from blinkb0t.core.agents.moving_heads.models_agent_plan import AgentPlan


class TestPlanGenerator:
    """Test PlanGenerator class."""

    @pytest.fixture
    def mock_openai_client(self) -> Mock:
        """Mock OpenAI client."""
        client = Mock()

        # Mock successful response - generate_json returns dict directly
        client.generate_json.return_value = {
            "sections": [
                {
                    "name": "verse_1",
                    "start_bar": 1,
                    "end_bar": 16,
                    "section_role": "verse",
                    "energy_level": 30,
                    "templates": ["gentle_sweep_breathe"],  # Planner selects templates (list)
                    "params": {"intensity": "SMOOTH"},
                    "base_pose": "AUDIENCE_CENTER",
                    "reasoning": "Low energy verse",
                }
            ],
            "overall_strategy": "Build from verses to chorus",
            "template_variety_score": 8,
            "energy_alignment_score": 9,
        }

        # Mock token usage tracking
        token_usage_mock = Mock()
        token_usage_mock.total_tokens = 1000
        token_usage_mock.prompt_tokens = 500
        token_usage_mock.completion_tokens = 500
        client.get_total_token_usage.return_value = token_usage_mock

        # Mock get_messages_from_simple (identity function)
        client.get_messages_from_simple.side_effect = lambda msgs: msgs

        # Mock get_simple_messages (for original_messages)
        client.get_simple_messages.return_value = []

        return client

    @pytest.fixture
    def mock_job_config(self) -> Mock:
        """Mock job config."""
        config = Mock()
        config.agent = Mock()
        config.agent.plan_agent = Mock()
        config.agent.plan_agent.model = "gpt-5.2"
        config.agent.plan_agent.temperature = 0.7
        config.agent.plan_agent.max_tokens = 8000
        config.planner_features = Mock()
        config.planner_features.enable_shutter = False
        config.planner_features.enable_color = False
        config.planner_features.enable_gobo = False
        return config

    @pytest.fixture
    def generator(self, mock_job_config: Mock, mock_openai_client: Mock) -> PlanGenerator:
        """Create PlanGenerator instance."""
        return PlanGenerator(job_config=mock_job_config, openai_client=mock_openai_client)

    @pytest.fixture
    def mock_song_features(self) -> dict:
        """Create mock song features."""
        return {
            "duration_s": 180.0,
            "tempo_bpm": 120.0,
            "time_signature": {"time_signature": "4/4"},
            "bars_s": [i * 2.0 for i in range(90)],
            "beats_s": [i * 0.5 for i in range(360)],
            "energy": {
                "times_s": [i * 0.1 for i in range(1800)],
                "phrase_level": [0.5 + (i % 10) * 0.05 for i in range(1800)],
                "peaks": [{"t_s": 50.0, "val": 0.9}],
                "stats": {"min": 0.2, "max": 0.95, "mean": 0.6},
            },
            "assumptions": {"beats_per_bar": 4},
        }

    @pytest.fixture
    def mock_template_metadata(self) -> list[dict]:
        """Create mock template metadata."""
        return [
            {
                "template_id": "gentle_sweep_breathe",
                "name": "Gentle Sweep with Breathing Dimmer",
                "category": "low_energy",
                "metadata": {
                    "description": "Gentle movement",
                    "energy_range": [10, 40],
                    "recommended_sections": ["verse", "ambient"],
                    "tags": ["gentle", "sweep", "breathe"],
                },
                "step_count": 2,
            }
        ]

    def test_generate_plan_success(
        self,
        generator: PlanGenerator,
        mock_song_features: dict,
        mock_template_metadata: list,
    ) -> None:
        """Test successful plan generation."""
        result = generator.generate_plan(
            song_features=mock_song_features,
            seq_fingerprint={},
            template_metadata=mock_template_metadata,
        )

        assert isinstance(result, PlanGenerationResult)
        assert result.success
        assert result.plan is not None
        assert isinstance(result.plan, AgentPlan)
        assert len(result.plan.sections) > 0
        assert result.tokens_used > 0
        assert result.retries == 0
        assert result.error is None

    def test_generate_plan_with_fingerprint(
        self,
        generator: PlanGenerator,
        mock_song_features: dict,
        mock_template_metadata: list,
    ) -> None:
        """Test plan generation with sequence fingerprint."""
        seq_fingerprint = {
            "existing_effects": {"total_count": 10, "by_type": {"rgb": 5}},
            "effect_coverage": {"pan_tilt_pct": 0, "dimmer_pct": 0},
        }

        result = generator.generate_plan(
            song_features=mock_song_features,
            seq_fingerprint=seq_fingerprint,
            template_metadata=mock_template_metadata,
        )

        assert result.success
        assert result.plan is not None

    def test_prompt_building(self, generator: PlanGenerator, mock_song_features: dict) -> None:
        """Test prompt construction."""
        # Shape context first
        shaped_context = generator.context_shaper.shape_for_stage(
            stage=Stage.PLAN,
            song_features=mock_song_features,
        )

        prompt = generator._build_prompt(shaped_context.data)

        # Should contain key sections
        assert "Song Information" in prompt
        assert "Energy Profile" in prompt
        assert "Template Library" in prompt  # Fixed: actual heading in prompt
        assert "Your Task" in prompt
        assert "Output Schema" in prompt

    def test_parse_valid_response(self, generator: PlanGenerator) -> None:
        """Test parsing valid LLM response."""
        response_json = {
            "sections": [
                {
                    "name": "test",
                    "start_bar": 1,
                    "end_bar": 8,
                    "section_role": "verse",
                    "energy_level": 50,
                    "templates": ["test_template"],  # Planner selects templates (list)
                    "params": {},
                    "base_pose": "AUDIENCE_CENTER",
                    "reasoning": "Test",
                }
            ],
            "overall_strategy": "Test strategy",
            "template_variety_score": 5,
            "energy_alignment_score": 5,
        }

        plan = generator._parse_response(json.dumps(response_json))

        assert isinstance(plan, AgentPlan)
        assert len(plan.sections) == 1
        assert plan.overall_strategy == "Test strategy"

    def test_retry_on_invalid_json(
        self,
        mock_job_config: Mock,
        mock_openai_client: Mock,
        mock_song_features: dict,
        mock_template_metadata: list,
    ) -> None:
        """Test retry logic on invalid JSON."""
        # First call returns invalid structure (will fail Pydantic validation)
        invalid_response = {"invalid": "structure"}

        # Second call succeeds
        valid_response = {
            "sections": [
                {
                    "name": "test",
                    "start_bar": 1,
                    "end_bar": 8,
                    "section_role": "verse",
                    "energy_level": 50,
                    "templates": ["test_template"],
                    "params": {},
                    "base_pose": "AUDIENCE_CENTER",
                    "reasoning": "Test",
                }
            ],
            "overall_strategy": "Test",
            "template_variety_score": 5,
            "energy_alignment_score": 5,
        }

        mock_openai_client.generate_json.side_effect = [
            invalid_response,
            valid_response,
        ]

        generator = PlanGenerator(job_config=mock_job_config, openai_client=mock_openai_client)

        result = generator.generate_plan(
            song_features=mock_song_features,
            seq_fingerprint={},
            template_metadata=mock_template_metadata,
        )

        assert result.success
        assert result.retries == 1

    def test_max_retries_exceeded(
        self,
        mock_job_config: Mock,
        mock_openai_client: Mock,
        mock_song_features: dict,
        mock_template_metadata: list,
    ) -> None:
        """Test max retries exceeded."""
        # All calls return invalid structure
        invalid_response = {"invalid": "structure"}

        mock_openai_client.generate_json.return_value = invalid_response

        generator = PlanGenerator(job_config=mock_job_config, openai_client=mock_openai_client)

        result = generator.generate_plan(
            song_features=mock_song_features,
            seq_fingerprint={},
            template_metadata=mock_template_metadata,
        )

        assert not result.success
        assert result.plan is None
        assert result.error is not None
        assert "Failed to parse plan" in result.error

    def test_format_energy_summary(self, generator: PlanGenerator) -> None:
        """Test energy summary formatting."""
        energy = {
            "curve": [{"t_s": 0.0, "val": 0.5}] * 10,
            "peaks": [{"t_s": 50.0, "val": 0.9}],
            "stats": {"min": 0.2, "max": 0.95, "mean": 0.6},
        }

        summary = generator._format_energy_summary(energy)

        assert "Range: 0.20 - 0.95" in summary
        assert "Average: 0.60" in summary
        assert "Peak moments" in summary

    def test_format_energy_summary_empty(self, generator: PlanGenerator) -> None:
        """Test energy summary with no data."""
        summary = generator._format_energy_summary({})

        assert "No energy data available" in summary

    def test_format_template_library(self, generator: PlanGenerator) -> None:
        """Test template library formatting."""
        templates = [
            {
                "template_id": "test",
                "name": "Test Template",
                "category": "low_energy",
                "description": "A test",
                "energy_range": [10, 40],
                "recommended_sections": ["verse"],
                "tags": ["test"],
                "step_count": 2,
            }
        ]

        formatted = generator._format_template_library(templates)

        assert "LOW_ENERGY" in formatted
        assert "test" in formatted
        assert "Test Template" in formatted

    def test_format_fingerprint_summary(self, generator: PlanGenerator) -> None:
        """Test fingerprint summary formatting."""
        fingerprint = {
            "existing_effects": {
                "total_count": 10,
                "by_type": {"rgb": 5, "matrix": 5},
            },
            "effect_coverage": {"pan_tilt_pct": 0, "dimmer_pct": 0},
        }

        summary = generator._format_fingerprint_summary(fingerprint)

        assert "Existing effects: 10" in summary
        assert "rgb: 5" in summary
        assert "matrix: 5" in summary

    def test_add_retry_context(self, generator: PlanGenerator) -> None:
        """Test adding retry context."""
        original = "Original prompt"
        error = "Test error"

        result = generator._add_retry_context(original, error)

        assert "Original prompt" in result
        assert "RETRY NOTICE" in result
        assert "Test error" in result
