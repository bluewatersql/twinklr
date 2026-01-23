"""Tests for fallback renderer (when Jinja2 not available)."""

from unittest.mock import patch

import pytest

from blinkb0t.core.agents.prompts.renderer import PromptRenderer, RenderError


@patch("blinkb0t.core.agents.prompts.renderer.PromptRenderer.__init__")
def test_simple_renderer_basic(mock_init):
    """Test simple $var renderer."""
    renderer = PromptRenderer.__new__(PromptRenderer)
    renderer.use_jinja2 = False

    result = renderer._simple_render("Hello $name!", {"name": "World"})

    assert result == "Hello World!"


@patch("blinkb0t.core.agents.prompts.renderer.PromptRenderer.__init__")
def test_simple_renderer_multiple_vars(mock_init):
    """Test simple renderer with multiple variables."""
    renderer = PromptRenderer.__new__(PromptRenderer)
    renderer.use_jinja2 = False

    result = renderer._simple_render(
        "Agent: $agent_name, Iteration: $iteration",
        {"agent_name": "planner", "iteration": "5"},
    )

    assert result == "Agent: planner, Iteration: 5"


@patch("blinkb0t.core.agents.prompts.renderer.PromptRenderer.__init__")
def test_simple_renderer_missing_variable(mock_init):
    """Test simple renderer raises on missing variable."""
    renderer = PromptRenderer.__new__(PromptRenderer)
    renderer.use_jinja2 = False

    with pytest.raises(RenderError) as exc_info:
        renderer._simple_render("Hello $name!", {})

    assert "Unresolved variables" in str(exc_info.value)
    assert "name" in str(exc_info.value)


@patch("blinkb0t.core.agents.prompts.renderer.PromptRenderer.__init__")
def test_simple_renderer_escape_dollar(mock_init):
    """Test simple renderer handles $$ escape."""
    renderer = PromptRenderer.__new__(PromptRenderer)
    renderer.use_jinja2 = False

    result = renderer._simple_render("Price: $$10", {})

    assert result == "Price: $10"
