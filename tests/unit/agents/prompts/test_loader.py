"""Tests for prompt pack loader."""

from pathlib import Path

import pytest

from twinklr.core.agents.prompts.loader import LoadError, PromptPackLoader

FIXTURES_PATH = Path(__file__).parent.parent.parent.parent / "fixtures" / "prompts"


def test_loader_init():
    """Test loader initialization."""
    loader = PromptPackLoader(base_path=FIXTURES_PATH)

    assert loader.base_path == FIXTURES_PATH


def test_load_complete_pack():
    """Test loading complete prompt pack."""
    loader = PromptPackLoader(base_path=FIXTURES_PATH)

    prompts = loader.load("test_pack")

    # Should have all components
    assert "system" in prompts
    assert "developer" in prompts
    assert "user" in prompts
    assert "examples" in prompts

    # Check types
    assert isinstance(prompts["system"], str)
    assert isinstance(prompts["developer"], str)
    assert isinstance(prompts["user"], str)
    assert isinstance(prompts["examples"], list)


def test_load_minimal_pack():
    """Test loading pack with only system prompt."""
    loader = PromptPackLoader(base_path=FIXTURES_PATH)

    prompts = loader.load("minimal_pack")

    # Should have system
    assert "system" in prompts
    assert isinstance(prompts["system"], str)

    # Should NOT have optional components
    assert "developer" not in prompts
    assert "user" not in prompts
    assert "examples" not in prompts


def test_load_nonexistent_pack():
    """Test loading nonexistent pack raises error."""
    loader = PromptPackLoader(base_path=FIXTURES_PATH)

    with pytest.raises(LoadError) as exc_info:
        loader.load("nonexistent_pack")

    assert "does not exist" in str(exc_info.value).lower()


def test_load_pack_without_system():
    """Test loading pack without system.j2 raises error."""
    loader = PromptPackLoader(base_path=FIXTURES_PATH)

    # Create a pack without system.j2
    test_dir = FIXTURES_PATH / "no_system_pack"
    test_dir.mkdir(exist_ok=True)
    (test_dir / "developer.j2").write_text("Test")

    try:
        with pytest.raises(LoadError) as exc_info:
            loader.load("no_system_pack")

        assert "system.j2" in str(exc_info.value).lower()
    finally:
        # Cleanup
        (test_dir / "developer.j2").unlink()
        test_dir.rmdir()


def test_load_and_render():
    """Test loading and rendering in one call."""
    loader = PromptPackLoader(base_path=FIXTURES_PATH)

    variables = {
        "agent_name": "test_agent",
        "iteration": 1,
        "context": {"test": "data"},
        "feedback": None,
    }

    prompts = loader.load_and_render("test_pack", variables)

    # Should have rendered templates
    assert "test_agent" in prompts["system"]
    assert "iteration 1" in prompts["system"]


def test_examples_parsing():
    """Test examples.jsonl parsing."""
    loader = PromptPackLoader(base_path=FIXTURES_PATH)

    prompts = loader.load("test_pack")

    examples = prompts["examples"]
    assert len(examples) == 2
    assert examples[0]["role"] == "user"
    assert examples[0]["content"] == "Example user message"
    assert examples[1]["role"] == "assistant"


def test_load_invalid_examples_jsonl():
    """Test handling invalid examples.jsonl."""
    loader = PromptPackLoader(base_path=FIXTURES_PATH)

    # Create pack with invalid examples
    test_dir = FIXTURES_PATH / "invalid_examples_pack"
    test_dir.mkdir(exist_ok=True)
    (test_dir / "system.j2").write_text("Test system")
    (test_dir / "examples.jsonl").write_text("not valid json\n")

    try:
        with pytest.raises(LoadError) as exc_info:
            loader.load("invalid_examples_pack")

        assert "examples.jsonl" in str(exc_info.value).lower()
    finally:
        # Cleanup
        (test_dir / "system.j2").unlink()
        (test_dir / "examples.jsonl").unlink()
        test_dir.rmdir()


def test_render_with_missing_variable():
    """Test rendering fails on missing variable."""
    loader = PromptPackLoader(base_path=FIXTURES_PATH)

    # Missing 'iteration' variable
    variables = {"agent_name": "test"}

    with pytest.raises(Exception):  # Could be RenderError or similar  # noqa: B017
        loader.load_and_render("test_pack", variables)
