"""Tests for v2 prompt templates.

These tests verify that the v2 prompts for the template-driven paradigm
are correctly structured and can be loaded.
"""

from pathlib import Path

import pytest


class TestV2PromptsExist:
    """Test that all v2 prompt files exist."""

    @pytest.fixture
    def prompts_dir(self) -> Path:
        """Get the v2 prompts directory."""
        return Path(__file__).parent.parent.parent.parent.parent / (
            "packages/blinkb0t/core/agents/moving_heads/prompts/v2"
        )

    def test_plan_system_prompt_exists(self, prompts_dir: Path) -> None:
        """Test plan_system.txt exists."""
        path = prompts_dir / "plan_system.txt"
        assert path.exists(), f"Missing: {path}"
        content = path.read_text()
        assert "template" in content.lower()
        assert "categorical" in content.lower() or "selection" in content.lower()

    def test_plan_user_prompt_exists(self, prompts_dir: Path) -> None:
        """Test plan_user.txt exists."""
        path = prompts_dir / "plan_user.txt"
        assert path.exists(), f"Missing: {path}"
        content = path.read_text()
        # Should have template variables
        assert "{bar_count}" in content
        assert "{template_library}" in content

    def test_judge_system_prompt_exists(self, prompts_dir: Path) -> None:
        """Test judge_system.txt exists."""
        path = prompts_dir / "judge_system.txt"
        assert path.exists(), f"Missing: {path}"
        content = path.read_text()
        assert "evaluation" in content.lower() or "judge" in content.lower()

    def test_judge_user_prompt_exists(self, prompts_dir: Path) -> None:
        """Test judge_user.txt exists."""
        path = prompts_dir / "judge_user.txt"
        assert path.exists(), f"Missing: {path}"

    def test_refinement_replan_prompt_exists(self, prompts_dir: Path) -> None:
        """Test refinement_replan.txt exists."""
        path = prompts_dir / "refinement_replan.txt"
        assert path.exists(), f"Missing: {path}"

    def test_implementation_system_prompt_exists(self, prompts_dir: Path) -> None:
        """Test implementation_system.txt exists."""
        path = prompts_dir / "implementation_system.txt"
        assert path.exists(), f"Missing: {path}"

    def test_implementation_user_prompt_exists(self, prompts_dir: Path) -> None:
        """Test implementation_user.txt exists."""
        path = prompts_dir / "implementation_user.txt"
        assert path.exists(), f"Missing: {path}"

    def test_refinement_implementation_prompt_exists(self, prompts_dir: Path) -> None:
        """Test refinement_implementation.txt exists."""
        path = prompts_dir / "refinement_implementation.txt"
        assert path.exists(), f"Missing: {path}"


class TestV2PromptContent:
    """Test v2 prompt content is simplified for template paradigm."""

    @pytest.fixture
    def prompts_dir(self) -> Path:
        """Get the v2 prompts directory."""
        return Path(__file__).parent.parent.parent.parent.parent / (
            "packages/blinkb0t/core/agents/moving_heads/prompts/v2"
        )

    def test_plan_system_no_layering(self, prompts_dir: Path) -> None:
        """Test plan_system.txt doesn't have complex layering rules."""
        path = prompts_dir / "plan_system.txt"
        content = path.read_text().lower()
        # Should not have 2-3 template layering rules
        assert "2+ templates" not in content
        assert "3 templates" not in content

    def test_plan_system_has_preset_info(self, prompts_dir: Path) -> None:
        """Test plan_system.txt mentions presets."""
        path = prompts_dir / "plan_system.txt"
        content = path.read_text().lower()
        assert "preset" in content

    def test_judge_system_simplified_categories(self, prompts_dir: Path) -> None:
        """Test judge_system.txt has simplified evaluation categories."""
        path = prompts_dir / "judge_system.txt"
        content = path.read_text()
        # Should have simplified categories (5 vs 8)
        # Check for key categories
        assert "Energy Alignment" in content
        assert "Template Variety" in content


class TestV2PromptVariables:
    """Test that v2 prompts have correct template variables."""

    @pytest.fixture
    def prompts_dir(self) -> Path:
        """Get the v2 prompts directory."""
        return Path(__file__).parent.parent.parent.parent.parent / (
            "packages/blinkb0t/core/agents/moving_heads/prompts/v2"
        )

    def test_plan_user_has_required_variables(self, prompts_dir: Path) -> None:
        """Test plan_user.txt has all required template variables."""
        path = prompts_dir / "plan_user.txt"
        content = path.read_text()

        required_vars = [
            "{duration_s}",
            "{tempo_bpm}",
            "{bar_count}",
            "{template_library}",
            "{json_schema}",
        ]
        for var in required_vars:
            assert var in content, f"Missing variable: {var}"

    def test_judge_user_has_required_variables(self, prompts_dir: Path) -> None:
        """Test judge_user.txt has required template variables."""
        path = prompts_dir / "judge_user.txt"
        content = path.read_text()

        required_vars = [
            "{pass_threshold}",
            "{json_schema}",
        ]
        for var in required_vars:
            assert var in content, f"Missing variable: {var}"


class TestLLMChoreographyPlanSchema:
    """Test that LLMChoreographyPlan can generate JSON schema."""

    def test_schema_generation(self) -> None:
        """Test that schema can be generated from LLMChoreographyPlan."""
        from blinkb0t.core.agents.moving_heads.models_llm_plan import LLMChoreographyPlan
        from blinkb0t.core.agents.schema_utils import get_json_schema_example

        schema = get_json_schema_example(LLMChoreographyPlan)
        assert "sections" in schema
        assert "overall_strategy" in schema

    def test_schema_has_section_selection(self) -> None:
        """Test schema includes SectionSelection fields."""
        from blinkb0t.core.agents.moving_heads.models_llm_plan import LLMChoreographyPlan
        from blinkb0t.core.agents.schema_utils import get_json_schema_example

        schema = get_json_schema_example(LLMChoreographyPlan)
        assert "template_id" in schema
        assert "preset_id" in schema
