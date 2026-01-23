"""Tests for moving heads prompt packs."""

from pathlib import Path

import pytest

from blinkb0t.core.agents.prompts import PromptPackLoader, PromptRenderer

PROMPTS_BASE = (
    Path(__file__).parent.parent.parent.parent.parent.parent
    / "packages"
    / "blinkb0t"
    / "core"
    / "agents"
    / "sequencer"
    / "moving_heads"
    / "prompts"
)


@pytest.fixture
def prompt_loader():
    """Create prompt loader."""
    return PromptPackLoader(base_path=PROMPTS_BASE)


@pytest.fixture
def renderer():
    """Create prompt renderer."""
    return PromptRenderer()


def test_planner_prompts_exist():
    """Test planner prompt files exist."""
    planner_dir = PROMPTS_BASE / "planner"
    assert planner_dir.exists()
    assert (planner_dir / "system.j2").exists()
    assert (planner_dir / "user.j2").exists()


def test_validator_prompts_exist():
    """Test validator prompt files exist."""
    validator_dir = PROMPTS_BASE / "validator"
    assert validator_dir.exists()
    assert (validator_dir / "system.j2").exists()
    assert (validator_dir / "user.j2").exists()


def test_judge_prompts_exist():
    """Test judge prompt files exist."""
    judge_dir = PROMPTS_BASE / "judge"
    assert judge_dir.exists()
    assert (judge_dir / "system.j2").exists()
    assert (judge_dir / "user.j2").exists()


def test_load_planner_prompts(prompt_loader):
    """Test loading planner prompts."""
    prompts = prompt_loader.load("planner")

    assert "system" in prompts
    assert "user" in prompts
    assert len(prompts["system"]) > 0
    assert len(prompts["user"]) > 0


def test_load_validator_prompts(prompt_loader):
    """Test loading validator prompts."""
    prompts = prompt_loader.load("validator")

    assert "system" in prompts
    assert "user" in prompts
    assert len(prompts["system"]) > 0
    assert len(prompts["user"]) > 0


def test_load_judge_prompts(prompt_loader):
    """Test loading judge prompts."""
    prompts = prompt_loader.load("judge")

    assert "system" in prompts
    assert "user" in prompts
    assert len(prompts["system"]) > 0
    assert len(prompts["user"]) > 0


def test_render_planner_user_prompt(prompt_loader, renderer):
    """Test rendering planner user prompt with variables."""
    prompts = prompt_loader.load("planner")

    variables = {
        "context": {
            "song_structure": {"intro": [0, 8], "verse": [8, 24]},
            "fixtures": {"count": 4, "groups": ["front", "back"]},
            "available_templates": ["template1", "template2"],
            "beat_grid": {
                "tempo": 120,
                "time_signature": "4/4",
                "total_bars": 32,
            },
        },
        "feedback": None,
        "response_schema": "{}",  # Add response_schema variable
    }

    rendered = renderer.render(prompts["user"], variables)

    # Should contain rendered content
    assert "intro" in rendered
    assert "120 BPM" in rendered
    assert "4 moving heads" in rendered


def test_render_planner_with_feedback(prompt_loader, renderer):
    """Test rendering planner prompt with feedback."""
    prompts = prompt_loader.load("planner")

    variables = {
        "context": {
            "song_structure": {"intro": [0, 8]},
            "fixtures": {"count": 4, "groups": []},
            "available_templates": [],
            "beat_grid": {"tempo": 120, "time_signature": "4/4", "total_bars": 32},
        },
        "feedback": ["Needs more variety in verse", "Chorus energy too low"],
        "response_schema": "{}",  # Add response_schema variable
    }

    rendered = renderer.render(prompts["user"], variables)

    # Should include feedback
    assert "Feedback from Previous Iteration" in rendered
    assert "Needs more variety in verse" in rendered


def test_render_validator_user_prompt(prompt_loader, renderer):
    """Test rendering validator user prompt."""
    prompts = prompt_loader.load("validator")

    variables = {
        "plan": {
            "sections": [
                {
                    "name": "intro",
                    "sequences": [{"template": "sweep_lr", "timing": {}}],
                }
            ]
        },
        "context": {
            "song_structure": {"intro": [0, 8]},
            "available_templates": ["sweep_lr", "fan_pulse"],
            "beat_grid": {"total_bars": 32},
        },
        "response_schema": "{}",  # Add response_schema variable
    }

    rendered = renderer.render(prompts["user"], variables)

    # Should contain plan and context
    assert "intro" in rendered
    assert "sweep_lr" in rendered


def test_render_judge_user_prompt(prompt_loader, renderer):
    """Test rendering judge user prompt."""
    prompts = prompt_loader.load("judge")

    variables = {
        "plan": {"sections": [{"name": "intro"}]},
        "context": {"song_structure": {"intro": [0, 8]}},
        "iteration": 1,
        "previous_feedback": [],
        "response_schema": "{}",  # Add response_schema variable
    }

    rendered = renderer.render(prompts["user"], variables)

    # Should contain plan
    assert "intro" in rendered
    assert "Evaluate the following" in rendered


def test_render_judge_with_iteration(prompt_loader, renderer):
    """Test rendering judge prompt with iteration info."""
    prompts = prompt_loader.load("judge")

    variables = {
        "plan": {"sections": []},
        "context": {"song_structure": {}},
        "iteration": 3,
        "previous_feedback": ["Fix timing", "Add variety"],
        "response_schema": "{}",  # Add response_schema variable
    }

    rendered = renderer.render(prompts["user"], variables)

    # Should show iteration context
    assert "iteration 3" in rendered.lower()
    assert "Fix timing" in rendered


def test_all_prompts_have_required_keys(prompt_loader):
    """Test all prompt packs have required prompts."""
    for pack_name in ["planner", "validator", "judge"]:
        prompts = prompt_loader.load(pack_name)

        # All should have system and user
        assert "system" in prompts, f"{pack_name} missing system prompt"
        assert "user" in prompts, f"{pack_name} missing user prompt"

        # Should be non-empty
        assert len(prompts["system"]) > 100, f"{pack_name} system prompt too short"
        assert len(prompts["user"]) > 100, f"{pack_name} user prompt too short"


def test_prompts_contain_key_concepts():
    """Test prompts contain domain-specific concepts."""
    loader = PromptPackLoader(base_path=PROMPTS_BASE)

    # Planner should mention templates, choreography
    planner = loader.load("planner")
    assert "template" in planner["system"].lower()
    assert "choreography" in planner["system"].lower()

    # Validator should mention validation, checks
    validator = loader.load("validator")
    assert "validation" in validator["system"].lower() or "validate" in validator["system"].lower()

    # Judge should mention evaluation, quality
    judge = loader.load("judge")
    assert "evaluat" in judge["system"].lower() or "judge" in judge["system"].lower()
